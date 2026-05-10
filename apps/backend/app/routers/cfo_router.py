"""Slice 3 — CFO action queue endpoints."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.core.security import require_roles
from app.deps import db, audit_log
from app.services import action_queue_service as aqs
from app.analytics import cfo_cockpit, controller_dashboard, working_capital_dashboard, treasury_dashboard
from app.services.kpi_service import as_of_now
from app.services.rbac_service import enforce_entity_scope

router = APIRouter(prefix="/cfo", tags=["cfo"])


@router.get("/action-queue")
async def action_queue_list(
    refresh: bool = Query(False, description="Recompute and upsert queue items"),
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="Filter by status (open/approved/rejected/escalated)"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Super Admin")),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    if refresh:
        await aqs.refresh_action_queue(
            db,
            entity_code=entity_code,
            period_ym=period_ym,
            department_id=department_id,
            cost_center_id=cost_center_id,
        )
    out = await aqs.list_queue(db, limit=limit, offset=offset, status=status)
    out["filters_applied"] = {k: v for k, v in {
        "entity_code": entity_code,
        "period_ym": period_ym,
        "department_id": department_id,
        "cost_center_id": cost_center_id,
    }.items() if v}
    return out


@router.get("/action-queue/{action_id}")
async def action_queue_detail(
    action_id: str,
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Super Admin")),
):
    doc = await aqs.get_action(db, action_id)
    if not doc:
        raise HTTPException(404, "Action not found")
    det = doc.get("detail") or {}
    ent = doc.get("entity") or det.get("entity")
    if ent:
        await enforce_entity_scope(db, current=current, requested_entity_code=ent)
    return doc


@router.post("/action/{action_id}/approve")
async def action_approve(
    action_id: str,
    body: Dict[str, Any] = Body(default={}),
    current=Depends(require_roles("CFO", "Controller", "Super Admin")),
):
    doc0 = await aqs.get_action(db, action_id)
    if not doc0:
        raise HTTPException(404, "Action not found")
    det = doc0.get("detail") or {}
    ent = doc0.get("entity") or det.get("entity")
    if ent:
        await enforce_entity_scope(db, current=current, requested_entity_code=ent)
    note = str(body.get("note") or "")
    doc = await aqs.approve(db, action_id, actor=current["email"], note=note)
    await audit_log(current["email"], "cfo_action_approve", "cfo_action", action_id, {"note": note})
    return doc


@router.post("/action/{action_id}/reject")
async def action_reject(
    action_id: str,
    body: Dict[str, Any] = Body(default={}),
    current=Depends(require_roles("CFO", "Controller", "Super Admin")),
):
    doc0 = await aqs.get_action(db, action_id)
    if not doc0:
        raise HTTPException(404, "Action not found")
    det = doc0.get("detail") or {}
    ent = doc0.get("entity") or det.get("entity")
    if ent:
        await enforce_entity_scope(db, current=current, requested_entity_code=ent)
    note = str(body.get("note") or "")
    doc = await aqs.reject(db, action_id, actor=current["email"], note=note)
    await audit_log(current["email"], "cfo_action_reject", "cfo_action", action_id, {"note": note})
    return doc


@router.post("/action/{action_id}/escalate")
async def action_escalate(
    action_id: str,
    body: Dict[str, Any] = Body(default={}),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Super Admin")),
):
    doc0 = await aqs.get_action(db, action_id)
    if not doc0:
        raise HTTPException(404, "Action not found")
    det = doc0.get("detail") or {}
    ent = doc0.get("entity") or det.get("entity")
    if ent:
        await enforce_entity_scope(db, current=current, requested_entity_code=ent)
    note = str(body.get("note") or "")
    doc = await aqs.escalate(db, action_id, actor=current["email"], note=note)
    await audit_log(current["email"], "cfo_action_escalate", "cfo_action", action_id, {"note": note})
    return doc


@router.post("/action/{action_id}/comment")
async def action_comment(
    action_id: str,
    body: Dict[str, Any] = Body(...),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Super Admin")),
):
    doc0 = await aqs.get_action(db, action_id)
    if not doc0:
        raise HTTPException(404, "Action not found")
    det = doc0.get("detail") or {}
    ent = doc0.get("entity") or det.get("entity")
    if ent:
        await enforce_entity_scope(db, current=current, requested_entity_code=ent)
    text = str(body.get("comment") or "").strip()
    if not text:
        raise HTTPException(400, "comment is required")
    doc = await aqs.comment(db, action_id, actor=current["email"], comment_text=text)
    await audit_log(current["email"], "cfo_action_comment", "cfo_action", action_id, {"comment": text[:200]})
    return doc


def _filters(entity_code, period_ym, department_id, cost_center_id):
    return {k: v for k, v in {
        "entity_code": entity_code,
        "period_ym": period_ym,
        "department_id": department_id,
        "cost_center_id": cost_center_id,
    }.items() if v}


@router.get("/summary")
async def cfo_summary_bff(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    out = await cfo_cockpit(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    out["as_of"] = as_of_now()
    return out


@router.get("/financial-health")
async def cfo_financial_health(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    c = await cfo_cockpit(
        db, entity_code=entity_code, period_ym=period_ym, department_id=department_id, cost_center_id=cost_center_id
    )
    ctrl = await controller_dashboard(
        db, entity_code=entity_code, period_ym=period_ym, department_id=department_id, cost_center_id=cost_center_id
    )
    return {
        "cockpit_kpis": c.get("kpis"),
        "controller_kpis": ctrl.get("kpis"),
        "heatmap": c.get("heatmap"),
        "filters_applied": _filters(entity_code, period_ym, department_id, cost_center_id),
        "as_of": as_of_now(),
    }


@router.get("/risk-summary")
async def cfo_risk_summary(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    c = await cfo_cockpit(
        db, entity_code=entity_code, period_ym=period_ym, department_id=department_id, cost_center_id=cost_center_id
    )
    return {
        "top_risks": c.get("top_risks"),
        "top_failing_controls": c.get("top_failing_controls"),
        "kpis": c.get("kpis"),
        "filters_applied": _filters(entity_code, period_ym, department_id, cost_center_id),
        "as_of": as_of_now(),
    }


@router.get("/liquidity-watch")
async def cfo_liquidity_watch(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    t = await treasury_dashboard(
        db, entity_code=entity_code, period_ym=period_ym, department_id=department_id, cost_center_id=cost_center_id
    )
    return {"treasury": t, "filters_applied": _filters(entity_code, period_ym, department_id, cost_center_id), "as_of": as_of_now()}


@router.get("/working-capital")
async def cfo_working_capital(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    wc = await working_capital_dashboard(
        db, entity_code=entity_code, period_ym=period_ym, department_id=department_id, cost_center_id=cost_center_id
    )
    return {"working_capital": wc, "filters_applied": _filters(entity_code, period_ym, department_id, cost_center_id), "as_of": as_of_now()}


@router.get("/team-performance")
async def cfo_team_performance(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    from app.services import finance_team_service as fts

    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    out = await fts.finance_team_dashboard(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    out["as_of"] = as_of_now()
    return out

