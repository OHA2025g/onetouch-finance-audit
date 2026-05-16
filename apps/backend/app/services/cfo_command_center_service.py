"""CFO Command Center BFF — cache, ops KPIs, what-changed, alerts, narrative."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.analytics import cfo_cockpit, treasury_dashboard
from app.services import action_queue_service as aqs
from app.services import action_queue_analytics_service as aqa
from app.services.cfo_executive_narrative_ml import build_executive_narrative_ml
from app.services import bank_recon_service as brs
from app.services import kpi_snapshot_service as kss
from app.services import reconciliation_metrics as rm
from app.services.kpi_service import as_of_now, cfo_kpi_summary, kpi_definitions
from app.utils.timeutil import iso_utc

_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL_SEC = 90

KPI_THRESHOLDS = {
    "audit_readiness_pct": {"good": 80, "warn": 60, "higher_is_better": True},
    "remediation_sla_pct": {"good": 85, "warn": 70, "higher_is_better": True},
    "repeat_finding_rate_pct": {"good": 20, "warn": 30, "higher_is_better": False},
    "high_critical_open_cases": {"good": 3, "warn": 6, "higher_is_better": False},
    "reconciliations_overdue": {"good": 0, "warn": 2, "higher_is_better": False},
    "close_critical_tasks_open": {"good": 0, "warn": 1, "higher_is_better": False},
    "bank_pending_signoff": {"good": 0, "warn": 2, "higher_is_better": False},
}


def _cache_key(scope: str, process: Optional[str], refresh: bool) -> str:
    return f"{scope}|p={process or ''}|r={int(refresh)}"


def _invalidate_scope_cache(scope: str) -> None:
    prefix = f"{scope}|"
    for k in list(_CACHE.keys()):
        if k.startswith(prefix):
            del _CACHE[k]


async def _ops_kpis(
    db,
    *,
    entity_code: Optional[str],
    period_ym: Optional[str],
) -> List[Dict[str, Any]]:
    overdue, total = await rm.count_overdue_reconciliations(db, entity_code=entity_code, period_ym=period_ym)
    bank = await brs.build_summary(db, entity_code=entity_code, scan_limit=200)
    bk = bank.get("kpis") or {}
    crit_close = await db.close_tasks.count_documents(
        {"critical": True, "status": {"$in": ["draft", "reopened", "submitted"]}}
    )
    treasury = await treasury_dashboard(db, entity_code=entity_code, period_ym=period_ym)
    runway = (treasury.get("kpis") or {}).get("liquidity_runway_weeks")

    rows = [
        {
            "id": "close_critical_tasks_open",
            "label": "Close — critical tasks",
            "unit": "count",
            "value": crit_close,
            "severity": "critical" if crit_close > 0 else "success",
            "drill_path": "/app/finance-operations/month-end-close",
        },
        {
            "id": "reconciliations_overdue",
            "label": "Recons overdue",
            "unit": "count",
            "value": overdue,
            "severity": "critical" if overdue > 2 else ("warning" if overdue > 0 else "success"),
            "drill_path": "/app/financial-audit/reconciliations-dashboard",
            "subtle": f"{total} total in scope" if total else None,
        },
        {
            "id": "bank_pending_signoff",
            "label": "Bank recon pending",
            "unit": "count",
            "value": bk.get("pending_signoff_count", 0),
            "severity": "warning" if (bk.get("pending_signoff_count") or 0) > 0 else "success",
            "drill_path": "/app/financial-audit/bank-reconciliation-dashboard",
        },
        {
            "id": "liquidity_runway_weeks",
            "label": "Liquidity runway",
            "unit": "weeks",
            "value": runway,
            "severity": None if runway is None else ("warning" if float(runway) < 8 else "success"),
            "drill_path": "/app/treasury",
        },
    ]
    return rows


def _build_alerts(kpis: Dict[str, Any], ops: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []
    merged = dict(kpis)
    for o in ops:
        if o.get("id") and o.get("value") is not None:
            merged[o["id"]] = o["value"]

    for kid, rules in KPI_THRESHOLDS.items():
        val = merged.get(kid)
        if val is None:
            continue
        try:
            v = float(val)
        except (TypeError, ValueError):
            continue
        good, warn = rules["good"], rules["warn"]
        higher = rules["higher_is_better"]
        breached = (v < warn) if higher else (v > warn)
        if not breached:
            continue
        sev = "critical" if ((v < good) if higher else (v > good)) else "warning"
        alerts.append({
            "id": f"alert-{kid}",
            "code": kid,
            "severity": sev,
            "title": kid.replace("_", " ").title(),
            "message": f"Current {v} vs target (good ≥{good}, warn ≥{warn})" if higher else f"Current {v} vs target (good ≤{good}, warn ≤{warn})",
            "metric": kid,
            "value": v,
            "threshold_warn": warn,
            "threshold_good": good,
        })
    return alerts[:12]


async def _what_changed(
    db,
    *,
    user_email: str,
    scope: str,
    current_kpis: Dict[str, Any],
    current_p0: int,
) -> Dict[str, Any]:
    visit = await db.cfo_cockpit_visits.find_one(
        {"user_email": user_email, "scope_key": scope},
        {"_id": 0},
        sort=[("visited_at", -1)],
    )
    changes: List[Dict[str, Any]] = []
    if visit:
        prior = visit.get("kpis") or {}
        for kid in kss.SNAPSHOT_KPI_KEYS:
            cur = current_kpis.get(kid)
            old = prior.get(kid)
            if cur is None or old is None:
                continue
            try:
                delta = float(cur) - float(old)
            except (TypeError, ValueError):
                continue
            if abs(delta) < 0.05 and kid.endswith("_pct"):
                continue
            if delta == 0:
                continue
            changes.append({
                "kpi_id": kid,
                "prior": old,
                "current": cur,
                "delta_abs": round(delta, 2),
                "direction": "up" if delta > 0 else "down",
            })
        prior_p0 = int(visit.get("p0_open_count") or 0)
        if current_p0 > prior_p0:
            changes.insert(0, {
                "kpi_id": "p0_actions",
                "prior": prior_p0,
                "current": current_p0,
                "delta_abs": current_p0 - prior_p0,
                "direction": "up",
                "label": "New P0 queue items",
            })

    return {
        "has_prior_visit": bool(visit),
        "last_visited_at": visit.get("visited_at") if visit else None,
        "changes": changes[:8],
    }


async def record_visit(
    db,
    *,
    user_email: str,
    scope: str,
    kpis: Dict[str, Any],
    p0_open_count: int,
) -> None:
    doc = {
        "user_email": user_email,
        "scope_key": scope,
        "kpis": {k: kpis.get(k) for k in kss.SNAPSHOT_KPI_KEYS if kpis.get(k) is not None},
        "p0_open_count": p0_open_count,
        "visited_at": iso_utc(datetime.now(timezone.utc)),
    }
    await db.cfo_cockpit_visits.update_one(
        {"user_email": user_email, "scope_key": scope},
        {"$set": doc},
        upsert=True,
    )


async def generate_narrative(
    db,
    *,
    user_email: str,
    user_role: Optional[str],
    entity_code: Optional[str],
    period_ym: Optional[str],
    cockpit: Dict[str, Any],
    alerts: List[Dict[str, Any]],
    ops_kpis: Optional[List[Dict[str, Any]]] = None,
    process: Optional[str] = None,
    action_queue_summary: Optional[Dict[str, Any]] = None,
    top_queue_items: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Data-driven executive briefing (weighted ML model over cockpit telemetry)."""
    void = db  # reserved for future snapshot-enriched features
    del void, user_email, user_role
    return build_executive_narrative_ml(
        cockpit=cockpit,
        alerts=alerts,
        ops_kpis=ops_kpis,
        entity_code=entity_code,
        period_ym=period_ym,
        process=process,
        action_queue_summary=action_queue_summary,
        top_queue_items=top_queue_items,
    )


