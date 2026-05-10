"""Legal hold lifecycle: create, list, release, link artifacts."""
from __future__ import annotations
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel

from app.auth import get_current_user
from app.core.entity_scope import entity_scope_enforced
from app.core.security import require_roles
from app.deps import audit_log, db
from app.services import legal_hold_service as lhs
from app.services.rbac_service import enforce_entity_scope

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
    hold_entity: Optional[str] = None
    if body.scope == "entity":
        hold_entity = await enforce_entity_scope(db, current=current, requested_entity_code=body.entity_code)
    elif body.entity_code:
        hold_entity = await enforce_entity_scope(db, current=current, requested_entity_code=body.entity_code)
    d = await lhs.create_hold(
        db, name=body.name, scope=body.scope, reason=body.reason, created_by=current["email"],
        entity_code=hold_entity if hold_entity is not None else body.entity_code,
    )
    await audit_log(current["email"], "legal_hold_create", "legal_hold", d["id"], body.model_dump())
    return d


@router.get("")
async def legal_holds_list(
    status: str = Query("active"),
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    filt: str | None = None
    if await entity_scope_enforced(db) and current.get("role") != "Super Admin":
        user = await db.users.find_one({"id": current.get("user_id")}, {"_id": 0, "entity": 1})
        ue = (user or {}).get("entity")
        filt = str(ue).strip() if ue else None
    return await lhs.list_holds(db, status=status, limit=500, entity_code=filt)


@router.get("/{hold_id}")
async def legal_hold_detail(
    hold_id: str, current=Depends(get_current_user),
):
    h = await db.legal_holds.find_one({"id": hold_id}, {"_id": 0})
    if not h:
        raise HTTPException(404, "Hold not found")
    if h.get("entity_code"):
        await enforce_entity_scope(db, current=current, requested_entity_code=h.get("entity_code"))
    links = [l async for l in db.hold_artifact_links.find({"hold_id": hold_id}, {"_id": 0})]
    return {"hold": h, "links": links}


@router.post("/{hold_id}/release")
async def legal_hold_release(
    hold_id: str,
    reason: str = Query("Released after review"),
    current=Depends(require_roles("CFO", "Internal Auditor", "Compliance Head")),
):
    from app.services.governance_approval_service import require_approval_or_raise
    h0 = await db.legal_holds.find_one({"id": hold_id}, {"_id": 0, "entity_code": 1})
    if h0 and h0.get("entity_code"):
        await enforce_entity_scope(db, current=current, requested_entity_code=h0.get("entity_code"))
    rel_ent = (str(h0.get("entity_code")).strip() if h0 and h0.get("entity_code") else None)
    await require_approval_or_raise(
        db,
        action="legal_hold_release",
        subject_type="legal_hold",
        subject_id=hold_id,
        entity_code=rel_ent,
    )
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
    h0 = await db.legal_holds.find_one({"id": hold_id}, {"_id": 0, "entity_code": 1})
    if h0 and h0.get("entity_code"):
        await enforce_entity_scope(db, current=current, requested_entity_code=h0.get("entity_code"))
    n = await lhs.attach_artifacts(db, hold_id, body.artifacts, current["email"])
    await audit_log(current["email"], "legal_hold_attach", "legal_hold", hold_id, {"n": n})
    return {"linked": n}
