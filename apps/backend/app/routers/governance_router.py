"""Governance approvals + policy versions (Child prompt 4)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel

from app.auth import get_current_user
from app.core.security import require_roles
from app.deps import audit_log, db
from app.services import governance_approval_service as gas

router = APIRouter(prefix="/governance", tags=["governance"])


class ApprovalRequestBody(BaseModel):
    request_type: str
    subject_type: str
    subject_id: str
    reason: str = ""
    proposed_change: Dict[str, Any] = {}


class DecisionBody(BaseModel):
    note: str = ""


@router.get("/policies")
async def governance_policies(current=Depends(get_current_user)):
    return await gas.get_policy(db)


@router.post("/policies")
async def governance_policy_update(
    body: Dict[str, Any] = Body(...),
    current=Depends(require_roles("CFO", "Internal Auditor", "Compliance Head")),
):
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
    current=Depends(get_current_user),
):
    return await gas.list_requests(db, status=status, limit=300)


@router.post("/approvals")
async def approvals_create(
    body: ApprovalRequestBody,
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head")),
):
    d = await gas.create_request(
        db,
        request_type=body.request_type,
        subject_type=body.subject_type,
        subject_id=body.subject_id,
        proposed_change=body.proposed_change,
        requested_by=current["email"],
        reason=body.reason,
    )
    await audit_log(current["email"], "approval_request_create", "approval_request", d["id"], body.model_dump())
    return d


@router.post("/approvals/{request_id}/approve")
async def approvals_approve(
    request_id: str,
    body: DecisionBody,
    current=Depends(require_roles("CFO", "Internal Auditor", "Compliance Head")),
):
    d = await gas.decide(db, request_id=request_id, decision="approved", decided_by=current["email"], note=body.note)
    await audit_log(current["email"], "approval_approve", "approval_request", request_id, {"note": body.note})
    return d


@router.post("/approvals/{request_id}/reject")
async def approvals_reject(
    request_id: str,
    body: DecisionBody,
    current=Depends(require_roles("CFO", "Internal Auditor", "Compliance Head")),
):
    d = await gas.decide(db, request_id=request_id, decision="rejected", decided_by=current["email"], note=body.note)
    await audit_log(current["email"], "approval_reject", "approval_request", request_id, {"note": body.note})
    return d

