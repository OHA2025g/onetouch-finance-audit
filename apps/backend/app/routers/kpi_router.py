"""Phase 3 / Slice 2 — KPI engine endpoints (minimal initial surface).

These endpoints are designed as a stable contract for the CFO cockpit UI:
- definitions: label/unit/drill mapping
- cfo-summary: values under current master filter scope
- trend: 8-point series per CFO hero KPI (readiness from cockpit; others anchored to current values)
- drilldown: references to contributing exceptions, cases, and controls (scoped like ``/dashboard/cfo``)
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from app.core.security import require_roles
from app.deps import db
from app.services import kpi_service as ks
from app.services.rbac_service import enforce_entity_scope

router = APIRouter(prefix="/kpi", tags=["kpi"])


@router.post("/refresh")
async def kpi_refresh(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await ks.refresh_kpis(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )


@router.get("/definitions")
async def kpi_definitions(current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin"))):
    items = ks.kpi_definitions()
    return {"items": items, "count": len(items), "as_of": ks.as_of_now()}


@router.get("/cfo-summary")
async def kpi_cfo_summary(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await ks.cfo_kpi_summary(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )


@router.get("/trend/{kpi_id}")
async def kpi_trend(
    kpi_id: str,
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    process: Optional[str] = Query(None),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await ks.kpi_trend(
        db,
        kpi_id,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
    )


@router.get("/drilldown/audit_readiness_pct/export")
async def kpi_audit_readiness_export(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    process: Optional[str] = Query(None),
    format: str = Query("csv", description="csv or xlsx"),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    body, media_type, filename = await ks.export_audit_readiness_drill(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
        fmt=format,
    )
    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/drilldown/{kpi_id}")
async def kpi_drilldown(
    kpi_id: str,
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    process: Optional[str] = Query(None),
    cells_limit: int = Query(50, ge=1, le=200),
    cells_offset: int = Query(0, ge=0),
    controls_limit: int = Query(10, ge=1, le=50),
    controls_offset: int = Query(0, ge=0),
    exceptions_limit: int = Query(15, ge=1, le=50),
    exceptions_offset: int = Query(0, ge=0),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await ks.kpi_drilldown(
        db,
        kpi_id,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
        cells_limit=cells_limit,
        cells_offset=cells_offset,
        controls_limit=controls_limit,
        controls_offset=controls_offset,
        exceptions_limit=exceptions_limit,
        exceptions_offset=exceptions_offset,
    )
