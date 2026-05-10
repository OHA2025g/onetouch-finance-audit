"""Governance approvals + policy versions (Child prompt 4)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.core.entity_scope import entity_scope_enforced
from app.core.security import require_roles
from app.deps import audit_log, db
from app.services import governance_approval_service as gas
from app.services.rbac_service import enforce_entity_scope, role_bypasses_entity_scope

router = APIRouter(prefix="/governance", tags=["governance"])


class ApprovalRequestBody(BaseModel):
    request_type: str
    subject_type: str
    subject_id: str
    reason: str = ""
    proposed_change: Dict[str, Any] = Field(default_factory=dict)
    entity_code: Optional[str] = Field(
        default=None,
        description="Legal entity this approval applies to; coerced to the caller's entity when RBAC scope is on.",
    )


class DecisionBody(BaseModel):
    note: str = ""


async def _governance_approvals_entity_filter(current: dict) -> Optional[str]:
    if not await entity_scope_enforced(db):
        return None
    if role_bypasses_entity_scope(current):
        return None
    user = await db.users.find_one({"id": current.get("user_id")}, {"_id": 0, "entity": 1})
    ue = (user or {}).get("entity")
    return str(ue).strip() if ue else None


@router.get("/policies")
async def governance_policies(
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await gas.get_policy(db)


@router.post("/policies")
async def governance_policy_update(
    body: Dict[str, Any] = Body(...),
    current=Depends(require_roles("CFO", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    if await entity_scope_enforced(db) and current.get("role") != "Super Admin":
        raise HTTPException(403, "Entity scope violation")
    pol = await gas.get_policy(db)
    version = int(pol.get("version", 1)) + 1
    pol["version"] = version
    if "requires_approval" in body:
        pol["requires_approval"] = body["requires_approval"]
    from datetime import datetime, timezone
    from app.utils.timeutil import iso_utc
    pol["updated_at"] = iso_utc(datetime.now(timezone.utc))
    pol["updated_by"] = current["email"]
    await db.governance_policy_versions.update_one({"id": "singleton"}, {"$set": pol}, upsert=True)
    await audit_log(current["email"], "governance_policy_update", "governance_policy", "singleton", {"version": version})
    return pol


@router.get("/approvals")
async def approvals_list(
    status: Optional[str] = Query(None),
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    ec = await _governance_approvals_entity_filter(current)
    list_entity = eff if eff else ec
    return await gas.list_requests(db, status=status, limit=300, entity_code=list_entity)


@router.post("/approvals")
async def approvals_create(
    body: ApprovalRequestBody,
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head")),
):
    raw_ec = (body.entity_code or "").strip() or None
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=raw_ec)
    d = await gas.create_request(
        db,
        request_type=body.request_type,
        subject_type=body.subject_type,
        subject_id=body.subject_id,
        proposed_change=body.proposed_change,
        requested_by=current["email"],
        reason=body.reason,
        entity_code=eff,
    )
    await audit_log(current["email"], "approval_request_create", "approval_request", d["id"], body.model_dump())
    return d


@router.post("/approvals/{request_id}/approve")
async def approvals_approve(
    request_id: str,
    body: DecisionBody,
    current=Depends(require_roles("CFO", "Internal Auditor", "Compliance Head")),
):
    d = await gas.decide(
        db,
        request_id=request_id,
        decision="approved",
        decided_by=current["email"],
        note=body.note,
        current=current,
    )
    await audit_log(current["email"], "approval_approve", "approval_request", request_id, {"note": body.note})
    return d


@router.post("/approvals/{request_id}/reject")
async def approvals_reject(
    request_id: str,
    body: DecisionBody,
    current=Depends(require_roles("CFO", "Internal Auditor", "Compliance Head")),
):
    d = await gas.decide(
        db,
        request_id=request_id,
        decision="rejected",
        decided_by=current["email"],
        note=body.note,
        current=current,
    )
    await audit_log(current["email"], "approval_reject", "approval_request", request_id, {"note": body.note})
    return d
