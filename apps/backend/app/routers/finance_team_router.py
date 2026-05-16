"""Phase 7 — ``/finance-team/*`` BFF for the finance operations team view."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.security import require_roles
from app.deps import db
from app.services import finance_team_service as fts
from app.services.rbac_service import enforce_entity_scope

router = APIRouter(prefix="/finance-team", tags=["finance-team"])


@router.get("/summary")
async def finance_team_summary(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await fts.finance_team_dashboard(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )


@router.get("/workload")
async def finance_team_workload(
    entity_code: Optional[str] = Query(None),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await fts.finance_team_workload(db, entity_code=entity_code)


@router.get("/sla-trend")
async def finance_team_sla_trend(
    entity_code: Optional[str] = Query(None),
    limit: int = Query(12, ge=1, le=36),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await fts.finance_team_sla_trend(db, entity_code=entity_code, limit=limit)


@router.get("/sla")
async def finance_team_sla(
    entity_code: Optional[str] = Query(None),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await fts.finance_team_sla(db, entity_code=entity_code)


@router.get("/rework")
async def finance_team_rework(
    entity_code: Optional[str] = Query(None),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await fts.finance_team_rework(db, entity_code=entity_code)


@router.get("/bottlenecks")
async def finance_team_bottlenecks(
    entity_code: Optional[str] = Query(None),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await fts.finance_team_bottlenecks(db, entity_code=entity_code)


@router.get("/scorecards")
async def finance_team_scorecards(
    entity_code: Optional[str] = Query(None),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await fts.finance_team_scorecards(db, entity_code=entity_code)
