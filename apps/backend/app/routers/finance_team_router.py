"""Phase 7 — ``/finance-team/*`` BFF for the finance operations team view."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.security import require_roles
from app.deps import db
from app.services import finance_team_service as fts

router = APIRouter(prefix="/finance-team", tags=["finance-team"])


@router.get("/summary")
async def finance_team_summary(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
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
    return await fts.finance_team_workload(db, entity_code=entity_code)


@router.get("/sla")
async def finance_team_sla(
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    return await fts.finance_team_sla(db)


@router.get("/rework")
async def finance_team_rework(
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    return await fts.finance_team_rework(db)


@router.get("/bottlenecks")
async def finance_team_bottlenecks(
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    return await fts.finance_team_bottlenecks(db)


@router.get("/scorecards")
async def finance_team_scorecards(
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    return await fts.finance_team_scorecards(db)
