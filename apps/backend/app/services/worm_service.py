"""WORM-style immutability for closed cases and evidence anchors."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException

from app.utils.timeutil import iso_utc

WORM_OVERRIDE_ROLES = ("CFO", "Internal Auditor", "Controller", "Compliance Head")

REF_CASE = "case"
REF_EVIDENCE = "evidence"


async def is_worm_locked(db, ref_type: str, ref_id: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    rec = await db.worm_protected_records.find_one(
        {"ref_type": ref_type, "ref_id": ref_id, "active": True}, {"_id": 0}
    )
    if rec:
        return True, rec
    if ref_type == REF_CASE:
        c = await db.cases.find_one({"id": ref_id}, {"_id": 0, "status": 1})
        if c and c.get("status") == "closed":
            return True, None
    return False, None


async def lock_case_on_close(db, case_id: str, actor: str) -> None:
    now = iso_utc(datetime.now(timezone.utc))
    await db.worm_protected_records.update_one(
        {"ref_type": REF_CASE, "ref_id": case_id},
        {
            "$set": {
                "id": f"worm-{case_id[:12]}",
                "ref_type": REF_CASE, "ref_id": case_id, "locked_at": now, "locked_by": actor,
                "reason": "Case closed — WORM", "active": True,
                "override_roles": list(WORM_OVERRIDE_ROLES),
            }
        },
        upsert=True,
    )
    c = await db.cases.find_one({"id": case_id}, {"_id": 0, "exception_id": 1})
    if c and c.get("exception_id"):
        await lock_exception_evidence(db, c["exception_id"], actor)


async def lock_exception_evidence(db, exception_id: str, actor: str) -> None:
    now = iso_utc(datetime.now(timezone.utc))
    await db.worm_protected_records.update_one(
        {"ref_type": REF_EVIDENCE, "ref_id": exception_id},
        {
            "$set": {
                "id": f"worm-ex-{exception_id[:12]}", "ref_type": REF_EVIDENCE, "ref_id": exception_id,
                "locked_at": now, "locked_by": actor, "reason": "Linked case closed", "active": True,
                "override_roles": list(WORM_OVERRIDE_ROLES),
            }
        },
        upsert=True,
    )


async def require_case_mutable(
    db,
    case: Dict[str, Any],
    user: Dict[str, Any],
    force_override: bool = False,
) -> None:
    if case.get("status") != "closed":
        return
    locked, rec = await is_worm_locked(db, REF_CASE, case["id"])
    if not locked and case.get("status") == "closed":
        locked = True
    if not locked:
        return
    ovr = set((rec or {}).get("override_roles") or WORM_OVERRIDE_ROLES)
    if force_override and user.get("role") in ovr:
        from app.deps import audit_log

        await audit_log(
            user.get("email", "unknown"), "worm_override", "case", case["id"],
            {"governance": "mutation_allowed", "force": True},
        )
        return
    raise HTTPException(
        status_code=409,
        detail="Case is closed and WORM-locked. Pass ?force_override=true if your role is permitted.",
    )
