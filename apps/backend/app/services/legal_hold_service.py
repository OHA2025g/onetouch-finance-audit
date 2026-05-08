"""Legal hold creation, linking, and eligibility checks (blocks purge / delete)."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.utils.timeutil import iso_utc


async def is_held(db, artifact_type: str, artifact_id: str) -> bool:
    async for link in db.hold_artifact_links.find(
        {"artifact_type": artifact_type, "artifact_id": artifact_id}, {"_id": 0, "hold_id": 1}
    ):
        h = await db.legal_holds.find_one({"id": link.get("hold_id")}, {"_id": 0, "status": 1})
        if h and h.get("status") == "active":
            return True
    if artifact_type == "case":
        c = await db.cases.find_one({"id": artifact_id}, {"_id": 0, "entity": 1})
        if c and c.get("entity") and await db.legal_holds.find_one(
            {"status": "active", "scope": "entity", "entity_code": c["entity"]}
        ):
            return True
    if await db.legal_holds.find_one({"status": "active", "scope": "global"}):
        return True
    return False


async def governance_flags_for_case(db, case_id: str) -> Dict[str, Any]:
    c = await db.cases.find_one({"id": case_id}, {"_id": 0, "id": 1, "status": 1, "entity": 1, "exception_id": 1})
    if not c:
        return {"legal_hold": False, "worm": False, "holds": []}
    holds: List[Dict[str, Any]] = []
    async for link in db.hold_artifact_links.find(
        {"artifact_type": "case", "artifact_id": case_id}, {"_id": 0}
    ):
        hd = await db.legal_holds.find_one({"id": link.get("hold_id")}, {"_id": 0})
        if hd and hd.get("status") == "active":
            holds.append(hd)
    on_hold = bool(holds) or await is_held(db, "case", case_id)
    if c.get("exception_id"):
        on_hold = on_hold or await is_held(db, "evidence", c["exception_id"])
    from app.services import worm_service as ws

    worm, _ = await ws.is_worm_locked(db, ws.REF_CASE, case_id)
    if not worm and c.get("status") == "closed":
        worm = True
    return {"legal_hold": on_hold, "worm": worm, "holds": holds}


async def list_holds(db, status: Optional[str] = "active", limit: int = 200) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    return [h async for h in db.legal_holds.find(q, {"_id": 0}).sort("created_at", -1).limit(limit)]


async def create_hold(
    db,
    *,
    name: str,
    scope: str,
    reason: str,
    created_by: str,
    entity_code: Optional[str] = None,
) -> Dict[str, Any]:
    now = iso_utc(datetime.now(timezone.utc))
    doc = {
        "id": f"hold-{uuid.uuid4().hex[:10]}",
        "name": name, "status": "active", "scope": scope, "reason": reason, "entity_code": entity_code,
        "created_by": created_by, "created_at": now, "released_at": None, "release_reason": None,
    }
    await db.legal_holds.insert_one(dict(doc))
    return doc


async def release_hold(
    db, hold_id: str, user: str, reason: str,
) -> Dict[str, Any]:
    now = iso_utc(datetime.now(timezone.utc))
    r = await db.legal_holds.update_one(
        {"id": hold_id, "status": "active"},
        {"$set": {"status": "released", "released_at": now, "release_reason": reason, "released_by": user}},
    )
    if r.matched_count == 0:
        from fastapi import HTTPException
        raise HTTPException(404, "Hold not found or already released")
    return (await db.legal_holds.find_one({"id": hold_id}, {"_id": 0}))  # type: ignore[return-value]


async def attach_artifacts(
    db, hold_id: str, artifacts: List[Dict[str, str]], user: str,
) -> int:
    hold = await db.legal_holds.find_one({"id": hold_id, "status": "active"}, {"_id": 0, "id": 1})
    if not hold:
        from fastapi import HTTPException
        raise HTTPException(404, "Active hold not found")
    n = 0
    for a in artifacts:
        await db.hold_artifact_links.update_one(
            {"hold_id": hold_id, "artifact_type": a["type"], "artifact_id": a["id"]},
            {
                "$set": {
                    "id": f"hal-{uuid.uuid4().hex[:8]}",
                    "hold_id": hold_id, "artifact_type": a["type"], "artifact_id": a["id"],
                    "attached_by": user, "attached_at": iso_utc(datetime.now(timezone.utc)),
                }
            },
            upsert=True,
        )
        n += 1
    return n
