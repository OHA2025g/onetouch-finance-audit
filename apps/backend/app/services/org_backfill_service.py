"""Slice 9 — Backfill department/cost center onto transactional docs.

We already enrich exceptions via Phase 10/11 helpers. This slice ensures domain
documents also carry `department_id` and `cost_center_id` so dashboards can
scope AR/AP/treasury/FP&A by masters.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def _blank(field: str) -> Dict[str, Any]:
    return {"$or": [{field: {"$exists": False}}, {field: None}, {field: ""}]}


async def _dept_cc_for_entity(db, entity_code: str) -> Tuple[Optional[str], Optional[str]]:
    dept = await db.master_departments.find_one(
        {"entity_code": entity_code, "active": True},
        {"_id": 0, "id": 1, "cost_center_id": 1},
    )
    did = dept.get("id") if dept else None
    cid = dept.get("cost_center_id") if dept else None
    if not cid and did:
        cc = await db.master_cost_centers.find_one(
            {"entity_code": entity_code, "department_id": did, "active": True},
            {"_id": 0, "id": 1},
        )
        cid = cc.get("id") if cc else None
    if not cid:
        cc = await db.master_cost_centers.find_one(
            {"entity_code": entity_code, "active": True},
            {"_id": 0, "id": 1},
        )
        cid = cc.get("id") if cc else None
    return did, cid


async def backfill_transaction_org_fields(
    db,
    *,
    collections: Optional[List[str]] = None,
    limit_entities: int = 250,
) -> Dict[str, Any]:
    """Backfill dept/cost_center on known collections.

    We set a *default* department + cost center per entity for demo data.
    """
    cols = collections or ["invoices", "ar_invoices", "journals", "bank_transactions", "capex_projects"]
    entities = [e async for e in db.entities.find({}, {"_id": 0, "code": 1}).limit(limit_entities)]
    updated: Dict[str, int] = {c: 0 for c in cols}
    scanned_entities = 0

    for e in entities:
        ent = e.get("code")
        if not ent:
            continue
        scanned_entities += 1
        did, cid = await _dept_cc_for_entity(db, ent)
        if not did and not cid:
            continue
        patch: Dict[str, Any] = {}
        if did:
            patch["department_id"] = did
        if cid:
            patch["cost_center_id"] = cid
        if not patch:
            continue

        q = {"entity": ent, "$or": [{"$and": [_blank("department_id")]}, {"$and": [_blank("cost_center_id")]}]}
        for coll in cols:
            try:
                res = await db[coll].update_many(q, {"$set": patch})
                updated[coll] += int(getattr(res, "modified_count", 0) or 0)
            except Exception:
                # collection may not exist in some environments
                continue

    return {"entities_scanned": scanned_entities, "updated": updated, "collections": cols}

