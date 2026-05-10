"""Phase 32 — User Access & SoD certification (seed-friendly)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.deps import audit_log, db
from app.services.kpi_service import as_of_now
from app.services.rbac_service import enforce_entity_scope


router = APIRouter(prefix="/access", tags=["access"])


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


async def _ensure_seed_access(entity_code: Optional[str] = None) -> Dict[str, int]:
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code

    out = {"access_users": 0, "access_roles": 0, "sod_rules": 0, "access_events": 0}
    now = datetime.now(timezone.utc)

    if await db.access_roles.count_documents({}) == 0:
        roles = [
            {"id": "ROLE-AP-CLERK", "name": "AP Clerk", "permissions": ["ap:create_invoice", "ap:edit_vendor"]},
            {"id": "ROLE-AP-APPROVER", "name": "AP Approver", "permissions": ["ap:approve_payment", "ap:release_hold"]},
            {"id": "ROLE-GL-POSTER", "name": "GL Poster", "permissions": ["gl:post_journal", "gl:edit_journal"]},
            {"id": "ROLE-GL-APPROVER", "name": "GL Approver", "permissions": ["gl:approve_journal"]},
            {"id": "ROLE-ADMIN", "name": "System Admin", "permissions": ["system:admin", "access:manage"]},
        ]
        await db.access_roles.insert_many([{**r, "created_at": as_of_now()} for r in roles])
        out["access_roles"] = len(roles)

    if await db.access_users.count_documents(q) == 0:
        users = [
            {"id": "U-1001", "email": "cfo@onetouch.ai", "name": "CFO", "entity": entity_code or "US-HQ", "active": True, "last_login_at": (now - timedelta(days=2)).isoformat(), "roles": ["ROLE-GL-APPROVER"]},
            {"id": "U-1002", "email": "controller@onetouch.ai", "name": "Controller", "entity": entity_code or "US-HQ", "active": True, "last_login_at": (now - timedelta(days=5)).isoformat(), "roles": ["ROLE-AP-APPROVER", "ROLE-GL-POSTER"]},
            {"id": "U-1003", "email": "apclerk@onetouch.ai", "name": "AP Clerk", "entity": entity_code or "US-HQ", "active": True, "last_login_at": (now - timedelta(days=60)).isoformat(), "roles": ["ROLE-AP-CLERK", "ROLE-AP-APPROVER"]},  # deliberate SoD issue
            {"id": "U-1004", "email": "sysadmin@onetouch.ai", "name": "SysAdmin", "entity": entity_code or "US-HQ", "active": True, "last_login_at": (now - timedelta(days=1)).isoformat(), "roles": ["ROLE-ADMIN"]},
            {"id": "U-1005", "email": "glposter@onetouch.ai", "name": "GL Poster", "entity": entity_code or "US-HQ", "active": True, "last_login_at": (now - timedelta(days=190)).isoformat(), "roles": ["ROLE-GL-POSTER"]},
        ]
        await db.access_users.insert_many([{**u, "created_at": as_of_now(), "created_by": "system"} for u in users])
        out["access_users"] = len(users)

    if await db.sod_rules.count_documents({}) == 0:
        rules = [
            {"id": "SOD-001", "name": "No AP create + approve", "conflicting_roles": ["ROLE-AP-CLERK", "ROLE-AP-APPROVER"], "severity": "high"},
            {"id": "SOD-002", "name": "No GL post + approve", "conflicting_roles": ["ROLE-GL-POSTER", "ROLE-GL-APPROVER"], "severity": "high"},
            {"id": "SOD-003", "name": "No admin + posting", "conflicting_roles": ["ROLE-ADMIN", "ROLE-GL-POSTER"], "severity": "medium"},
        ]
        await db.sod_rules.insert_many([{**r, "created_at": as_of_now(), "created_by": "compliance@onetouch.ai"} for r in rules])
        out["sod_rules"] = len(rules)

    if await db.user_access_events.count_documents(q) == 0:
        # Minimal activity events for dormant user detection.
        users = [u async for u in db.access_users.find(q, {"_id": 0, "id": 1, "email": 1, "entity": 1}).limit(100)]
        evs = []
        for i, u in enumerate(users):
            # Spread activity; some users intentionally stale.
            days = 10 if i % 2 == 0 else 120
            evs.append({"id": f"ACE-{u['id']}", "entity": u.get("entity"), "user_id": u["id"], "user_email": u["email"], "event_type": "login", "at": (now - timedelta(days=days)).isoformat()})
        await db.user_access_events.insert_many(evs)
        out["access_events"] = len(evs)

    return out


def _has_all(roles: Set[str], required: List[str]) -> bool:
    return all(r in roles for r in required)


async def _compute_sod_conflicts(entity_code: Optional[str] = None) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"entity": entity_code} if entity_code else {}
    users = [u async for u in db.access_users.find(q, {"_id": 0}).limit(2000)]
    rules = [r async for r in db.sod_rules.find({}, {"_id": 0}).limit(5000)]
    out = []
    for u in users:
        rset = set(u.get("roles") or [])
        for rule in rules:
            conf = rule.get("conflicting_roles") or []
            if len(conf) >= 2 and _has_all(rset, conf[:2]):
                out.append(
                    {
                        "id": f"CONFLICT-{rule['id']}-{u['id']}",
                        "entity": u.get("entity"),
                        "user_id": u.get("id"),
                        "user_email": u.get("email"),
                        "rule_id": rule.get("id"),
                        "rule_name": rule.get("name"),
                        "severity": rule.get("severity"),
                        "conflicting_roles": conf,
                        "detected_at": as_of_now(),
                        "status": "open",
                    }
                )
    return out


@router.get("/users")
async def access_users(entity_code: Optional[str] = Query(None), q: Optional[str] = Query(None), limit: int = Query(200, ge=1, le=5000), offset: int = Query(0, ge=0), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_access(entity_code=entity_code)
    filt: Dict[str, Any] = {}
    if entity_code:
        filt["entity"] = entity_code
    if q and q.strip():
        rq = {"$regex": q.strip(), "$options": "i"}
        filt["$or"] = [{"email": rq}, {"name": rq}, {"id": rq}]
    cur = db.access_users.find(filt, {"_id": 0}).sort("email", 1).skip(offset).limit(limit)
    items = [x async for x in cur]
    total = await db.access_users.count_documents(filt)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": as_of_now()}


@router.get("/roles")
async def access_roles(current=Depends(get_current_user)):
    await _ensure_seed_access(entity_code=None)
    items = [x async for x in db.access_roles.find({}, {"_id": 0}).sort("name", 1).limit(5000)]
    return {"items": items, "count": len(items), "as_of": as_of_now()}


@router.get("/sod-rules")
async def access_sod_rules(current=Depends(get_current_user)):
    await _ensure_seed_access(entity_code=None)
    items = [x async for x in db.sod_rules.find({}, {"_id": 0}).sort("id", 1).limit(5000)]
    return {"items": items, "count": len(items), "as_of": as_of_now()}


@router.post("/sod-rules")
async def access_sod_rule_create(body: Dict[str, Any], current=Depends(get_current_user)):
    rid = f"SOD-{__import__('uuid').uuid4().hex[:8]}"
    doc = {
        "id": rid,
        "name": body.get("name") or "SoD rule",
        "conflicting_roles": body.get("conflicting_roles") or [],
        "severity": body.get("severity") or "medium",
        "created_at": as_of_now(),
        "created_by": current.get("email"),
        "active": bool(body.get("active", True)),
    }
    await db.sod_rules.insert_one(dict(doc))
    await audit_log(current["email"], "sod_rule_create", "sod_rule", rid, {"severity": doc["severity"]})
    return {"status": "ok", "rule_id": rid, "as_of": as_of_now()}


@router.get("/sod-conflicts")
async def access_sod_conflicts(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_access(entity_code=entity_code)
    items = await _compute_sod_conflicts(entity_code=entity_code)
    return {"items": items, "count": len(items), "as_of": as_of_now(), "entity_code": entity_code}


@router.get("/dormant-users")
async def access_dormant_users(entity_code: Optional[str] = Query(None), dormant_days: int = Query(90, ge=1, le=3650), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_access(entity_code=entity_code)
    q: Dict[str, Any] = {"entity": entity_code} if entity_code else {}
    now = datetime.now(timezone.utc)
    users = [u async for u in db.access_users.find(q, {"_id": 0}).limit(5000)]
    dormant = []
    for u in users:
        last = u.get("last_login_at")
        dt = None
        try:
            dt = datetime.fromisoformat(str(last).replace("Z", "+00:00")) if last else None
        except Exception:  # noqa: BLE001
            dt = None
        if not dt or (now - dt).days >= dormant_days:
            dormant.append({**u, "dormant_days": (now - dt).days if dt else None})
    dormant.sort(key=lambda x: -(int(x.get("dormant_days") or 999999)))
    return {"items": dormant, "count": len(dormant), "as_of": as_of_now(), "entity_code": entity_code, "dormant_days": dormant_days}


@router.get("/privileged-users")
async def access_privileged_users(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_access(entity_code=entity_code)
    q: Dict[str, Any] = {"entity": entity_code} if entity_code else {}
    users = [u async for u in db.access_users.find(q, {"_id": 0}).limit(5000)]
    privileged = [u for u in users if "ROLE-ADMIN" in (u.get("roles") or [])]
    return {"items": privileged, "count": len(privileged), "as_of": as_of_now(), "entity_code": entity_code}


@router.post("/certification-campaign")
async def access_certification_campaign(body: Dict[str, Any], current=Depends(get_current_user)):
    entity = await enforce_entity_scope(
        db,
        current=current,
        requested_entity_code=(body.get("entity") or body.get("entity_code")),
    )
    if not entity:
        entity = str(body.get("entity") or body.get("entity_code") or "US-HQ")
    await _ensure_seed_access(entity_code=entity)
    cid = f"CERT-{__import__('uuid').uuid4().hex[:10]}"
    due_date = body.get("due_date") or (datetime.now(timezone.utc) + timedelta(days=14)).date().isoformat()
    campaign = {"id": cid, "entity": entity, "scope": body.get("scope") or "all_users", "status": "active", "due_date": due_date, "created_at": as_of_now(), "created_by": current.get("email")}
    await db.access_certification_campaigns.insert_one(dict(campaign))

    # Seed certification items: one per user.
    users = [u async for u in db.access_users.find({"entity": entity}, {"_id": 0}).limit(5000)]
    seeded = 0
    for u in users:
        iid = f"CERTITEM-{cid}-{u['id']}"
        doc = {
            "id": iid,
            "campaign_id": cid,
            "entity": entity,
            "user_id": u["id"],
            "user_email": u.get("email"),
            "current_roles": u.get("roles") or [],
            "decision": None,
            "decision_by": None,
            "decision_at": None,
            "status": "pending",
            "created_at": as_of_now(),
        }
        await db.access_certification_items.update_one({"id": iid}, {"$setOnInsert": doc}, upsert=True)
        seeded += 1

    await audit_log(current["email"], "access_cert_campaign_create", "access_cert_campaign", cid, {"items_seeded": seeded, "entity": entity})
    return {"status": "ok", "campaign_id": cid, "items_seeded": seeded, "as_of": as_of_now()}


@router.post("/certification-item/{item_id}/decision")
async def access_certification_item_decision(item_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    row = await db.access_certification_items.find_one({"id": item_id}, {"_id": 0, "entity": 1})
    if row and row.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=row.get("entity"))
    decision = str(body.get("decision") or "")
    if decision not in {"approve", "revoke", "modify"}:
        raise HTTPException(400, "Invalid decision (approve|revoke|modify)")
    update = {
        "decision": decision,
        "decision_by": current.get("email"),
        "decision_at": as_of_now(),
        "status": "completed",
        "note": body.get("note"),
        "proposed_roles": body.get("proposed_roles"),
        "updated_at": as_of_now(),
    }
    res = await db.access_certification_items.update_one({"id": item_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Certification item not found")
    await audit_log(current["email"], "access_cert_item_decision", "access_cert_item", item_id, {"decision": decision})
    return {"status": "ok", "matched": res.matched_count, "modified": res.modified_count, "as_of": as_of_now()}

