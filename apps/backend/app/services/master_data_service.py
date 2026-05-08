"""Unified master data lookups + adapters over legacy Mongo collections (Phase 2).

L4 hardening:
- pagination (limit/offset)
- lightweight search (`q`) where meaningful
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.rollup_service import get_hierarchy_tree
from app.utils.timeutil import iso_utc


def _iso_now() -> str:
    return iso_utc(datetime.now(timezone.utc))


def _q_entity(entity_code: Optional[str]) -> Dict[str, Any]:
    if not entity_code:
        return {}
    return {"entity_code": entity_code}


def _regex_q(q: Optional[str]) -> Optional[Dict[str, Any]]:
    qq = (q or "").strip()
    if not qq:
        return None
    return {"$regex": qq, "$options": "i"}


async def list_companies(db) -> List[Dict[str, Any]]:
    rows = [c async for c in db.companies.find({}, {"_id": 0}).sort("name", 1)]
    return rows


async def list_legal_entities(db, entity_code: Optional[str] = None) -> List[Dict[str, Any]]:
    """Adapter: `entities` collection → unified legal_entities shape."""
    q: Dict[str, Any] = {}
    if entity_code:
        q["code"] = entity_code
    out = []
    async for e in db.entities.find(q, {"_id": 0}).sort("code", 1):
        cid = await db.companies.find_one({}, {"_id": 0, "id": 1})
        company_id = cid["id"] if cid else None
        out.append(
            {
                "id": e.get("id") or e.get("code"),
                "code": e.get("code"),
                "name": e.get("name"),
                "geo": e.get("geo"),
                "company_id": company_id,
                "source": "entities",
            }
        )
    return out


async def list_business_units(db, entity_code: Optional[str] = None) -> List[Dict[str, Any]]:
    q = _q_entity(entity_code)
    return [r async for r in db.master_business_units.find(q, {"_id": 0}).sort("code", 1)]


async def list_locations(db, entity_code: Optional[str] = None) -> List[Dict[str, Any]]:
    q = _q_entity(entity_code)
    return [r async for r in db.master_locations.find(q, {"_id": 0}).sort("code", 1)]


async def list_departments(db, entity_code: Optional[str] = None) -> List[Dict[str, Any]]:
    q = _q_entity(entity_code)
    return [r async for r in db.master_departments.find(q, {"_id": 0}).sort("code", 1)]


async def list_cost_centers(db, entity_code: Optional[str] = None) -> List[Dict[str, Any]]:
    q = _q_entity(entity_code)
    return [r async for r in db.master_cost_centers.find(q, {"_id": 0}).sort("code", 1)]


async def list_gl_accounts(db, entity_code: Optional[str] = None) -> List[Dict[str, Any]]:
    q = _q_entity(entity_code)
    return [r async for r in db.master_gl_accounts.find(q, {"_id": 0}).sort("account_code", 1)]


async def list_vendors(
    db,
    entity_code: Optional[str] = None,
    *,
    limit: int = 500,
    offset: int = 0,
    q: Optional[str] = None,
) -> List[Dict[str, Any]]:
    qq: Dict[str, Any] = {}
    if entity_code:
        qq["entity"] = entity_code
    rq = _regex_q(q)
    if rq:
        qq["$or"] = [{"vendor_name": rq}, {"vendor_code": rq}, {"id": rq}]
    out: List[Dict[str, Any]] = []
    cur = db.vendors.find(qq, {"_id": 0}).sort("vendor_code", 1).skip(offset).limit(limit)
    async for v in cur:
        out.append(
            {
                "id": v.get("id"),
                "vendor_code": v.get("vendor_code") or v.get("id"),
                "vendor_name": v.get("vendor_name"),
                "entity_code": v.get("entity"),
                "status": v.get("status", "active"),
                "pan": v.get("pan"),
                "gstin": v.get("gstin"),
                "bank_account_masked": v.get("bank_account_masked") or v.get("bank_account_number_masked"),
                "ifsc": v.get("ifsc"),
                "source": "vendors",
            }
        )
    return out


async def list_customers(
    db,
    entity_code: Optional[str] = None,
    *,
    limit: int = 500,
    offset: int = 0,
    q: Optional[str] = None,
) -> List[Dict[str, Any]]:
    qq: Dict[str, Any] = {}
    if entity_code:
        qq["entity"] = entity_code
    rq = _regex_q(q)
    if rq:
        qq["$or"] = [{"customer_name": rq}, {"customer_code": rq}, {"id": rq}]
    out = []
    cur = db.customers.find(qq, {"_id": 0}).sort("customer_code", 1).skip(offset).limit(limit)
    async for c in cur:
        out.append(
            {
                "id": c.get("id"),
                "customer_code": c.get("customer_code") or c.get("id"),
                "customer_name": c.get("customer_name"),
                "entity_code": c.get("entity"),
                "status": c.get("status", "active"),
                "credit_limit": c.get("credit_limit"),
                "gstin": c.get("gstin"),
                "source": "customers",
            }
        )
    return out


async def list_employees(
    db,
    entity_code: Optional[str] = None,
    *,
    limit: int = 500,
    offset: int = 0,
    q: Optional[str] = None,
) -> List[Dict[str, Any]]:
    qq: Dict[str, Any] = {}
    if entity_code:
        qq["entity"] = entity_code
    rq = _regex_q(q)
    if rq:
        qq["$or"] = [{"full_name": rq}, {"employee_code": rq}, {"email": rq}, {"id": rq}]
    out = []
    cur = db.employees.find(qq, {"_id": 0}).sort("employee_code", 1).skip(offset).limit(limit)
    async for e in cur:
        dept = await db.master_departments.find_one(
            {"name": e.get("department"), "entity_code": e.get("entity")},
            {"_id": 0, "id": 1},
        )
        out.append(
            {
                "id": e.get("id"),
                "employee_number": e.get("employee_code") or e.get("id"),
                "full_name": e.get("full_name"),
                "entity_code": e.get("entity"),
                "email": e.get("email"),
                "department_id": dept["id"] if dept else None,
                "status": e.get("status", "active"),
                "source": "employees",
            }
        )
    return out


async def list_bank_accounts(db, entity_code: Optional[str] = None) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    out = []
    async for b in db.bank_accounts.find(q, {"_id": 0}).sort("id", 1):
        out.append(
            {
                "id": b.get("id"),
                "account_name": f"{b.get('bank_name', 'Bank')} ({b.get('currency', 'USD')})",
                "entity_code": b.get("entity"),
                "currency": b.get("currency", "USD"),
                "bank_name": b.get("bank_name"),
                "masked_number": b.get("account_number_masked"),
                "source": "bank_accounts",
            }
        )
    return out


async def list_transactions(
    db,
    entity_code: Optional[str] = None,
    *,
    limit: int = 200,
    offset: int = 0,
    q: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Adapter: GL journals as transaction headers."""
    qq: Dict[str, Any] = {}
    if entity_code:
        qq["entity"] = entity_code
    rq = _regex_q(q)
    if rq:
        qq["$or"] = [{"journal_number": rq}, {"id": rq}, {"narration": rq}]
    out = []
    cur = db.journals.find(qq, {"_id": 0}).sort("posting_date", -1).skip(offset).limit(limit)
    async for j in cur:
        out.append(
            {
                "id": j.get("id"),
                "document_number": j.get("journal_number") or j.get("id"),
                "entity_code": j.get("entity"),
                "posting_date": j.get("posting_date"),
                "total_amount": float(j.get("total_amount") or 0),
                "source": "journals",
            }
        )
    return out


