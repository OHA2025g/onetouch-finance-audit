"""Phase 40 — RBAC helpers (entity scope enforcement)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Optional

from fastapi import HTTPException

_ENTITY_SCOPE_UNRESTRICTED_ROLES = frozenset({"Super Admin", "CFO"})


def role_bypasses_entity_scope(current: dict) -> bool:
    """Roles that may pass any ``entity_code`` (or none for consolidated dashboards) when RBAC entity scope is on."""
    role = str(current.get("role") or "").strip()
    return role in _ENTITY_SCOPE_UNRESTRICTED_ROLES


async def enforce_entity_scope(db, *, current: dict, requested_entity_code: Optional[str]) -> Optional[str]:
    """If system security config enables entity scoping, enforce user's entity.

    Behavior:
    - When disabled: return requested_entity_code unchanged.
    - When enabled:
      - Super Admin and CFO bypass (group-wide finance visibility).
      - If the user has an entity assigned:
        - If caller provided a different entity_code → 403.
        - Otherwise force entity_code to user's entity.
    """
    try:
        sec = await db.system_security_config.find_one({"id": "singleton"}, {"_id": 0})
        enabled = bool(((sec or {}).get("config") or {}).get("rbac", {}).get("entity_scope_enforced"))
    except Exception:
        enabled = False
    if not enabled:
        return requested_entity_code

    if role_bypasses_entity_scope(current):
        return requested_entity_code

    user = await db.users.find_one({"id": current.get("user_id")}, {"_id": 0, "entity": 1})
    ent = (user or {}).get("entity")
    if not ent:
        return requested_entity_code

    if requested_entity_code and str(requested_entity_code).strip() and requested_entity_code != ent:
        raise HTTPException(403, "Entity scope violation")
    return ent


async def assert_engagement_entity_scope(db, *, current: dict, engagement: dict) -> None:
    """When entity RBAC scope is on, deny CA audit routes for engagements outside the user's ``users.entity``.

    Engagements carry ``entity_code`` (legal entity key); legacy documents without it are denied when the user
    has a scoped entity so we do not leak cross-tenant CA data.
    """
    try:
        sec = await db.system_security_config.find_one({"id": "singleton"}, {"_id": 0})
        enabled = bool(((sec or {}).get("config") or {}).get("rbac", {}).get("entity_scope_enforced"))
    except Exception:  # noqa: BLE001
        enabled = False
    # Engagement documents stay tied to ``users.entity`` even when CFO has group-wide dashboard reads.
    if not enabled or current.get("role") == "Super Admin":
        return
    user = await db.users.find_one({"id": current.get("user_id")}, {"_id": 0, "entity": 1})
    ue = (user or {}).get("entity")
    if not ue:
        return
    ec = engagement.get("entity_code")
    if not ec or str(ec).strip() != str(ue).strip():
        raise HTTPException(403, "Entity scope violation")


async def assert_close_cycle_entity_scope(db, *, current: dict, cycle: dict) -> None:
    """Deny close-cycle reads/writes outside the user's legal entity when RBAC entity scope is on."""
    try:
        sec = await db.system_security_config.find_one({"id": "singleton"}, {"_id": 0})
        enabled = bool(((sec or {}).get("config") or {}).get("rbac", {}).get("entity_scope_enforced"))
    except Exception:  # noqa: BLE001
        enabled = False
    if not enabled or role_bypasses_entity_scope(current):
        return
    user = await db.users.find_one({"id": current.get("user_id")}, {"_id": 0, "entity": 1})
    ue = (user or {}).get("entity")
    if not ue:
        return
    ec = cycle.get("entity_code")
    if not ec or str(ec).strip() != str(ue).strip():
        raise HTTPException(403, "Entity scope violation")


