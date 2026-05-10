"""Phase 15 — GL Audit Workbench endpoints (seed-backed, stable contracts).

Implements the SRS `/api/gl/*` surface using existing seeded collections:
- `master_gl_accounts` (GL master)
- `transactions` / `transaction_lines` (if present) or falls back to `journals`
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from app.auth import get_current_user
from app.deps import audit_log, db
from app.services.kpi_service import as_of_now
from app.services.rbac_service import enforce_entity_scope


router = APIRouter(prefix="/gl", tags=["gl"])


@router.get("/accounts")
async def gl_accounts(
    entity_code: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    current=Depends(get_current_user),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity_code"] = entity_code
    cur = db.master_gl_accounts.find(q, {"_id": 0}).sort("account_code", 1).skip(offset).limit(limit)
    items = [a async for a in cur]
    total = await db.master_gl_accounts.count_documents(q)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": as_of_now()}


@router.get("/transactions")
async def gl_transactions(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    current=Depends(get_current_user),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    if period_ym:
        # supports either `posting_date` or `txn_date` prefixes depending on seed
        q["$or"] = [{"posting_date": {"$regex": f"^{period_ym}"}}, {"txn_date": {"$regex": f"^{period_ym}"}}]

    # Prefer `transactions` if present; else fall back to seeded `journals`.
    if "transactions" in await db.list_collection_names():
        cur = db.transactions.find(q, {"_id": 0}).sort("txn_date", -1).skip(offset).limit(limit)
        items = [t async for t in cur]
        total = await db.transactions.count_documents(q)
        source = "transactions"
    else:
        cur = db.journals.find(q, {"_id": 0}).sort("posting_date", -1).skip(offset).limit(limit)
        items = [t async for t in cur]
        total = await db.journals.count_documents(q)
        source = "journals"

    return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": as_of_now(), "source": source}


@router.get("/summary")
async def gl_summary(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    tx = await gl_transactions(entity_code=entity_code, period_ym=period_ym, limit=200, offset=0, current=current)
    items = tx.get("items") or []
    total_amount = 0.0
    for t in items:
        total_amount += float(t.get("amount") or t.get("total_amount") or 0.0)
    return {
        "as_of": as_of_now(),
        "entity_code": entity_code,
        "period_ym": period_ym,
        "kpis": {"txn_count": len(items), "total_amount": round(total_amount, 2)},
        "source": f"gl_summary_from_{tx.get('source')}",
    }


@router.get("/anomalies")
async def gl_anomalies(
    entity_code: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    current=Depends(get_current_user),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    # Use existing exceptions where control_code indicates GL signals; otherwise empty.
    q: Dict[str, Any] = {"process": "Finance"}
    if entity_code:
        q["entity_code"] = entity_code
    cur = db.exceptions.find(q, {"_id": 0}).sort("financial_exposure", -1).limit(limit)
    items = [e async for e in cur if str(e.get("control_code") or "").startswith("C-GL-")]
    return {"items": items, "count": len(items), "as_of": as_of_now(), "source": "exceptions:C-GL-*"}


@router.get("/movement-analysis")
async def gl_movement_analysis(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    # Minimal movement proxy: totals by day prefix from available txn list.
    tx = await gl_transactions(entity_code=entity_code, period_ym=period_ym, limit=500, offset=0, current=current)
    buckets: Dict[str, float] = {}
    for t in tx.get("items") or []:
        d = str(t.get("posting_date") or t.get("txn_date") or "")[:10] or "unknown"
        buckets[d] = buckets.get(d, 0.0) + float(t.get("amount") or t.get("total_amount") or 0.0)
    rows = [{"date": k, "amount": round(v, 2)} for k, v in sorted(buckets.items())]
    return {"items": rows, "count": len(rows), "as_of": as_of_now(), "source": f"movement_from_{tx.get('source')}"}


@router.get("/suspense-ageing")
async def gl_suspense_ageing(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    # Placeholder until we have suspense account mapping; return stable contract.
    return {
        "as_of": as_of_now(),
        "entity_code": entity_code,
        "items": [],
        "count": 0,
        "note": "Wire suspense account mapping to transactions/journals for ageing buckets.",
    }


@router.post("/signoff")
async def gl_signoff(body: Dict[str, Any], current=Depends(get_current_user)):
    be = body.get("entity") or body.get("entity_code")
    if be and str(be).strip():
        await enforce_entity_scope(db, current=current, requested_entity_code=str(be))
    sid = f"glso-{__import__('uuid').uuid4().hex[:10]}"
    doc = {**body, "id": sid, "created_at": as_of_now(), "created_by": current.get("email")}
    await db.gl_signoffs.insert_one(dict(doc))
    await audit_log(current["email"], "gl_signoff", "gl_signoff", sid, {"entity": body.get("entity"), "period_ym": body.get("period_ym")})
    return {"status": "ok", "signoff_id": sid, "as_of": as_of_now()}

