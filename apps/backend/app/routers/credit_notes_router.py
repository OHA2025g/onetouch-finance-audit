"""Phase 22 — Credit Note and Revenue Reversal Analytics (seed-backed)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.deps import audit_log, db
from app.services.kpi_service import as_of_now
from app.services.rbac_service import enforce_entity_scope


router = APIRouter(prefix="/credit-notes", tags=["credit-notes"])


def _now() -> str:
    return as_of_now()


def _parse_dt(s: Any) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:  # noqa: BLE001
        return None


async def _ensure_seed_credit_notes(entity_code: Optional[str] = None) -> int:
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    existing = await db.credit_notes.count_documents(q)
    if existing > 0:
        return 0

    # Synthesize from invoices: pick a small sample and generate credit notes.
    inv_q: Dict[str, Any] = {}
    if entity_code:
        inv_q["entity"] = entity_code
    invs = [i async for i in db.invoices.find(inv_q, {"_id": 0}).sort("invoice_date", -1).limit(80)]
    if not invs:
        return 0

    now = datetime.now(timezone.utc)
    docs = []
    for idx, inv in enumerate(invs[:25]):
        inv_dt = _parse_dt(inv.get("invoice_date")) or now
        cn_dt = inv_dt + timedelta(days=timedelta(days=15).days + (idx % 7))
        amt = round(float(inv.get("amount") or 0.0) * (0.1 if idx % 6 else 0.4), 2)
        docs.append(
            {
                "id": f"CN-{inv.get('id')}",
                "credit_note_number": f"CN-{inv.get('id')}",
                "entity": inv.get("entity"),
                "vendor_id": inv.get("vendor_id"),
                "vendor_name": inv.get("vendor_name"),
                "invoice_id": inv.get("id"),
                "invoice_number": inv.get("invoice_number"),
                "credit_note_date": cn_dt.astimezone(timezone.utc).isoformat(),
                "amount": amt,
                "reason": "pricing_adjustment" if idx % 3 else "return",
                "approved": False if idx % 5 == 0 else True,
                "status": "open" if idx % 4 == 0 else "posted",
                "created_at": _now(),
            }
        )
    if docs:
        await db.credit_notes.insert_many(docs)
    return len(docs)


@router.get("/summary")
async def credit_notes_summary(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_credit_notes(entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    total = await db.credit_notes.count_documents(q)
    open_cnt = await db.credit_notes.count_documents({**q, "status": "open"})
    unapproved = await db.credit_notes.count_documents({**q, "approved": False})
    amt = 0.0
    async for cn in db.credit_notes.find(q, {"_id": 0, "amount": 1}).limit(2000):
        amt += float(cn.get("amount") or 0.0)
    return {
        "as_of": _now(),
        "entity_code": entity_code,
        "kpis": {
            "credit_note_count": total,
            "open_credit_notes": open_cnt,
            "unapproved_credit_notes": unapproved,
            "total_credit_amount": round(amt, 2),
        },
        "source": "credit_notes (seed-synth from invoices if empty)",
    }


@router.get("")
async def credit_notes_list(entity_code: Optional[str] = Query(None), limit: int = Query(200, ge=1, le=2000), offset: int = Query(0, ge=0), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_credit_notes(entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    cur = db.credit_notes.find(q, {"_id": 0}).sort("credit_note_date", -1).skip(offset).limit(limit)
    items = [x async for x in cur]
    total = await db.credit_notes.count_documents(q)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": _now()}


@router.get("/high-risk")
async def credit_notes_high_risk(entity_code: Optional[str] = Query(None), limit: int = Query(50, ge=1, le=500), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_credit_notes(entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    cur = db.credit_notes.find(q, {"_id": 0}).sort("amount", -1).limit(500)
    items = [x async for x in cur]
    # high-risk proxy: large or unapproved
    out = [x for x in items if float(x.get("amount") or 0.0) >= 20000 or x.get("approved") is False]
    out.sort(key=lambda x: -(float(x.get("amount") or 0.0)))
    return {"items": out[:limit], "count": len(out), "as_of": _now(), "note": "Risk proxy: amount>=20k OR approved=false"}


@router.get("/revenue-reversals")
async def credit_notes_revenue_reversals(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_credit_notes(entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    # Trend proxy: group by YYYY-MM
    buckets: Dict[str, float] = {}
    async for cn in db.credit_notes.find(q, {"_id": 0, "credit_note_date": 1, "amount": 1}):
        ym = str(cn.get("credit_note_date") or "")[:7] or "unknown"
        buckets[ym] = buckets.get(ym, 0.0) + float(cn.get("amount") or 0.0)
    rows = [{"period_ym": k, "credit_amount": round(v, 2)} for k, v in sorted(buckets.items())]
    return {"items": rows, "count": len(rows), "as_of": _now(), "source": "credit_notes_by_month"}


@router.post("/{credit_note_id}/review")
async def credit_note_review(credit_note_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    cn0 = await db.credit_notes.find_one({"id": credit_note_id}, {"_id": 0, "entity": 1})
    if cn0 and cn0.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=cn0.get("entity"))
    decision = str(body.get("decision") or "reviewed")
    note = body.get("note")
    await db.credit_note_reviews.insert_one({"id": f"cnr-{__import__('uuid').uuid4().hex[:10]}", "credit_note_id": credit_note_id, "decision": decision, "note": note, "by": current.get("email"), "at": _now()})
    await audit_log(current["email"], "credit_note_review", "credit_note", credit_note_id, {"decision": decision})
    return {"status": "ok", "as_of": _now()}


@router.post("/{credit_note_id}/create-case")
async def credit_note_create_case(credit_note_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    cn = await db.credit_notes.find_one({"id": credit_note_id}, {"_id": 0})
    if not cn:
        raise HTTPException(404, "Credit note not found")
    if cn.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=cn.get("entity"))

    now = _now()
    cid = f"case-cn-{__import__('uuid').uuid4().hex[:10]}"
    ex_id = f"cn-{credit_note_id}"

    ex_doc = {
        "id": ex_id,
        "control_id": "C-CN-001",
        "control_code": "CN-001",
        "control_name": "Credit note risk follow-up",
        "process": "Order-to-Cash",
        "entity": cn.get("entity") or current.get("entity") or "US-HQ",
        "severity": str(body.get("severity") or "medium"),
        "status": "open",
        "materiality_score": float(body.get("materiality_score") or 0.4),
        "anomaly_score": float(body.get("anomaly_score") or 0.4),
        "financial_exposure": float(body.get("financial_exposure") or float(cn.get("amount") or 0.0)),
        "source_record_type": "credit_note",
        "source_record_id": credit_note_id,
        "detected_at": now,
        "title": body.get("title") or f"Credit note review: {credit_note_id}",
        "summary": body.get("summary") or "Case created from Credit Note Analytics module.",
        "recurrence_count": 0,
        "department_id": None,
        "cost_center_id": None,
    }
    await db.exceptions.update_one({"id": ex_id}, {"$setOnInsert": ex_doc}, upsert=True)

    case_doc = {
        "id": cid,
        "exception_id": ex_id,
        "control_code": ex_doc["control_code"],
        "control_name": ex_doc["control_name"],
        "title": ex_doc["title"],
        "summary": ex_doc["summary"],
        "severity": ex_doc["severity"],
        "status": "open",
        "priority": body.get("priority") or "P2",
        "owner_email": body.get("owner_email") or current.get("email"),
        "owner_name": None,
        "due_date": body.get("due_date") or now,
        "financial_exposure": float(ex_doc.get("financial_exposure") or 0.0),
        "entity": ex_doc["entity"],
        "process": ex_doc["process"],
        "detected_at": now,
        "opened_at": now,
        "closed_at": None,
        "root_cause_category": None,
        "engagement_id": None,
        "material_impact": body.get("material_impact"),
        "material_watch": None,
        "department_id": None,
        "cost_center_id": None,
    }
    await db.cases.insert_one(dict(case_doc))
    await audit_log(current["email"], "credit_note_create_case", "case", cid, {"credit_note_id": credit_note_id})
    return {"status": "ok", "case_id": cid, "exception_id": ex_id, "as_of": _now()}

