"""Phase 7 — Finance team dashboard aggregates (close + cases + CFO signals)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.analytics import cfo_cockpit, controller_dashboard
from app.services import action_queue_service as aqs
from app.services import close_service as cs
from app.services.kpi_service import as_of_now


async def _cycle_ids_for_entity(db, entity_code: Optional[str]) -> Optional[List[str]]:
    """When ``entity_code`` is set, return cycle ids for that entity (possibly empty). ``None`` = no cycle filter (global)."""
    if not entity_code:
        return None
    return [c["id"] async for c in db.close_cycles.find({"entity_code": entity_code}, {"id": 1, "_id": 0})]


def _cycle_scope_query(cycle_ids: Optional[List[str]]) -> Dict[str, Any]:
    """Mongo filter fragment restricting ``close_tasks`` to cycles for an entity."""
    if cycle_ids is None:
        return {}
    if not cycle_ids:
        return {"cycle_id": {"$in": []}}
    return {"cycle_id": {"$in": cycle_ids}}


async def count_open_close_tasks(db, *, entity_code: Optional[str] = None) -> int:
    """Open close tasks, scoped to ``entity_code`` cycles when provided (matches close hub semantics)."""
    cids = await _cycle_ids_for_entity(db, entity_code)
    q: Dict[str, Any] = {
        "status": {"$in": ["draft", "reopened", "submitted"]},
        **_cycle_scope_query(cids),
    }
    return await db.close_tasks.count_documents(q)


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
    open_tasks = await count_open_close_tasks(db, entity_code=entity_code)
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
    cids = await _cycle_ids_for_entity(db, entity_code)
    q: Dict[str, Any] = {
        "status": {"$in": ["draft", "reopened", "submitted"]},
        **_cycle_scope_query(cids),
    }
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


async def finance_team_sla(db, *, entity_code: Optional[str] = None) -> Dict[str, Any]:
    """SLA proxy: share of approved close tasks (scoped to entity cycles when ``entity_code`` is set)."""
    cids = await _cycle_ids_for_entity(db, entity_code)
    scope = _cycle_scope_query(cids)
    total = await db.close_tasks.count_documents(scope)
    approved = await db.close_tasks.count_documents({**scope, "status": "approved"})
    pct = round(100.0 * approved / (total or 1), 1)
    return {"approved_pct": pct, "total_tasks": total, "as_of": as_of_now()}


async def finance_team_sla_trend(
    db,
    *,
    entity_code: Optional[str] = None,
    limit: int = 12,
) -> Dict[str, Any]:
    """Time series: close-task approved % per close cycle (newest ``limit`` cycles, oldest→newest in ``series``)."""
    lim = max(1, min(int(limit or 12), 36))
    cycles = await cs.list_cycles(db, entity_code=entity_code)
    window: List[Dict[str, Any]] = list(reversed(cycles[:lim]))
    series: List[Dict[str, Any]] = []
    for c in window:
        cid = c.get("id")
        if not cid:
            continue
        tasks = [t async for t in db.close_tasks.find({"cycle_id": cid}, {"_id": 0, "status": 1})]
        total = len(tasks)
        approved = sum(1 for t in tasks if t.get("status") == "approved")
        pending = sum(1 for t in tasks if t.get("status") in ("draft", "reopened", "submitted"))
        pct = round(100.0 * approved / (total or 1), 1)
        series.append({
            "period_ym": c.get("period_ym"),
            "cycle_id": cid,
            "cycle_name": c.get("name"),
            "cycle_status": c.get("status"),
            "approved_pct": pct,
            "total_tasks": total,
            "approved_count": approved,
            "pending_count": pending,
        })
    return {
        "series": series,
        "metric": "close_task_approved_pct_per_cycle",
        "limit": lim,
        "as_of": as_of_now(),
    }


async def finance_team_rework(db, *, entity_code: Optional[str] = None) -> Dict[str, Any]:
    """Rework proxy: tasks that were reopened at least once (scoped to entity cycles when set)."""
    cids = await _cycle_ids_for_entity(db, entity_code)
    scope = _cycle_scope_query(cids)
    reopened = await db.close_tasks.count_documents({**scope, "status": "reopened"})
    total = await db.close_tasks.count_documents(scope)
    pct = round(100.0 * reopened / (total or 1), 1)
    return {"reopened_pct": pct, "reopened_tasks": reopened, "total_tasks": total, "as_of": as_of_now()}


async def finance_team_bottlenecks(db, *, entity_code: Optional[str] = None) -> Dict[str, Any]:
    """Return bottlenecks for the most recent cycle if present (entity-aware cycle resolution)."""
    b = await cs.bottlenecks(db, None, entity_code=entity_code)
    return {**b, "as_of": as_of_now()}


async def finance_team_scorecards(db, *, entity_code: Optional[str] = None) -> Dict[str, Any]:
    """Role scorecards: expose a small set of actionable metrics per role."""
    q = await aqs.list_queue(db, limit=1, offset=0, status="open")
    open_actions = q.get("total", 0)
    open_close = await count_open_close_tasks(db, entity_code=entity_code)
    return {
        "scorecards": [
            {"role": "Controller", "open_close_tasks": open_close},
            {"role": "CFO", "open_actions": open_actions},
        ],
        "as_of": as_of_now(),
    }
