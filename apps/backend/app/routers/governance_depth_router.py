"""Wave 3 — Compliance / governance read models (Phase 40 L4).

Backed by existing collections (RPT, DoA, SoD certification, MDQ) with optional ``entity_code``
and the same ``enforce_entity_scope`` behavior as other dashboards.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from app.auth import get_current_user
from app.deps import db
from app.services import master_dq_service as mdq_svc
from app.services.rbac_service import enforce_entity_scope
from app.routers.access_router import _ensure_seed_access
from app.routers.doa_router import _ensure_seed_doa
from app.routers.rpt_router import _ensure_seed_rpt

router = APIRouter(prefix="/compliance-depth", tags=["compliance-depth"])


def _depth_payload(*, entity_code: Optional[str], extra: Dict[str, Any]) -> Dict[str, Any]:
    scope_label = "ALL ENTITIES" if entity_code in (None, "") else str(entity_code)
    out: Dict[str, Any] = {"entity_code": entity_code, "scope_label": scope_label, **extra}
    return out


@router.get("/rpt/register")
async def rpt_register(
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_rpt(entity_code=eff)
    filt: Dict[str, Any] = {}
    if eff:
        filt["entity"] = eff
    related_parties_count = await db.related_parties.count_documents(filt)
    rpt_transactions_count = await db.rpt_transactions.count_documents(filt)
    items: List[Dict[str, Any]] = [
        x async for x in db.related_parties.find(filt, {"_id": 0}).sort("name", 1).limit(15)
    ]
    return _depth_payload(
        entity_code=eff,
        extra={
            "related_parties_count": related_parties_count,
            "rpt_transactions_count": rpt_transactions_count,
            "items": items,
            "note": "Related-party master + RPT transactions for the selected reporting scope.",
        },
    )


@router.get("/legal/notices")
async def legal_notices(
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    filt: Dict[str, Any] = {}
    if eff:
        filt["entity"] = eff
    n = await db.legal_notices.count_documents(filt)
    items = [x async for x in db.legal_notices.find(filt, {"_id": 0}).sort("id", -1).limit(10)]
    return _depth_payload(
        entity_code=eff,
        extra={"items": items, "count": n, "note": "Legal notices register (Wave 3)."},
    )


@router.get("/doa/rules")
async def doa_rules(
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_doa(entity_code=eff)
    q: Dict[str, Any] = {"entity": eff} if eff else {}
    items = [x async for x in db.doa_rules.find(q, {"_id": 0}).sort("id", 1).limit(25)]
    rules_count = await db.doa_rules.count_documents(q)
    matrix_rows = await db.doa_matrix.count_documents(q)
    return _depth_payload(
        entity_code=eff,
        extra={
            "items": items,
            "rules_count": rules_count,
            "matrix_rows": matrix_rows,
            "note": "Delegation of authority — policy rules and matrix rows for scope.",
        },
    )


@router.get("/sod/campaigns")
async def sod_campaigns(
    status: Optional[str] = Query(None),
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_access(entity_code=eff)
    cq: Dict[str, Any] = {}
    if eff:
        cq["entity"] = eff
    if status and str(status).strip():
        cq["status"] = str(status).strip()
    items = [x async for x in db.access_certification_campaigns.find(cq, {"_id": 0}).sort("created_at", -1).limit(25)]
    campaigns_total = await db.access_certification_campaigns.count_documents(cq)
    return _depth_payload(
        entity_code=eff,
        extra={
            "items": items,
            "campaigns_total": campaigns_total,
            "status_filter": status,
            "note": "SoD / access certification campaigns for scope.",
        },
    )


@router.get("/mdq/summary")
async def mdq_summary(
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    sumy = await mdq_svc.summary(db, entity_code=eff or None)
    by_sev = sumy.get("open_by_severity") or {}
    open_findings = int(sum(int(v) for v in by_sev.values())) if by_sev else 0
    return _depth_payload(
        entity_code=eff,
        extra={
            **sumy,
            "open_findings": open_findings,
            "note": "Master data quality — open findings by severity and master object type.",
        },
    )
