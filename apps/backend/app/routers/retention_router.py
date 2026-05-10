"""Retention policy CRUD, eligible list, and purge run."""
from __future__ import annotations
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel

from app.auth import get_current_user
from app.core.entity_scope import entity_scope_enforced
from app.core.security import require_roles
from app.deps import db
from app.services import retention_service as rs
from app.services.rbac_service import enforce_entity_scope

router = APIRouter(prefix="/retention", tags=["retention"])


class RetentionRunBody(BaseModel):
    dry_run: bool = True
    artifact_types: Optional[List[str]] = None


@router.get("/policies")
async def retention_policies_list(
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await rs.list_policies(db)


@router.post("/policies")
async def retention_policies_create(
    body: Dict[str, Any] = Body(...), current=Depends(require_roles("CFO", "Controller", "Compliance Head")),
):
    from app.services.governance_approval_service import require_approval_or_raise
    await require_approval_or_raise(db, action="retention_policy_change", subject_type="retention_policy", subject_id=body.get("id", "new"))
    from app.deps import audit_log
    p = await rs.upsert_policy(db, None, body)
    await audit_log(current["email"], "retention_policy_create", "retention", p.get("id", ""), body)
    return p


@router.put("/policies/{policy_id}")
async def retention_policies_update(
    policy_id: str, body: Dict[str, Any] = Body(...),
    current=Depends(require_roles("CFO", "Controller", "Compliance Head")),
):
    from app.services.governance_approval_service import require_approval_or_raise
    await require_approval_or_raise(db, action="retention_policy_change", subject_type="retention_policy", subject_id=policy_id)
    p = await rs.upsert_policy(db, policy_id, body)
    from app.deps import audit_log
    await audit_log(current["email"], "retention_policy_update", "retention", policy_id, body)
    return p


@router.get("/eligible")
async def retention_eligible(
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await rs.find_eligible(db)


@router.post("/run")
async def retention_run(
    body: RetentionRunBody,
    current=Depends(
        require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin"),
    ),
):
    if await entity_scope_enforced(db) and current.get("role") != "Super Admin":
        raise HTTPException(403, "Entity scope violation")
    return await rs.run_retention(
        db, dry_run=body.dry_run, artifact_types=body.artifact_types, user_email=current["email"],
    )
