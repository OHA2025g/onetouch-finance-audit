"""Multi-entity rollups, hierarchy, drilldown, FX, snapshots."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.core.entity_scope import entity_scope_enforced
from app.core.security import require_roles
from app.deps import db
from app.services import rollup_service as rs
from app.services.rbac_service import enforce_entity_scope, role_bypasses_entity_scope


async def _enforce_rollups_node_scope(db, current: dict, node_id: str) -> None:
    """When entity scope is enforced, deny rollup/drilldown for nodes spanning other legal entities."""
    node = await rs.get_node(db, node_id)
    if not node:
        return
    eids = await rs.entity_codes_for_node(db, node["id"])
    if not eids:
        return
    try:
        sec = await db.system_security_config.find_one({"id": "singleton"}, {"_id": 0})
        enabled = bool(((sec or {}).get("config") or {}).get("rbac", {}).get("entity_scope_enforced"))
    except Exception:  # noqa: BLE001
        enabled = False
    if not enabled or role_bypasses_entity_scope(current):
        return
    user = await db.users.find_one({"id": current.get("user_id")}, {"_id": 0, "entity": 1})
    user_ent = (user or {}).get("entity")
    if not user_ent:
        return
    if not eids.issubset({user_ent}):
        raise HTTPException(403, "Entity scope violation")


router = APIRouter(prefix="/rollups", tags=["rollups"])


async def _rollup_summary_for_current_user(db, current: dict) -> dict:
    """Full org rollup unless entity scope is enforced and the user has an assigned legal entity."""
    if role_bypasses_entity_scope(current):
        return await rs.rollup_summary(db)
    if await entity_scope_enforced(db):
        user = await db.users.find_one({"id": current.get("user_id")}, {"_id": 0, "entity": 1})
        ue = (user or {}).get("entity")
        if ue:
            return await rs.rollup_summary_scoped_to_user_entity(db, ue)
    return await rs.rollup_summary(db)


@router.get("/summary")
async def rollups_summary(
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await _rollup_summary_for_current_user(db, current)


@router.get("/hierarchy")
async def rollups_hierarchy(
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await _rollup_summary_for_current_user(db, current)


@router.get("/entity/{entity_id}")
async def rollups_by_entity(
    entity_id: str, current=Depends(get_current_user),
):
    await _enforce_rollups_node_scope(db, current, entity_id)
    d = await rs.get_entity_rollup(db, entity_id)
    if d.get("error"):
        raise HTTPException(404, d.get("message", "Not found"))
    return d


@router.get("/drilldown")
async def rollups_drilldown(
    node_id: str = Query(..., description="Hierarchy node id or entity code (e.g. US-HQ)"),
    process: Optional[str] = None,
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _enforce_rollups_node_scope(db, current, node_id)
    d = await rs.drilldown(db, node_id, process)
    if d.get("error"):
        raise HTTPException(404, d.get("message", "Not found"))
    return d


@router.post("/recompute")
async def rollups_recompute(
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    if await entity_scope_enforced(db) and not role_bypasses_entity_scope(current):
        raise HTTPException(403, "Entity scope violation")
    return await rs.recompute_snapshots(db)


@router.get("/snapshots/history")
async def rollup_snapshots_history(
    node_id: str = Query(..., description="Hierarchy node id"),
    limit: int = Query(48, ge=2, le=120),
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _enforce_rollups_node_scope(db, current, node_id)
    return await rs.rollup_snapshot_history(db, node_id, limit=limit)


@router.get("/chart/hierarchy")
async def rollup_chart_hierarchy(
    node_id: str = Query(..., description="Parent hierarchy node"),
    metric: str = Query("unresolved_high_risk_exposure"),
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _enforce_rollups_node_scope(db, current, node_id)
    d = await rs.rollup_chart_hierarchy(db, node_id, metric_key=metric)
    if d.get("error"):
        raise HTTPException(404, d.get("message", "Not found"))
    return d


@router.get("/chart/scatter")
async def rollup_chart_scatter(
    node_id: str = Query(..., description="Roll up leaf entities under this node"),
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _enforce_rollups_node_scope(db, current, node_id)
    d = await rs.rollup_chart_scatter_entities(db, node_id)
    if d.get("error"):
        raise HTTPException(404, d.get("message", "Not found"))
    return d


@router.get("/currency-rates")
async def reporting_currency_rates(current=Depends(get_current_user)):
    return {
        "rates": [r async for r in db.reporting_currency_rates.find({}, {"_id": 0})],
        "default_reporting": "USD",
    }
