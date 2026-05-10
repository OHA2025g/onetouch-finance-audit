"""Entity scope enforcement when ``system_security_config.config.rbac.entity_scope_enforced`` is true."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException

from app.services.rbac_service import role_bypasses_entity_scope


async def _security_config(db) -> Dict[str, Any]:
    doc = await db.system_security_config.find_one({"id": "singleton"}, {"_id": 0})
    return (doc or {}).get("config") or {}


async def entity_scope_enforced(db) -> bool:
    cfg = await _security_config(db)
    rbac = cfg.get("rbac") or {}
    return bool(rbac.get("entity_scope_enforced"))


async def resolve_entity_code_for_query(
    db,
    current: Dict[str, Any],
    requested: Optional[str],
) -> Optional[str]:
    """Return the entity code to apply to list queries.

    .. deprecated::
        Prefer ``app.services.rbac_service.enforce_entity_scope`` for one consistent
        implementation (uses ``users.id`` / ``user_id`` and matches Phase 40 RBAC).

    When enforcement is off, returns ``requested`` unchanged (may be ``None``).
    When on, non-``Super Admin`` users are limited to their profile ``entity``;
    requesting a different entity returns 403.
    """
    if not await entity_scope_enforced(db):
        return requested
    if role_bypasses_entity_scope(current):
        return requested
    prof = await db.users.find_one({"email": current["email"]}, {"_id": 0, "entity": 1})
    user_ent = (prof or {}).get("entity")
    if requested and user_ent and requested != user_ent:
        raise HTTPException(403, "Entity scope: cannot query outside assigned entity")
    return user_ent or requested
