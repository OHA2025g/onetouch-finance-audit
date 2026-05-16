"""Phase 18 — Bank Reconciliation Automation (seed-backed workflow)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.auth import get_current_user
from app.deps import audit_log, db
from app.services import bank_recon_service as brs
from app.services.kpi_service import as_of_now
from app.services.rbac_service import enforce_entity_scope


router = APIRouter(prefix="/bank-recon", tags=["bank-recon"])


def _now() -> str:
    return as_of_now()


async def _get_statement(statement_id: str) -> Dict[str, Any]:
    st = await db.bank_recon_statements.find_one({"id": statement_id}, {"_id": 0})
    if not st:
        raise HTTPException(404, "Statement not found")
    return st


@router.get("/summary")
async def bank_recon_summary(
    entity_code: Optional[str] = Query(None),
    scan_limit: int = Query(500, ge=1, le=2000),
    current=Depends(get_current_user),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    summary = await brs.build_summary(db, entity_code=entity_code, scan_limit=scan_limit)
    return {**summary, "entity_code": entity_code, "as_of": _now()}


@router.post("/upload-statement")
async def upload_statement(body: Dict[str, Any], current=Depends(get_current_user)):
    """JSON statement upload: { entity, bank_account_id?, statement_period?, items: [...] }"""
    sid = f"bst-{__import__('uuid').uuid4().hex[:10]}"
    ent_resolved = await enforce_entity_scope(
        db, current=current, requested_entity_code=(body.get("entity") or body.get("entity_code"))
    )
    payload = dict(body)
    if ent_resolved:
        payload["entity"] = ent_resolved
    items = payload.get("items") or []
    counts = brs.count_line_buckets([{**i, "match_status": "unmatched"} for i in items])
    doc = {
        **payload,
        "id": sid,
        "status": "uploaded",
        "created_at": _now(),
        "created_by": current.get("email"),
        **counts,
    }
    await db.bank_recon_statements.insert_one(dict(doc))
    await audit_log(current["email"], "bank_statement_upload", "bank_recon_statement", sid, {"entity": doc.get("entity")})
    return {"status": "ok", "statement_id": sid, "as_of": _now()}


@router.post("/upload-statement/csv")
async def upload_statement_csv(body: Dict[str, Any] = Body(...), current=Depends(get_current_user)):
    """CSV text upload: { entity, bank_account_id?, statement_period?, csv_text }."""
    csv_text = body.get("csv_text") or body.get("csv") or ""
    if not str(csv_text).strip():
        raise HTTPException(400, "csv_text is required")
    items = brs.parse_csv_statement(str(csv_text))
    if not items:
        raise HTTPException(400, "No rows parsed from CSV")
    payload = {
        "entity": body.get("entity") or body.get("entity_code"),
        "bank_account_id": body.get("bank_account_id"),
        "statement_period": body.get("statement_period"),
        "items": items,
        "source": "csv",
    }
    return await upload_statement(payload, current=current)


@router.get("/statements")
async def list_statements(
    entity_code: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    current=Depends(get_current_user),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    cur = db.bank_recon_statements.find(q, {"_id": 0}).sort("created_at", -1).limit(limit)
    items = [s async for s in cur]
    return {"items": items, "count": len(items), "as_of": _now()}


@router.get("/{statement_id}")
async def get_statement(statement_id: str, current=Depends(get_current_user)):
    st = await _get_statement(statement_id)
    if st.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=st.get("entity"))
    items = await brs.enrich_statement_items(db, st)
    classifications = [
        c async for c in db.bank_recon_classifications.find({"statement_id": statement_id}, {"_id": 0}).sort("created_at", -1).limit(20)
    ]
    signoffs = [
        s async for s in db.bank_recon_signoffs.find({"statement_id": statement_id}, {"_id": 0}).sort("created_at", -1).limit(5)
    ]
    return {
        "statement": {**st, "items": items},
        "classifications": classifications,
        "signoffs": signoffs,
        "as_of": _now(),
    }


@router.post("/{statement_id}/auto-match")
async def auto_match(statement_id: str, current=Depends(get_current_user)):
    st = await _get_statement(statement_id)
    if st.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=st.get("entity"))

    items, counts = await brs.run_auto_match(db, st)
    await db.bank_recon_statements.update_one(
        {"id": statement_id},
        {
            "$set": {
                "status": "matched",
                "items": items,
                "updated_at": _now(),
                **counts,
            }
        },
    )
    await audit_log(
        current["email"],
        "bank_recon_auto_match",
        "bank_recon_statement",
        statement_id,
        {"matched": counts["matched_count"], "unmatched": counts["unmatched_count"]},
    )
    return {
        "status": "ok",
        "matched": counts["matched_count"],
        "classified": counts["classified_count"],
        "unmatched": counts["unmatched_count"],
        "as_of": _now(),
    }


@router.get("/{statement_id}/unmatched")
async def unmatched_items(statement_id: str, current=Depends(get_current_user)):
    st = await _get_statement(statement_id)
    if st.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=st.get("entity"))
    items = await brs.enrich_statement_items(db, st)
    out = [i for i in items if i.get("match_status") == "unmatched"]
    return {"items": out, "count": len(out), "as_of": _now()}


@router.post("/{statement_id}/classify")
async def classify_unmatched(statement_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    """body: { items: [{reference, classification, notes?}] }"""
    st = await _get_statement(statement_id)
    if st.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=st.get("entity"))

    items = await brs.enrich_statement_items(db, st)
    class_items = body.get("items") or []
    items = await brs.apply_classifications(items, class_items)
    counts = brs.count_line_buckets(items)

    cid = f"cls-{__import__('uuid').uuid4().hex[:10]}"
    doc = {
        **body,
        "id": cid,
        "statement_id": statement_id,
        "created_at": _now(),
        "created_by": current.get("email"),
        "applied_count": len(class_items),
    }
    await db.bank_recon_classifications.insert_one(dict(doc))
    await db.bank_recon_statements.update_one(
        {"id": statement_id},
        {"$set": {"items": items, "updated_at": _now(), **counts}},
    )
    await audit_log(current["email"], "bank_recon_classify", "bank_recon_statement", statement_id, {"classification_id": cid})
    return {
        "status": "ok",
        "classification_id": cid,
        "unmatched": counts["unmatched_count"],
        "as_of": _now(),
    }


@router.post("/{statement_id}/signoff")
async def signoff(statement_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    st = await _get_statement(statement_id)
    if st.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=st.get("entity"))

    items = await brs.enrich_statement_items(db, st)
    counts = brs.count_line_buckets(items)
    unmatched = int(counts["unmatched_count"])
    if unmatched > 0 and not bool(body.get("acknowledge_residual_exceptions")):
        raise HTTPException(
            409,
            "Statement still has unmatched lines; classify them or pass acknowledge_residual_exceptions with a documented waiver.",
        )

    sid = f"bso-{__import__('uuid').uuid4().hex[:10]}"
    doc = {**body, "id": sid, "statement_id": statement_id, "created_at": _now(), "created_by": current.get("email")}
    await db.bank_recon_signoffs.insert_one(dict(doc))
    await db.bank_recon_statements.update_one(
        {"id": statement_id},
        {
            "$set": {
                "status": "signed_off",
                "signed_off_at": _now(),
                "signed_off_by": current.get("email"),
                "items": items,
                **counts,
            }
        },
    )
    await audit_log(current["email"], "bank_recon_signoff", "bank_recon_statement", statement_id, {"signoff_id": sid})
    return {"status": "ok", "signoff_id": sid, "as_of": _now()}