async def list_transaction_lines(
    db, entity_code: Optional[str] = None, transaction_id: Optional[str] = None, limit: int = 500
) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity_code"] = entity_code
    if transaction_id:
        q["transaction_id"] = transaction_id
    return [x async for x in db.master_transaction_lines.find(q, {"_id": 0}).sort("transaction_id", 1).limit(limit)]


async def list_documents(db, entity_code: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity_code"] = entity_code
    return [d async for d in db.master_documents.find(q, {"_id": 0}).sort("title", 1).limit(limit)]


async def list_risk_scores(db, entity_code: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity_code"] = entity_code
    out: List[Dict[str, Any]] = []
    async for r in db.finance_risk_scores.find(q, {"_id": 0}).sort("score", -1).limit(limit):
        # Older seeded rows may miss a top-level `id`, but API responses require it.
        rid = r.get("id") or r.get("natural_key") or f"{r.get('object_type')}::{r.get('object_id')}"
        out.append({**r, "id": rid})
    return out


async def list_audit_trail(db, limit: int = 100) -> List[Dict[str, Any]]:
    """Prefer master_data_audit_trail; fallback to recent audit_logs."""
    n_master = await db.master_data_audit_trail.count_documents({})
    coll = db.master_data_audit_trail if n_master else db.audit_logs
    field_map = "master" if n_master else "legacy"

    out: List[Dict[str, Any]] = []
    if n_master:
        async for row in coll.find({}, {"_id": 0}).sort("at", -1).limit(limit):
            out.append({**row, "source": field_map})
    else:
        async for row in coll.find({}, {"_id": 0}).sort("event_ts", -1).limit(limit):
            out.append(
                {
                    "id": row.get("id"),
                    "at": row.get("event_ts"),
                    "actor_email": row.get("actor_user_email"),
                    "action": row.get("action_type"),
                    "resource_type": row.get("object_type"),
                    "resource_id": row.get("object_id"),
                    "detail": row.get("detail"),
                    "source": "audit_logs",
                }
            )
    return out


async def query_audit_trail(
    db,
    *,
    q: Optional[str] = None,
    actor_email: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    entity_code: Optional[str] = None,
    since_ts: Optional[str] = None,
    until_ts: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    """Query master audit trail with stable filters and pagination.

    Prefers `master_data_audit_trail` when present; otherwise maps from legacy `audit_logs`.
    """
    n_master = await db.master_data_audit_trail.count_documents({})
    if n_master:
        filt: Dict[str, Any] = {}
        if q and q.strip():
            rq = _regex_q(q.strip())
            filt["$or"] = [{"actor_email": rq}, {"action": rq}, {"resource_type": rq}, {"resource_id": rq}]
        if actor_email:
            filt["actor_email"] = actor_email
        if resource_type:
            filt["resource_type"] = resource_type
        if resource_id:
            filt["resource_id"] = resource_id
        if entity_code:
            filt["entity_code"] = entity_code
        if since_ts or until_ts:
            ts: Dict[str, Any] = {}
            if since_ts:
                ts["$gte"] = since_ts
            if until_ts:
                ts["$lte"] = until_ts
            filt["at"] = ts
        total = await db.master_data_audit_trail.count_documents(filt)
        cur = (
            db.master_data_audit_trail.find(filt, {"_id": 0})
            .sort("at", -1)
            .skip(offset)
            .limit(limit)
        )
        items = [{**row, "source": "master"} async for row in cur]
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    # legacy mapping from audit_logs
    filt2: Dict[str, Any] = {}
    if q and q.strip():
        rq = _regex_q(q.strip())
        filt2["$or"] = [
            {"actor_user_email": rq},
            {"action_type": rq},
            {"object_type": rq},
            {"object_id": rq},
        ]
    if actor_email:
        filt2["actor_user_email"] = actor_email
    if resource_type:
        filt2["object_type"] = resource_type
    if resource_id:
        filt2["object_id"] = resource_id
    if since_ts or until_ts:
        ts: Dict[str, Any] = {}
        if since_ts:
            ts["$gte"] = since_ts
        if until_ts:
            ts["$lte"] = until_ts
        filt2["event_ts"] = ts
    total2 = await db.audit_logs.count_documents(filt2)
    cur2 = db.audit_logs.find(filt2, {"_id": 0}).sort("event_ts", -1).skip(offset).limit(limit)
    items2: List[Dict[str, Any]] = []
    async for row in cur2:
        items2.append(
            {
                "id": row.get("id"),
                "at": row.get("event_ts"),
                "actor_email": row.get("actor_user_email"),
                "action": row.get("action_type"),
                "resource_type": row.get("object_type"),
                "resource_id": row.get("object_id"),
                "detail": row.get("detail"),
                "source": "audit_logs",
            }
        )
    return {"items": items2, "total": total2, "limit": limit, "offset": offset}


async def entity_hierarchy_tree(db) -> List[Dict[str, Any]]:
    """Thin wrapper for rollups hierarchy (org → regions → legal entities)."""
    return await get_hierarchy_tree(db)
