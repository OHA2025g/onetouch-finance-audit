"""Phase 18 — Bank Reconciliation Automation (seed-backed workflow)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.deps import audit_log, db
from app.services.kpi_service import as_of_now


router = APIRouter(prefix="/bank-recon", tags=["bank-recon"])


def _now() -> str:
    return as_of_now()


@router.post("/upload-statement")
async def upload_statement(body: Dict[str, Any], current=Depends(get_current_user)):
    """Accept a JSON statement payload to stay container-friendly in tests.

    body: { entity, bank_account_id?, statement_period?, items: [{date, amount, direction?, reference?}] }
    """
    sid = f"bst-{__import__('uuid').uuid4().hex[:10]}"
    doc = {
        **body,
        "id": sid,
        "status": "uploaded",
        "created_at": _now(),
        "created_by": current.get("email"),
        "matched_count": 0,
        "unmatched_count": len(body.get("items") or []),
    }
    await db.bank_recon_statements.insert_one(dict(doc))
    await audit_log(current["email"], "bank_statement_upload", "bank_recon_statement", sid, {"entity": body.get("entity")})
    return {"status": "ok", "statement_id": sid, "as_of": _now()}


@router.get("/statements")
async def list_statements(
    entity_code: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    current=Depends(get_current_user),
):
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    cur = db.bank_recon_statements.find(q, {"_id": 0}).sort("created_at", -1).limit(limit)
    items = [s async for s in cur]
    return {"items": items, "count": len(items), "as_of": _now()}


@router.post("/{statement_id}/auto-match")
async def auto_match(statement_id: str, current=Depends(get_current_user)):
    st = await db.bank_recon_statements.find_one({"id": statement_id}, {"_id": 0})
    if not st:
        raise HTTPException(404, "Statement not found")

    items = st.get("items") or []
    # Simple placeholder: treat items with reference prefix "WIRE-" as matched.
    matched = [i for i in items if str(i.get("reference") or "").startswith("WIRE-")]
    unmatched = [i for i in items if i not in matched]

    await db.bank_recon_statements.update_one(
        {"id": statement_id},
        {"$set": {"status": "matched", "matched_count": len(matched), "unmatched_count": len(unmatched), "updated_at": _now()}},
    )
    await audit_log(current["email"], "bank_recon_auto_match", "bank_recon_statement", statement_id, {"matched": len(matched), "unmatched": len(unmatched)})
    return {"status": "ok", "matched": len(matched), "unmatched": len(unmatched), "as_of": _now()}


@router.get("/{statement_id}/unmatched")
async def unmatched_items(statement_id: str, current=Depends(get_current_user)):
    st = await db.bank_recon_statements.find_one({"id": statement_id}, {"_id": 0})
    if not st:
        raise HTTPException(404, "Statement not found")
    items = st.get("items") or []
    out = [i for i in items if not str(i.get("reference") or "").startswith("WIRE-")]
    return {"items": out, "count": len(out), "as_of": _now()}


@router.post("/{statement_id}/classify")
async def classify_unmatched(statement_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    """Record classification decisions for unmatched items.

    body: { items: [{reference, classification, notes?}] }
    """
    cid = f"cls-{__import__('uuid').uuid4().hex[:10]}"
    doc = {**body, "id": cid, "statement_id": statement_id, "created_at": _now(), "created_by": current.get("email")}
    await db.bank_recon_classifications.insert_one(dict(doc))
    await audit_log(current["email"], "bank_recon_classify", "bank_recon_statement", statement_id, {"classification_id": cid})
    return {"status": "ok", "classification_id": cid, "as_of": _now()}


@router.post("/{statement_id}/signoff")
async def signoff(statement_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    sid = f"bso-{__import__('uuid').uuid4().hex[:10]}"
    doc = {**body, "id": sid, "statement_id": statement_id, "created_at": _now(), "created_by": current.get("email")}
    await db.bank_recon_signoffs.insert_one(dict(doc))
    await db.bank_recon_statements.update_one({"id": statement_id}, {"$set": {"status": "signed_off", "signed_off_at": _now(), "signed_off_by": current.get("email")}})
    await audit_log(current["email"], "bank_recon_signoff", "bank_recon_statement", statement_id, {"signoff_id": sid})
    return {"status": "ok", "signoff_id": sid, "as_of": _now()}

