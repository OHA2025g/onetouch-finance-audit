"""Wave 3 — Compliance / governance REST stubs (workflows land incrementally)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from app.auth import get_current_user
from app.deps import db
from app.services.rbac_service import enforce_entity_scope

router = APIRouter(prefix="/compliance-depth", tags=["compliance-depth"])


def _depth_payload(*, entity_code: Optional[str], extra: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"entity_code": entity_code, **extra}
    return out


@router.get("/rpt/register")
async def rpt_register(
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return _depth_payload(
        entity_code=eff,
        extra={"items": [], "note": "Related-party transaction register — seed rpt_register collection."},
    )


@router.get("/legal/notices")
async def legal_notices(
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return _depth_payload(
        entity_code=eff,
        extra={"items": [], "note": "Legal notice workflow — attach to compliance reviews."},
    )


@router.get("/doa/rules")
async def doa_rules(
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return _depth_payload(
        entity_code=eff,
        extra={"items": [], "note": "Delegation of authority matrix."},
    )


@router.get("/sod/campaigns")
async def sod_campaigns(
    status: Optional[str] = Query(None),
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return _depth_payload(
        entity_code=eff,
        extra={"items": [], "status_filter": status, "note": "SoD certification campaigns."},
    )


@router.get("/mdq/summary")
async def mdq_summary(
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return _depth_payload(
        entity_code=eff,
        extra={"open_findings": 0, "note": "Master data quality command center (Wave 3)."},
    )
