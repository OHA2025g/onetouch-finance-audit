"""Data trust / data quality visibility endpoints (Child prompt 3)."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from app.auth import get_current_user
from app.core.entity_scope import resolve_entity_code_for_query
from app.core.security import require_roles
from app.deps import db
from app.services import connector_service as cs
from app.services import master_dq_service as mdq

router = APIRouter(prefix="/dq", tags=["data-trust"])


@router.get("/health")
async def dq_health(current=Depends(get_current_user)):
    return await cs.dq_health(db)


@router.get("/schema-validations")
async def dq_schema_validations(limit: int = Query(200, ge=1, le=1000), current=Depends(get_current_user)):
    return await cs.dq_schema_validations(db, limit=limit)


# ---------------- Phase 2 hardening: master data quality ----------------

@router.get("/masters/summary")
async def masters_dq_summary(current=Depends(get_current_user)):
    return await mdq.summary(db)


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
    eff_entity = await resolve_entity_code_for_query(db, current, entity_code)
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