async def assert_connector_entity_scope(db, *, current: dict, connector: dict) -> None:
    """Deny connector operations when ``config.entity_code`` is outside the user's entity (scope on)."""
    try:
        sec = await db.system_security_config.find_one({"id": "singleton"}, {"_id": 0})
        enabled = bool(((sec or {}).get("config") or {}).get("rbac", {}).get("entity_scope_enforced"))
    except Exception:  # noqa: BLE001
        enabled = False
    if not enabled or role_bypasses_entity_scope(current):
        return
    user = await db.users.find_one({"id": current.get("user_id")}, {"_id": 0, "entity": 1})
    ue = (user or {}).get("entity")
    if not ue:
        return
    cfg = connector.get("config") if isinstance(connector.get("config"), dict) else {}
    ec = cfg.get("entity_code")
    if not ec or str(ec).strip() != str(ue).strip():
        raise HTTPException(403, "Entity scope violation")


async def assert_approval_request_entity_scope(db, *, current: dict, request: dict) -> None:
    """Deny governance approve/reject (and similar) when the approval was raised for another legal entity."""
    try:
        sec = await db.system_security_config.find_one({"id": "singleton"}, {"_id": 0})
        enabled = bool(((sec or {}).get("config") or {}).get("rbac", {}).get("entity_scope_enforced"))
    except Exception:  # noqa: BLE001
        enabled = False
    if not enabled or role_bypasses_entity_scope(current):
        return
    user = await db.users.find_one({"id": current.get("user_id")}, {"_id": 0, "entity": 1})
    ue = (user or {}).get("entity")
    if not ue:
        return
    ec = request.get("entity_code")
    if not ec or str(ec).strip() != str(ue).strip():
        raise HTTPException(403, "Entity scope violation")


def _record_entity_code(rec: Optional[Dict[str, Any]]) -> Optional[str]:
    if not rec or not isinstance(rec, dict):
        return None
    ec = rec.get("entity_code") or rec.get("entity")
    if ec is None:
        return None
    s = str(ec).strip()
    return s or None


async def enforce_drill_entity_scope(db, *, current: dict, result: Dict[str, Any]) -> None:
    """When entity RBAC scope is on, deny drill reads outside the user's entity or narrow shared types (e.g. control).

    Mutates ``result`` in place for ``type == \"control\"`` (filters exceptions/cases/stats). For other drill types,
    raises ``HTTPException(403)`` if the primary record is tied to another legal entity.
    """
    try:
        sec = await db.system_security_config.find_one({"id": "singleton"}, {"_id": 0})
        enabled = bool(((sec or {}).get("config") or {}).get("rbac", {}).get("entity_scope_enforced"))
    except Exception:  # noqa: BLE001
        enabled = False
    if not enabled or role_bypasses_entity_scope(current):
        return
    user = await db.users.find_one({"id": current.get("user_id")}, {"_id": 0, "entity": 1})
    ue = (user or {}).get("entity")
    if not ue:
        return
    ue_s = str(ue).strip()
    if result.get("error"):
        return
    dtype = str(result.get("type") or "").strip().lower()
    if dtype == "control":
        exs = list(result.get("exceptions") or [])
        filtered = [e for e in exs if _record_entity_code(e) == ue_s]
        ex_ids = {e.get("id") for e in filtered if e.get("id")}
        cases_in = list(result.get("cases") or [])
        cases_out = [c for c in cases_in if c.get("exception_id") in ex_ids]
        exposure_total = sum(float(e.get("financial_exposure") or 0) for e in filtered)
        by_entity: Dict[str, int] = defaultdict(int)
        for e in filtered:
            ent = str(e.get("entity") or "").strip() or "unknown"
            by_entity[ent] += 1
        open_cases = len([ca for ca in cases_out if (ca.get("status") or "").lower() != "closed"])
        stats = dict(result.get("stats") or {})
        stats["exception_count"] = len(filtered)
        stats["total_exposure"] = round(exposure_total, 2)
        stats["open_cases"] = open_cases
        stats["by_entity"] = dict(by_entity)
        result["exceptions"] = filtered
        result["cases"] = cases_out
        result["stats"] = stats
        return
    primary = result.get("primary")
    pe = _record_entity_code(primary if isinstance(primary, dict) else None)
    if not pe:
        raise HTTPException(403, "Entity scope violation")
    if pe != ue_s:
        raise HTTPException(403, "Entity scope violation")


