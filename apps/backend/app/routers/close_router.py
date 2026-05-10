"""Slice 4 — Month-end close management endpoints."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.core.entity_scope import entity_scope_enforced
from app.core.security import require_roles
from app.deps import db, audit_log
from app.services import close_service as cs
from app.services.rbac_service import assert_close_cycle_entity_scope, enforce_entity_scope

router = APIRouter(prefix="/close", tags=["close"])


async def _close_list_entity_filter(current: dict) -> Optional[str]:
    if await entity_scope_enforced(db) and current.get("role") != "Super Admin":
        user = await db.users.find_one({"id": current.get("user_id")}, {"_id": 0, "entity": 1})
        return (user or {}).get("entity")
    return None


async def _require_close_cycle_scope(current: dict, cycle_id: str) -> None:
    cyc = await db.close_cycles.find_one({"id": cycle_id}, {"_id": 0})
    if not cyc:
        raise HTTPException(404, "Close cycle not found")
    await assert_close_cycle_entity_scope(db, current=current, cycle=cyc)


@router.get("/cycles")
async def list_cycles(current=Depends(require_roles("CFO", "Controller", "Super Admin"))):
    ef = await _close_list_entity_filter(current)
    return await cs.list_cycles(db, entity_code=ef)


@router.post("/cycles")
async def create_cycle(
    body: Dict[str, Any] = Body(...),
    current=Depends(require_roles("CFO", "Controller", "Super Admin")),
):
    raw_ec = (str(body.get("entity_code") or "")).strip() or None
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=raw_ec)
    cyc = await cs.create_cycle(
        db,
        period_ym=str(body.get("period_ym") or ""),
        name=str(body.get("name") or ""),
        created_by=current["email"],
        entity_code=entity_code,
    )
    await audit_log(current["email"], "close_cycle_create", "close_cycle", cyc["id"], {"period_ym": cyc["period_ym"]})
    return cyc


@router.get("/cycles/{cycle_id}")
async def get_cycle(cycle_id: str, current=Depends(require_roles("CFO", "Controller", "Super Admin"))):
    out = await cs.get_cycle(db, cycle_id)
    await assert_close_cycle_entity_scope(db, current=current, cycle=out)
    return out


@router.get("/tasks")
async def list_tasks(
    cycle_id: Optional[str] = Query(None),
    current=Depends(require_roles("CFO", "Controller", "Super Admin")),
):
    if cycle_id:
        await _require_close_cycle_scope(current, cycle_id)
        return await cs.list_tasks(db, cycle_id, entity_code=None)
    ef = await _close_list_entity_filter(current)
    return await cs.list_tasks(db, None, entity_code=ef)


@router.post("/tasks")
async def create_task_placeholder(
    body: Dict[str, Any] = Body(...),
    current=Depends(require_roles("CFO", "Controller", "Super Admin")),
):
    """Phase 6 API shape expects POST /close/tasks; we map to template-less ad hoc task insert."""
    cycle_id = str(body.get("cycle_id") or "").strip()
    if not cycle_id:
        raise ValueError("cycle_id required")
    await _require_close_cycle_scope(current, cycle_id)
    # Use patch_task pattern by creating a minimal task directly.
    now = cs._now()  # noqa: SLF001 — local helper for consistency
    doc = {
        "id": f"tsk-{__import__('uuid').uuid4().hex[:10]}",
        "cycle_id": cycle_id,
        "template_code": None,
        "title": str(body.get("title") or "Ad hoc close task"),
        "category": str(body.get("category") or "General"),
        "critical": bool(body.get("critical") or False),
        "status": "draft",
        "owner_email": body.get("owner_email"),
        "due_date": body.get("due_date") or now,
        "evidence": [],
        "notes": [],
        "created_at": now,
        "updated_at": now,
    }
    await db.close_tasks.insert_one(dict(doc))
    await audit_log(current["email"], "close_task_create", "close_task", doc["id"], {"cycle_id": cycle_id})
    return doc


@router.patch("/tasks/{task_id}")
async def patch_task(
    task_id: str,
    body: Dict[str, Any] = Body(...),
    current=Depends(require_roles("CFO", "Controller", "Super Admin")),
):
    t0 = await db.close_tasks.find_one({"id": task_id}, {"_id": 0, "cycle_id": 1})
    if not t0 or not t0.get("cycle_id"):
        raise HTTPException(404, "Task not found")
    await _require_close_cycle_scope(current, t0["cycle_id"])
    doc = await cs.patch_task(db, task_id, body, actor=current["email"])
    await audit_log(current["email"], "close_task_patch", "close_task", task_id, {"fields": list(body.keys())})
    return doc


@router.post("/tasks/{task_id}/evidence")
async def add_evidence(
    task_id: str,
    body: Dict[str, Any] = Body(...),
    current=Depends(require_roles("CFO", "Controller", "Super Admin")),
):
    t0 = await db.close_tasks.find_one({"id": task_id}, {"_id": 0, "cycle_id": 1})
    if not t0 or not t0.get("cycle_id"):
        raise HTTPException(404, "Task not found")
    await _require_close_cycle_scope(current, t0["cycle_id"])
    doc = await cs.add_evidence(db, task_id, body, actor=current["email"])
    await audit_log(current["email"], "close_task_evidence", "close_task", task_id, {"type": body.get("type")})
    return doc


@router.post("/tasks/{task_id}/submit")
async def submit_task(task_id: str, current=Depends(require_roles("Controller", "CFO", "Super Admin"))):
    t0 = await db.close_tasks.find_one({"id": task_id}, {"_id": 0, "cycle_id": 1})
    if not t0 or not t0.get("cycle_id"):
        raise HTTPException(404, "Task not found")
    await _require_close_cycle_scope(current, t0["cycle_id"])
    doc = await cs.submit_task(db, task_id, actor=current["email"])
    await audit_log(current["email"], "close_task_submit", "close_task", task_id)
    return doc


@router.post("/tasks/{task_id}/approve")
async def approve_task(task_id: str, current=Depends(require_roles("CFO", "Controller", "Super Admin"))):
    t0 = await db.close_tasks.find_one({"id": task_id}, {"_id": 0, "cycle_id": 1})
    if not t0 or not t0.get("cycle_id"):
        raise HTTPException(404, "Task not found")
    await _require_close_cycle_scope(current, t0["cycle_id"])
    doc = await cs.approve_task(db, task_id, actor=current["email"])
    await audit_log(current["email"], "close_task_approve", "close_task", task_id)
    return doc


@router.post("/tasks/{task_id}/reopen")
async def reopen_task(
    task_id: str,
    body: Dict[str, Any] = Body(default={}),
    current=Depends(require_roles("CFO", "Controller", "Super Admin")),
):
    t0 = await db.close_tasks.find_one({"id": task_id}, {"_id": 0, "cycle_id": 1})
    if not t0 or not t0.get("cycle_id"):
        raise HTTPException(404, "Task not found")
    await _require_close_cycle_scope(current, t0["cycle_id"])
    doc = await cs.reopen_task(db, task_id, actor=current["email"], note=str(body.get("note") or ""))
    await audit_log(current["email"], "close_task_reopen", "close_task", task_id, {"note": body.get("note")})
    return doc


@router.post("/signoff")
async def signoff(
    body: Dict[str, Any] = Body(...),
    current=Depends(require_roles("CFO", "Super Admin")),
):
    cycle_id = str(body.get("cycle_id") or "")
    if cycle_id:
        await _require_close_cycle_scope(current, cycle_id)
    override = bool(body.get("override") or False)
    reason = str(body.get("override_reason") or "")
    doc = await cs.signoff(db, cycle_id, actor=current["email"], override=override, override_reason=reason)
    await audit_log(
        current["email"],
        "close_cycle_signoff",
        "close_cycle",
        cycle_id,
        {"override": override, "override_reason_chars": len(reason.strip()) if override else 0},
    )
    return doc


@router.get("/bottlenecks")
async def bottlenecks(
    cycle_id: Optional[str] = Query(
        None,
        description="Close cycle id. When omitted, uses the latest cycle by period (same as list_cycles ordering).",
    ),
    current=Depends(require_roles("CFO", "Controller", "Super Admin")),
):
    if cycle_id:
        await _require_close_cycle_scope(current, cycle_id)
    ef = await _close_list_entity_filter(current)
    return await cs.bottlenecks(db, cycle_id, entity_code=ef)


@router.get("/quality-score")
async def quality_score(
    cycle_id: Optional[str] = Query(
        None,
        description="Close cycle id. When omitted, uses the latest cycle by period (same as list_cycles ordering).",
    ),
    current=Depends(require_roles("CFO", "Controller", "Super Admin")),
):
    if cycle_id:
        await _require_close_cycle_scope(current, cycle_id)
    ef = await _close_list_entity_filter(current)
    return await cs.quality_score(db, cycle_id, entity_code=ef)
