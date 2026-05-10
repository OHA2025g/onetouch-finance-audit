"""Phase 30 — Delegation of Authority (DoA) Engine (seed-friendly)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.deps import audit_log, db
from app.services.kpi_service import as_of_now
from app.services.rbac_service import enforce_entity_scope


router = APIRouter(prefix="/doa", tags=["doa"])


async def _ensure_seed_doa(entity_code: Optional[str] = None) -> Dict[str, int]:
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code

    out = {"doa_matrix": 0, "doa_rules": 0}

    if await db.doa_matrix.count_documents(q) == 0:
        # Simple tiered limits by category + role (approver).
        rows = []
        categories = ["capex", "opex", "vendor_onboarding", "payment", "discount", "writeoff"]
        roles = ["manager", "controller", "cfo", "board"]
        # Increasing ceilings per role.
        ceilings = {"manager": 50_000, "controller": 250_000, "cfo": 2_000_000, "board": 10_000_000}
        for c in categories:
            for r in roles:
                rows.append(
                    {
                        "id": f"DOA-{c}-{r}",
                        "entity": entity_code or "US-HQ",
                        "category": c,
                        "approver_role": r,
                        "max_amount": float(ceilings[r] * (1.0 if c != "capex" else 1.5)),
                        "currency": "INR",
                        "effective_from": datetime.now(timezone.utc).date().isoformat(),
                        "version": 1,
                        "active": True,
                        "created_at": as_of_now(),
                        "created_by": "controller@onetouch.ai",
                    }
                )
        await db.doa_matrix.insert_many(rows)
        out["doa_matrix"] = len(rows)

    if await db.doa_rules.count_documents(q) == 0:
        # Rules are a higher-level wrapper over matrix rows.
        rules = [
            {
                "id": "DOA-R-001",
                "entity": entity_code or "US-HQ",
                "name": "Capex approval limits",
                "category": "capex",
                "currency": "INR",
                "active": True,
                "created_at": as_of_now(),
                "created_by": "controller@onetouch.ai",
            },
            {
                "id": "DOA-R-002",
                "entity": entity_code or "US-HQ",
                "name": "Payments approval limits",
                "category": "payment",
                "currency": "INR",
                "active": True,
                "created_at": as_of_now(),
                "created_by": "controller@onetouch.ai",
            },
        ]
        await db.doa_rules.insert_many(rules)
        out["doa_rules"] = len(rules)

    return out


@router.get("/matrix")
async def doa_matrix(entity_code: Optional[str] = Query(None), category: Optional[str] = Query(None), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_doa(entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    if category:
        q["category"] = category
    cur = db.doa_matrix.find(q, {"_id": 0}).sort([("category", 1), ("max_amount", 1)]).limit(5000)
    items = [x async for x in cur]
    return {"items": items, "count": len(items), "as_of": as_of_now(), "entity_code": entity_code}


@router.post("/matrix")
async def doa_matrix_create(body: Dict[str, Any], current=Depends(get_current_user)):
    mid = f"DOA-{__import__('uuid').uuid4().hex[:10]}"
    ent = await enforce_entity_scope(
        db, current=current, requested_entity_code=(body.get("entity") or body.get("entity_code"))
    )
    doc = {
        "id": mid,
        "entity": ent or body.get("entity") or "US-HQ",
        "category": body.get("category") or "opex",
        "approver_role": body.get("approver_role") or "controller",
        "max_amount": float(body.get("max_amount") or 0.0),
        "currency": body.get("currency") or "INR",
        "effective_from": body.get("effective_from") or datetime.now(timezone.utc).date().isoformat(),
        "version": int(body.get("version") or 1),
        "active": bool(body.get("active", True)),
        "created_at": as_of_now(),
        "created_by": current.get("email"),
    }
    await db.doa_matrix.insert_one(dict(doc))
    await audit_log(current["email"], "doa_matrix_create", "doa_matrix", mid, {"category": doc["category"], "role": doc["approver_role"]})
    return {"status": "ok", "matrix_id": mid, "as_of": as_of_now()}


@router.get("/rules")
async def doa_rules(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_doa(entity_code=entity_code)
    q: Dict[str, Any] = {"entity": entity_code} if entity_code else {}
    cur = db.doa_rules.find(q, {"_id": 0}).sort("id", 1).limit(5000)
    items = [x async for x in cur]
    return {"items": items, "count": len(items), "as_of": as_of_now()}


@router.post("/rules")
async def doa_rules_create(body: Dict[str, Any], current=Depends(get_current_user)):
    rid = f"DOA-R-{__import__('uuid').uuid4().hex[:8]}"
    ent = await enforce_entity_scope(
        db, current=current, requested_entity_code=(body.get("entity") or body.get("entity_code"))
    )
    doc = {
        "id": rid,
        "entity": ent or body.get("entity") or "US-HQ",
        "name": body.get("name") or "DoA rule",
        "category": body.get("category") or "opex",
        "currency": body.get("currency") or "INR",
        "active": bool(body.get("active", True)),
        "created_at": as_of_now(),
        "created_by": current.get("email"),
    }
    await db.doa_rules.insert_one(dict(doc))
    await audit_log(current["email"], "doa_rule_create", "doa_rule", rid, {"category": doc["category"]})
    return {"status": "ok", "rule_id": rid, "as_of": as_of_now()}


async def _resolve_limit(entity: str, category: str) -> float:
    # Lowest role limit is the minimum; for validation we care about whether ANY limit exists.
    row = await db.doa_matrix.find_one({"entity": entity, "category": category, "active": True}, {"_id": 0}, sort=[("max_amount", -1)])
    if not row:
        return 0.0
    return float(row.get("max_amount") or 0.0)


@router.post("/validate-transaction")
async def doa_validate_transaction(body: Dict[str, Any], current=Depends(get_current_user)):
    """Validate a transaction against the DoA matrix; creates a breach when exceeded."""
    entity = await enforce_entity_scope(
        db, current=current, requested_entity_code=(body.get("entity") or body.get("entity_code"))
    )
    if not entity:
        entity = str(body.get("entity") or body.get("entity_code") or current.get("entity") or "US-HQ")
    category = body.get("category") or "opex"
    currency = body.get("currency") or "INR"
    amount = float(body.get("amount") or 0.0)
    txn_id = body.get("transaction_id") or f"TXN-{__import__('uuid').uuid4().hex[:10]}"

    await _ensure_seed_doa(entity_code=entity)
    limit = await _resolve_limit(entity, category)

    ok = amount <= limit if limit > 0 else False
    required_role = "unknown"
    # Pick smallest role that can approve (first ceiling >= amount).
    matrix = [m async for m in db.doa_matrix.find({"entity": entity, "category": category, "active": True}, {"_id": 0})]
    matrix.sort(key=lambda x: float(x.get("max_amount") or 0.0))
    for m in matrix:
        if amount <= float(m.get("max_amount") or 0.0):
            required_role = str(m.get("approver_role") or "unknown")
            break
    if required_role == "unknown" and matrix:
        required_role = str(matrix[-1].get("approver_role") or "unknown")

    result = {"transaction_id": txn_id, "entity": entity, "category": category, "currency": currency, "amount": amount, "limit": limit, "required_approver_role": required_role, "is_authorized": ok}

    if not ok:
        bid = f"DOA-BREACH-{__import__('uuid').uuid4().hex[:10]}"
        breach = {
            "id": bid,
            "entity": entity,
            "transaction_id": txn_id,
            "category": category,
            "currency": currency,
            "amount": amount,
            "limit": limit,
            "required_approver_role": required_role,
            "status": "open",
            "detected_at": as_of_now(),
            "created_at": as_of_now(),
            "created_by": current.get("email"),
            "exception_approval": None,
        }
        await db.doa_breaches.insert_one(dict(breach))
        await audit_log(current["email"], "doa_breach_detected", "doa_breach", bid, {"transaction_id": txn_id, "category": category, "amount": amount, "limit": limit})
        return {"as_of": as_of_now(), "result": result, "breach_created": True, "breach_id": bid}

    await audit_log(current["email"], "doa_validate_transaction", "doa_validation", txn_id, {"category": category, "amount": amount, "limit": limit})
    return {"as_of": as_of_now(), "result": result, "breach_created": False}


@router.get("/breaches")
async def doa_breaches(entity_code: Optional[str] = Query(None), status: Optional[str] = Query(None), limit: int = Query(200, ge=1, le=5000), offset: int = Query(0, ge=0), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_doa(entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    if status:
        q["status"] = status
    cur = db.doa_breaches.find(q, {"_id": 0}).sort("detected_at", -1).skip(offset).limit(limit)
    items = [x async for x in cur]
    total = await db.doa_breaches.count_documents(q)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": as_of_now()}


@router.post("/breaches/{breach_id}/exception-approval")
async def doa_exception_approval(breach_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    br = await db.doa_breaches.find_one({"id": breach_id}, {"_id": 0, "entity": 1})
    if br and br.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=br.get("entity"))
    decision = str(body.get("decision") or body.get("status") or "approved")
    if decision not in {"approved", "rejected"}:
        raise HTTPException(400, "Invalid decision")
    approval = {
        "decision": decision,
        "by": current.get("email"),
        "at": as_of_now(),
        "note": body.get("note"),
    }
    new_status = "closed" if decision == "approved" else "open"
    res = await db.doa_breaches.update_one({"id": breach_id}, {"$set": {"exception_approval": approval, "status": new_status, "updated_at": as_of_now()}})
    if res.matched_count == 0:
        raise HTTPException(404, "Breach not found")
    await audit_log(current["email"], "doa_exception_approval", "doa_breach", breach_id, {"decision": decision})
    return {"status": "ok", "as_of": as_of_now(), "matched": res.matched_count, "modified": res.modified_count}

