"""Phase 7 — Finance team dashboard aggregates (close + cases + CFO signals)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.analytics import cfo_cockpit, controller_dashboard
from app.services import action_queue_service as aqs
from app.services import close_service as cs
from app.services.kpi_service import as_of_now


async def finance_team_dashboard(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
) -> Dict[str, Any]:
    cockpit = await cfo_cockpit(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    ctrl = await controller_dashboard(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    cycles = await cs.list_cycles(db, entity_code=entity_code)
    open_tasks = await db.close_tasks.count_documents(
        {"status": {"$in": ["draft", "reopened", "submitted"]}}
    )
    q_summary = await aqs.list_queue(db, limit=1, offset=0, status=None)
    filters_applied = {k: v for k, v in {
        "entity_code": entity_code,
        "period_ym": period_ym,
        "department_id": department_id,
        "cost_center_id": cost_center_id,
    }.items() if v}
    return {
        "cycles": {"items": cycles, "count": len(cycles)},
        "close_tasks_open": open_tasks,
        "controller": {"kpis": ctrl.get("kpis"), "filters_applied": ctrl.get("filters_applied")},
        "cockpit_kpis": cockpit.get("kpis"),
        "action_queue_total": q_summary.get("total", 0),
        "filters_applied": filters_applied,
        "as_of": as_of_now(),
        "drill_paths": {
            "close": "/app/finance-operations/month-end-close",
            "cases": "/app/cases?status=open",
            "exceptions": "/app/audit",
        },
    }


async def finance_team_workload(db, *, entity_code: Optional[str] = None) -> Dict[str, Any]:
    """Lightweight workload view: pending close tasks grouped by owner."""
    q: Dict[str, Any] = {"status": {"$in": ["draft", "reopened", "submitted"]}}
    if entity_code:
        q["entity_code"] = entity_code
    tasks = [t async for t in db.close_tasks.find(q, {"_id": 0, "owner_email": 1, "status": 1, "critical": 1})]
    by_owner: Dict[str, int] = {}
    critical_by_owner: Dict[str, int] = {}
    for t in tasks:
        o = t.get("owner_email") or "unassigned"
        by_owner[o] = by_owner.get(o, 0) + 1
        if t.get("critical"):
            critical_by_owner[o] = critical_by_owner.get(o, 0) + 1
    top = sorted(by_owner.items(), key=lambda kv: -kv[1])[:10]
    return {
        "pending_tasks": len(tasks),
        "by_owner": by_owner,
        "critical_by_owner": critical_by_owner,
        "top": top,
        "as_of": as_of_now(),
    }


async def finance_team_sla(db) -> Dict[str, Any]:
    """SLA proxy: share of approved close tasks."""
    total = await db.close_tasks.count_documents({})
    approved = await db.close_tasks.count_documents({"status": "approved"})
    pct = round(100.0 * approved / (total or 1), 1)
    return {"approved_pct": pct, "total_tasks": total, "as_of": as_of_now()}


async def finance_team_rework(db) -> Dict[str, Any]:
    """Rework proxy: tasks that were reopened at least once."""
    reopened = await db.close_tasks.count_documents({"status": "reopened"})
    total = await db.close_tasks.count_documents({})
    pct = round(100.0 * reopened / (total or 1), 1)
    return {"reopened_pct": pct, "reopened_tasks": reopened, "total_tasks": total, "as_of": as_of_now()}


async def finance_team_bottlenecks(db) -> Dict[str, Any]:
    """Return bottlenecks for the most recent cycle if present."""
    b = await cs.bottlenecks(db, None)
    return {**b, "as_of": as_of_now()}


async def finance_team_scorecards(db) -> Dict[str, Any]:
    """Role scorecards: expose a small set of actionable metrics per role."""
    q = await aqs.list_queue(db, limit=1, offset=0, status="open")
    open_actions = q.get("total", 0)
    open_close = await db.close_tasks.count_documents({"status": {"$in": ["draft", "reopened", "submitted"]}})
    return {
        "scorecards": [
            {"role": "Controller", "open_close_tasks": open_close},
            {"role": "CFO", "open_actions": open_actions},
        ],
        "as_of": as_of_now(),
    }
