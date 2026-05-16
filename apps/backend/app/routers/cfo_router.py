"""Slice 3 — CFO action queue endpoints."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response

from app.core.security import require_roles
from app.deps import db, audit_log
from app.services import action_queue_service as aqs
from app.services import action_queue_analytics_service as aqa
from app.services.action_queue_rate_limit import enforce_action_queue_rate_limit
from app.analytics import cfo_cockpit, controller_dashboard, working_capital_dashboard, treasury_dashboard
from app.services.kpi_service import as_of_now
from app.services.rbac_service import enforce_entity_scope
from app.services import cfo_command_center_service as ccc

router = APIRouter(prefix="/cfo", tags=["cfo"])


@router.get("/action-queue/summary")
async def action_queue_summary(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    process: Optional[str] = Query(None),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Super Admin")),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    out = await aqa.build_summary(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
    )
    out["filters_applied"] = _filters(entity_code, period_ym, department_id, cost_center_id)
    return out


@router.get("/action-queue/dashboard")
async def action_queue_dashboard(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    process: Optional[str] = Query(None),
    record_snapshot: bool = Query(True),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Super Admin")),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    out = await aqa.build_dashboard(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
        record_snapshot_flag=record_snapshot,
    )
    out["filters_applied"] = _filters(entity_code, period_ym, department_id, cost_center_id)
    return out


@router.get("/action-queue/trends")
async def action_queue_trends(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    weeks: int = Query(8, ge=1, le=52),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Super Admin")),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await aqa.build_trends(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        weeks=weeks,
    )


@router.get("/action-queue/export")
async def action_queue_export(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    status: Optional[str] = Query("open"),
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    current=Depends(require_roles("CFO", "Controller", "Super Admin")),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await enforce_action_queue_rate_limit(
        current["email"],
        bucket="export",
        env_key="ACTION_QUEUE_EXPORT_PER_MINUTE",
        default_cap=20,
    )
    out = await aqs.list_queue(
        db,
        limit=500,
        offset=0,
        status=status,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    items = out.get("items") or []
    if format == "xlsx":
        body = aqs.export_xlsx_bytes(items)
        return Response(
            content=body,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=cfo_action_queue.xlsx"},
        )
    csv_body = aqs.export_csv_rows(items)
    return Response(
        content=csv_body,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cfo_action_queue.csv"},
    )


@router.get("/action-queue")
async def action_queue_list(
    refresh: bool = Query(False, description="Recompute and upsert queue items"),
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    process: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="Filter by status (open/approved/rejected/escalated)"),
    priority: Optional[str] = Query(None),
    type: Optional[str] = Query(None, alias="action_type"),
    assignee_email: Optional[str] = Query(None),
    sort: str = Query("score"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    cursor: Optional[str] = Query(None, description="Keyset cursor from prior page next_cursor"),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Super Admin")),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    if refresh:
        await enforce_action_queue_rate_limit(
            current["email"],
            bucket="refresh",
            env_key="ACTION_QUEUE_REFRESH_PER_MINUTE",
            default_cap=10,
        )
        await aqs.refresh_action_queue(
            db,
            entity_code=entity_code,
            period_ym=period_ym,
            department_id=department_id,
            cost_center_id=cost_center_id,
        )
        await aqa.record_snapshot(
            db,
            entity_code=entity_code,
            period_ym=period_ym,
            department_id=department_id,
            cost_center_id=cost_center_id,
        )
    out = await aqs.list_queue(
        db,
        limit=limit,
        offset=offset,
        cursor=cursor,
        status=status,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
        priority=priority,
        action_type=type,
        assignee_email=assignee_email,
        sort=sort,
    )
    out["filters_applied"] = _filters(entity_code, period_ym, department_id, cost_center_id)
    if process:
        out["filters_applied"]["process"] = process
    return out


@router.post("/action/bulk")
async def action_bulk(
    body: Dict[str, Any] = Body(...),
    current=Depends(require_roles("CFO", "Controller", "Super Admin")),
):
    await enforce_action_queue_rate_limit(
        current["email"],
        bucket="bulk",
        env_key="ACTION_QUEUE_BULK_PER_MINUTE",
        default_cap=30,
    )
    ids = body.get("ids") or body.get("action_ids") or []
    action = str(body.get("action") or "")
    if not ids or action not in ("approve", "reject", "escalate"):
        raise HTTPException(400, "ids and action (approve|reject|escalate) required")
    note = str(body.get("note") or "")
    reject_reason = body.get("reject_reason")
    out = await aqs.bulk_action(
        db,
        action_ids=list(ids),
        action=action,
        actor=current["email"],
        note=note,
        reject_reason=str(reject_reason) if reject_reason else None,
    )
    await audit_log(current["email"], "cfo_action_bulk", "cfo_action", action, {"count": len(ids), "action": action})
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
    reject_reason = body.get("reject_reason")
    doc = await aqs.reject(
        db,
        action_id,
        actor=current["email"],
        note=note,
        reject_reason=str(reject_reason) if reject_reason else None,
    )
    await audit_log(
        current["email"],
        "cfo_action_reject",
        "cfo_action",
        action_id,
        {"note": note, "reject_reason": reject_reason},
    )
    return doc


@router.post("/action/{action_id}/reopen")
async def action_reopen(
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
    doc = await aqs.reopen(db, action_id, actor=current["email"], note=note)
    await audit_log(current["email"], "cfo_action_reopen", "cfo_action", action_id, {"note": note})
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


@router.get("/command-center")
async def cfo_command_center(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    process: Optional[str] = Query(None),
    refresh: bool = Query(True, description="Refresh action queue materialization"),
    no_cache: bool = Query(False, description="Bypass 90s response cache"),
    include_narrative: bool = Query(False, description="Include ML executive briefing in payload"),
    queue_limit: int = Query(6, ge=1, le=50),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    """Single BFF payload for CFO Cockpit (Phases A–D)."""
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await ccc.build_command_center(
        db,
        user_email=current["email"],
        user_role=current.get("role"),
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
        refresh_queue=refresh,
        queue_limit=queue_limit,
        use_cache=not no_cache,
        include_narrative=include_narrative,
    )


@router.post("/command-center/narrative")
async def cfo_command_center_narrative(
    body: Dict[str, Any] = Body(default={}),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    """Executive briefing generated by on-platform ML over scoped cockpit data."""
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=body.get("entity_code"))
    period_ym = body.get("period_ym")
    process = body.get("process")
    cockpit = await cfo_cockpit(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=body.get("department_id"),
        cost_center_id=body.get("cost_center_id"),
        process=process,
    )
    kpis = cockpit.get("kpis") or {}
    from app.services.cfo_command_center_service import _build_alerts, _ops_kpis

    ops = await _ops_kpis(db, entity_code=entity_code, period_ym=period_ym)
    alerts = _build_alerts(kpis, ops)
    narrative = await ccc.generate_narrative(
        db,
        user_email=current["email"],
        user_role=current.get("role"),
        entity_code=entity_code,
        period_ym=period_ym,
        cockpit=cockpit,
        alerts=alerts,
        ops_kpis=ops,
        process=process,
    )
    await audit_log(
        current["email"],
        "cfo_ml_narrative_generate",
        "cfo_command_center",
        "narrative",
        {"entity_code": entity_code, "period_ym": period_ym, "model": narrative.get("model")},
    )
    return {"narrative": narrative, "alerts": alerts, "as_of": as_of_now()}


@router.get("/summary")
async def cfo_summary_bff(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    process: Optional[str] = Query(None),
    current=Depends(require_roles("CFO", "Controller", "Internal Auditor", "Compliance Head", "Super Admin")),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    out = await cfo_cockpit(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
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

