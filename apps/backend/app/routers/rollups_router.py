"""Multi-entity rollups, hierarchy, drilldown, FX, snapshots."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.core.security import require_roles
from app.deps import db
from app.services import rollup_service as rs

router = APIRouter(prefix="/rollups", tags=["rollups"])


@router.get("/summary")
async def rollups_summary(current=Depends(get_current_user)):
    return await rs.rollup_summary(db)


@router.get("/hierarchy")
async def rollups_hierarchy(current=Depends(get_current_user)):
    return await rs.rollup_hierarchy_with_metrics(db)


@router.get("/entity/{entity_id}")
async def rollups_by_entity(
    entity_id: str, current=Depends(get_current_user),
):
    d = await rs.get_entity_rollup(db, entity_id)
    if d.get("error"):
        raise HTTPException(404, d.get("message", "Not found"))
    return d


@router.get("/drilldown")
async def rollups_drilldown(
    node_id: str = Query(..., description="Hierarchy node id or entity code (e.g. US-HQ)"),
    process: Optional[str] = None,
    current=Depends(get_current_user),
):
    d = await rs.drilldown(db, node_id, process)
    if d.get("error"):
        raise HTTPException(404, d.get("message", "Not found"))
    return d


@router.post("/recompute")
async def rollups_recompute(
    _current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head")),
):
    return await rs.recompute_snapshots(db)


@router.get("/currency-rates")
async def reporting_currency_rates(current=Depends(get_current_user)):
    return {
        "rates": [r async for r in db.reporting_currency_rates.find({}, {"_id": 0})],
        "default_reporting": "USD",
    }
