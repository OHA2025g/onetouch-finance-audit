"""Legal hold lifecycle: create, list, release, link artifacts."""
from __future__ import annotations
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel

from app.auth import get_current_user
from app.core.security import require_roles
from app.deps import audit_log, db
from app.services import legal_hold_service as lhs

router = APIRouter(prefix="/legal-holds", tags=["legal-holds"])


class CreateHoldBody(BaseModel):
    name: str
    scope: str  # case|evidence|export|entity|global
    reason: str
    entity_code: Optional[str] = None


class AttachBody(BaseModel):
    artifacts: List[Dict[str, str]]  # [{"type":"case","id":"..."}]


@router.post("/")
async def legal_holds_create(
    body: CreateHoldBody, current=Depends(require_roles("CFO", "Internal Auditor", "Compliance Head", "Controller")),
):
    if body.scope not in ("case", "evidence", "export", "entity", "global"):
        raise HTTPException(400, "Invalid scope")
    d = await lhs.create_hold(
        db, name=body.name, scope=body.scope, reason=body.reason, created_by=current["email"],
        entity_code=body.entity_code,
    )
    await audit_log(current["email"], "legal_hold_create", "legal_hold", d["id"], body.model_dump())
    return d


@router.get("")
async def legal_holds_list(
    status: str = Query("active"),
    current=Depends(get_current_user),
):
    return await lhs.list_holds(db, status=status, limit=500)


@router.get("/{hold_id}")
async def legal_hold_detail(
    hold_id: str, current=Depends(get_current_user),
):
    h = await db.legal_holds.find_one({"id": hold_id}, {"_id": 0})
    if not h:
        raise HTTPException(404, "Hold not found")
    links = [l async for l in db.hold_artifact_links.find({"hold_id": hold_id}, {"_id": 0})]
    return {"hold": h, "links": links}


@router.post("/{hold_id}/release")
async def legal_hold_release(
    hold_id: str,
    reason: str = Query("Released after review"),
    current=Depends(require_roles("CFO", "Internal Auditor", "Compliance Head")),
):
    from app.services.governance_approval_service import require_approval_or_raise
    await require_approval_or_raise(db, action="legal_hold_release", subject_type="legal_hold", subject_id=hold_id)
    d = await lhs.release_hold(db, hold_id, current["email"], reason)
    if not d:
        raise HTTPException(404, "Not found")
    await audit_log(current["email"], "legal_hold_release", "legal_hold", hold_id, {"reason": reason})
    return d


@router.post("/{hold_id}/attach-artifacts")
async def legal_hold_attach(
    hold_id: str, body: AttachBody,
    current=Depends(require_roles("CFO", "Internal Auditor", "Compliance Head")),
):
    n = await lhs.attach_artifacts(db, hold_id, body.artifacts, current["email"])
    await audit_log(current["email"], "legal_hold_attach", "legal_hold", hold_id, {"n": n})
    return {"linked": n}