async def build_command_center(
    db,
    *,
    user_email: str,
    user_role: Optional[str] = None,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
    process: Optional[str] = None,
    refresh_queue: bool = True,
    queue_limit: int = 6,
    use_cache: bool = True,
    record_visit_flag: bool = True,
    include_narrative: bool = True,
) -> Dict[str, Any]:
    scope = kss.scope_key(
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
    )
    ck = _cache_key(scope, process, refresh_queue)
    if use_cache and ck in _CACHE:
        exp, payload = _CACHE[ck]
        if time.time() < exp:
            return {**payload, "cached": True}

    cockpit = await cfo_cockpit(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
    )
    kpis = dict(cockpit.get("kpis") or {})

    ops = await _ops_kpis(db, entity_code=entity_code, period_ym=period_ym)
    for o in ops:
        if o.get("id") and o.get("value") is not None:
            kpis[o["id"]] = o["value"]

    await kss.ensure_seed_snapshots(
        db,
        kpis,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
    )
    from app.services.readiness_drill_service import _portfolio_components

    heatmap = cockpit.get("heatmap") or []
    await kss.record_snapshot(
        db,
        kpis,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
        readiness_cells=kss.heatmap_to_cell_map(heatmap),
        portfolio_components=kss.portfolio_components_snapshot(_portfolio_components(heatmap)),
    )

    trends = await kss.fetch_weekly_trends(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
    )
    if not trends:
        trends = cockpit.get("trends") or []
    cockpit["trends"] = trends

    summary = await cfo_kpi_summary(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
    )
    hero = await kss.enrich_kpis_with_deltas(
        db,
        summary.get("kpis") or [],
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
    )
    ops_enriched = await kss.enrich_kpis_with_deltas(
        db,
        ops,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
    )

    if refresh_queue:
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
    queue = await aqs.list_queue(
        db,
        limit=queue_limit,
        offset=0,
        status="open",
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
    )
    action_queue_summary = await aqa.build_summary(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
    )
    p0_count = int(action_queue_summary.get("p0_open") or 0)

    linkage = await aqa.ops_linkage(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
    )
    link_map = {r.get("id"): r.get("linked_queue_count", 0) for r in linkage}
    for o in ops_enriched:
        o["linked_queue_count"] = link_map.get(o.get("id"), 0)

    alerts = _build_alerts(kpis, ops)
    if p0_count >= 3:
        alerts.insert(
            0,
            {
                "id": "alert-p0-queue",
                "code": "p0_action_queue",
                "severity": "critical",
                "title": "P0 action queue backlog",
                "message": f"{p0_count} P0 items require CFO attention",
                "metric": "p0_open",
                "value": p0_count,
                "href": "/app/cfo-action-queue?priority=P0",
            },
        )
    what_changed = await _what_changed(
        db,
        user_email=user_email,
        scope=scope,
        current_kpis=kpis,
        current_p0=p0_count,
    )

    narrative = None
    if include_narrative:
        narrative = await generate_narrative(
            db,
            user_email=user_email,
            user_role=user_role,
            entity_code=entity_code,
            period_ym=period_ym,
            cockpit=cockpit,
            alerts=alerts,
            ops_kpis=ops_enriched,
            process=process,
            action_queue_summary=action_queue_summary,
            top_queue_items=(queue.get("items") or [])[:5],
        )

    if record_visit_flag:
        await record_visit(db, user_email=user_email, scope=scope, kpis=kpis, p0_open_count=p0_count)

    filters = dict(cockpit.get("filters_applied") or {})
    if process:
        filters["process"] = process

    payload = {
        "as_of": as_of_now(),
        "cached": False,
        "cockpit": cockpit,
        "hero_kpis": hero,
        "ops_kpis": ops_enriched,
        "kpi_definitions": kpi_definitions(),
        "action_queue": queue,
        "action_queue_summary": action_queue_summary,
        "what_changed": what_changed,
        "alerts": alerts,
        "narrative": narrative,
        "filters_applied": filters,
    }
    _CACHE[ck] = (time.time() + _CACHE_TTL_SEC, payload)
    return payload


def clear_all_cache() -> None:
    _CACHE.clear()


def invalidate_cache_for_scope(
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
    process: Optional[str] = None,
) -> None:
    scope = kss.scope_key(
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
    )
    _invalidate_scope_cache(scope)
