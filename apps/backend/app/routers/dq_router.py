"""Data trust / data quality visibility endpoints (Child prompt 3)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query

from app.auth import get_current_user
from app.core.security import require_roles
from app.services.rbac_service import enforce_entity_scope
from app.deps import db
from app.services import connector_service as cs
from app.services import master_dq_service as mdq

router = APIRouter(prefix="/dq", tags=["data-trust"])


@router.get("/health")
async def dq_health(
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await cs.dq_health(db, entity_code=eff)


@router.get("/schema-validations")
async def dq_schema_validations(
    limit: int = Query(200, ge=1, le=1000),
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await cs.dq_schema_validations(db, limit=limit)


# ---------------- Phase 2 hardening: master data quality ----------------

@router.get("/masters/summary")
async def masters_dq_summary(
    entity_code: str | None = Query(None),
    current=Depends(get_current_user),
):
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    out = await mdq.summary(db, entity_code=eff or None)
    if eff:
        out["entity_scope_applied"] = True
        out["entity_codes"] = [eff]
    return out


@router.get("/masters/findings")
async def masters_dq_findings(
    master_type: str | None = Query(None),
    severity: str | None = Query(None),
    entity_code: str | None = Query(None),
    status: str = Query("open"),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current=Depends(get_current_user),
):
    eff_entity = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await mdq.list_findings(
        db,
        master_type=master_type,
        severity=severity,
        entity_code=eff_entity,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.post("/masters/recompute")
async def masters_dq_recompute(
    body: dict = Body(default={}),
    current=Depends(require_roles("Super Admin")),
):
    limit_per_type = int(body.get("limit_per_type") or 50_000)
    if limit_per_type < 1 or limit_per_type > 200_000:
        raise ValueError("limit_per_type out of range")
    return await mdq.recompute_findings(db, limit_per_type=limit_per_type)

