"""Wave 3 — GL / JE / recon / bank REST trees (MVP on seeded Mongo collections)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.deps import db

router = APIRouter(prefix="/audit-depth", tags=["audit-depth"])


@router.get("/gl/accounts")
async def gl_accounts(
    entity_code: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    current=Depends(get_current_user),
):
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity_code"] = entity_code
    cur = db.master_gl_accounts.find(q, {"_id": 0}).sort("account_code", 1).skip(offset).limit(limit)
    items = [a async for a in cur]
    total = await db.master_gl_accounts.count_documents(q)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/journal-entries")
async def journal_entries(
    entity_code: Optional[str] = Query(None),
    is_manual: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current=Depends(get_current_user),
):
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    if is_manual is not None:
        q["is_manual"] = is_manual
    cur = db.journals.find(q, {"_id": 0}).sort("posting_date", -1).skip(offset).limit(limit)
    items = [j async for j in cur]
    total = await db.journals.count_documents(q)
    return {"items": items, "total": total, "workflow": {"states": ["draft", "posted", "reversed"]}}


@router.get("/journal-entries/{je_id}")
async def journal_entry_detail(je_id: str, current=Depends(get_current_user)):
    doc = await db.journals.find_one({"id": je_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Journal entry not found")
    return doc


@router.get("/reconciliations")
async def recon_list(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current=Depends(get_current_user),
):
    from app.analytics import _reconciliation_scope

    q = _reconciliation_scope(entity_code, period_ym)
    if status:
        q = {**q, "status": status}
    cur = db.reconciliations.find(q, {"_id": 0}).sort("due_date", -1).skip(offset).limit(limit)
    items = [r async for r in cur]
    total = await db.reconciliations.count_documents(q)
    return {"items": items, "total": total}


@router.get("/bank/activity")
async def bank_activity(
    entity_code: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    current=Depends(get_current_user),
):
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    cur = db.bank_transactions.find(q, {"_id": 0}).sort("txn_ts", -1).limit(limit)
    items = [t async for t in cur]
    return {"items": items, "count": len(items)}


@router.get("/vendor/risk-flags")
async def vendor_risk_flags(
    limit: int = Query(50, ge=1, le=500),
    current=Depends(get_current_user),
):
    """Placeholder vendor risk surface; extend with vendor master + P2P signals."""
    return {
        "items": [],
        "count": 0,
        "note": "Wire vendor collection and 3-way match outcomes (Wave 3).",
    }