async def assert_exception_entity_scope(db, *, current: dict, exception: dict) -> None:
    """Deny evidence / drill paths when ``exceptions.entity`` is outside the user's entity (scope on)."""
    try:
        sec = await db.system_security_config.find_one({"id": "singleton"}, {"_id": 0})
        enabled = bool(((sec or {}).get("config") or {}).get("rbac", {}).get("entity_scope_enforced"))
    except Exception:  # noqa: BLE001
        enabled = False
    if not enabled or role_bypasses_entity_scope(current):
        return
    user = await db.users.find_one({"id": current.get("user_id")}, {"_id": 0, "entity": 1})
    ue = (user or {}).get("entity")
    if not ue:
        return
    ent = exception.get("entity")
    if not ent or str(ent).strip() != str(ue).strip():
        raise HTTPException(403, "Entity scope violation")


async def assert_master_dq_finding_entity_scope(db, *, current: dict, finding: dict) -> None:
    """Deny MDQ case creation (and similar) when the finding belongs to another legal entity."""
    try:
        sec = await db.system_security_config.find_one({"id": "singleton"}, {"_id": 0})
        enabled = bool(((sec or {}).get("config") or {}).get("rbac", {}).get("entity_scope_enforced"))
    except Exception:  # noqa: BLE001
        enabled = False
    if not enabled or role_bypasses_entity_scope(current):
        return
    user = await db.users.find_one({"id": current.get("user_id")}, {"_id": 0, "entity": 1})
    ue = (user or {}).get("entity")
    if not ue:
        return
    ec = finding.get("entity_code")
    if not ec or str(ec).strip() != str(ue).strip():
        raise HTTPException(403, "Entity scope violation")


async def assert_report_entity_scope(db, *, current: dict, report: dict) -> None:
    """Deny board report reads/exports/signoff by id when ``filters.entity_code`` is outside the user's entity (scope on)."""
    try:
        sec = await db.system_security_config.find_one({"id": "singleton"}, {"_id": 0})
        enabled = bool(((sec or {}).get("config") or {}).get("rbac", {}).get("entity_scope_enforced"))
    except Exception:  # noqa: BLE001
        enabled = False
    if not enabled or role_bypasses_entity_scope(current):
        return
    user = await db.users.find_one({"id": current.get("user_id")}, {"_id": 0, "entity": 1})
    ue = (user or {}).get("entity")
    if not ue:
        return
    ue_s = str(ue).strip()
    filters = report.get("filters") if isinstance(report.get("filters"), dict) else {}
    ec = filters.get("entity_code") or report.get("entity_code")
    if not ec or str(ec).strip() != ue_s:
        raise HTTPException(403, "Entity scope violation")


async def report_list_entity_mongo_filter(db, *, current: dict) -> Dict[str, Any]:
    """Extra ``find`` constraints so scoped users only see reports stamped with their ``filters.entity_code``."""
    try:
        sec = await db.system_security_config.find_one({"id": "singleton"}, {"_id": 0})
        enabled = bool(((sec or {}).get("config") or {}).get("rbac", {}).get("entity_scope_enforced"))
    except Exception:  # noqa: BLE001
        enabled = False
    if not enabled or role_bypasses_entity_scope(current):
        return {}
    user = await db.users.find_one({"id": current.get("user_id")}, {"_id": 0, "entity": 1})
    ue = (user or {}).get("entity")
    if not ue:
        return {}
    return {"filters.entity_code": str(ue).strip()}


async def assert_super_admin_when_entity_scope_enforced(db, *, current: dict) -> None:
    """Global writes with no per-entity row (e.g. shared control catalog): Super Admin only when entity scope is on."""
    try:
        sec = await db.system_security_config.find_one({"id": "singleton"}, {"_id": 0})
        enabled = bool(((sec or {}).get("config") or {}).get("rbac", {}).get("entity_scope_enforced"))
    except Exception:  # noqa: BLE001
        enabled = False
    if not enabled:
        return
    if current.get("role") == "Super Admin":
        return
    raise HTTPException(403, "Entity scope violation")

