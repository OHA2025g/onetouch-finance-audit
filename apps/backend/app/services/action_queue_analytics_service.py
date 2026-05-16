"""CFO Action Queue — analytics, trends, snapshots, ops linkage."""

from __future__ import annotations

import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.analytics import cfo_cockpit
from app.services import action_queue_service as aqs
from app.services.cfo_command_center_service import _ops_kpis
from app.services.kpi_service import as_of_now
from app.utils.timeutil import iso_utc

_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL = 90.0
SLA_DAYS = aqs.SLA_DAYS
STALE_DAYS = aqs.STALE_OPEN_DAYS


def _scope_key(**kwargs) -> str:
    parts = [f"{k}={v or ''}" for k, v in sorted(kwargs.items())]
    return "|".join(parts)


def _cached(key: str, factory):
    now = time.time()
    hit = _CACHE.get(key)
    if hit and hit[0] > now:
        return hit[1]
    val = factory()
    _CACHE[key] = (now + _CACHE_TTL, val)
    return val


def _exposure_of(item: Dict[str, Any]) -> float:
    det = item.get("detail") or {}
    try:
        return float(det.get("exposure") or det.get("financial_exposure") or 0)
    except (TypeError, ValueError):
        return 0.0


def _is_sla_breached(item: Dict[str, Any], age_days: float) -> bool:
    pri = item.get("priority") or "P3"
    return age_days > SLA_DAYS.get(pri, 14)


async def _fetch_scoped_items(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
    process: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    out = await aqs.list_queue(
        db,
        limit=limit,
        offset=0,
        status=status,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
    )
    return out.get("items") or []


def _compute_summary(items: List[Dict[str, Any]], all_status_items: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    open_items = [i for i in items if i.get("status") == "open"]
    all_items = all_status_items or items

    by_priority = Counter(i.get("priority") for i in open_items)
    by_type = Counter(i.get("type") for i in open_items)
    by_status = Counter(i.get("status") for i in all_items)

    ages = [float(i.get("age_days") or aqs._age_days(i.get("created_at"), now=now)) for i in open_items]
    mean_age = round(sum(ages) / len(ages), 1) if ages else 0.0
    oldest = round(max(ages), 1) if ages else 0.0

    exposure = sum(_exposure_of(i) for i in open_items)
    overdue_n = 0
    sla_ok = 0
    stale = 0
    for i in open_items:
        age = float(i.get("age_days") or 0)
        if _is_sla_breached(i, age):
            overdue_n += 1
        else:
            sla_ok += 1
        evts = i.get("events") or []
        if age > STALE_DAYS and len(evts) == 0:
            stale += 1

    open_n = len(open_items)
    overdue_pct = round(100.0 * overdue_n / open_n, 1) if open_n else 0.0
    sla_compliance_pct = round(100.0 * sla_ok / open_n, 1) if open_n else 100.0

    entity_counts = Counter(i.get("entity") or "unknown" for i in open_items)
    top_ent, top_cnt = ("", 0)
    if entity_counts:
        top_ent, top_cnt = entity_counts.most_common(1)[0]
    entity_concentration_pct = round(100.0 * top_cnt / open_n, 1) if open_n else 0.0

    aging_buckets = {"0_3": 0, "4_7": 0, "8_14": 0, "14_plus": 0}
    for age in ages:
        if age <= 3:
            aging_buckets["0_3"] += 1
        elif age <= 7:
            aging_buckets["4_7"] += 1
        elif age <= 14:
            aging_buckets["8_14"] += 1
        else:
            aging_buckets["14_plus"] += 1

    # decision metrics (7d window)
    week_ago = now - timedelta(days=7)
    decided = 0
    escalated = 0
    created_7d = 0
    ttf_hours: List[float] = []
    ttc_days: List[float] = []
    notes_with_action = 0
    actions_with_note = 0

    for i in all_items:
        created = aqs._parse_dt(i.get("created_at"))
        if created and created >= week_ago:
            created_7d += 1
        evts = i.get("events") or []
        terminal = [e for e in evts if e.get("type") in ("approved", "rejected", "escalated")]
        if terminal:
            actions_with_note += 1
            if any(e.get("note") for e in terminal):
                notes_with_action += 1
        if i.get("status") == "escalated":
            escalated += 1
        if i.get("status") in ("approved", "rejected"):
            decided += 1
            if created and evts:
                first = aqs._parse_dt(evts[0].get("at"))
                if first:
                    ttf_hours.append((first - created).total_seconds() / 3600.0)
                last = aqs._parse_dt(evts[-1].get("at"))
                if last:
                    ttc_days.append((last - created).total_seconds() / 86400.0)

    decision_rate_7d = round(100.0 * decided / max(created_7d, 1), 1)
    escalation_rate_7d = round(100.0 * escalated / max(len(all_items), 1), 1)
    audit_note_completeness_pct = round(100.0 * notes_with_action / max(actions_with_note, 1), 1)

    approval_items = [i for i in open_items if i.get("type") == "approval_pending"]
    approval_ages = [
        float(i.get("age_days") or aqs._age_days(i.get("created_at"), now=now)) for i in approval_items
    ]
    approval_pending_avg_days = round(sum(approval_ages) / len(approval_ages), 1) if approval_ages else 0.0

    exposure_by_process: Dict[str, float] = defaultdict(float)
    for i in open_items:
        proc = i.get("process") or (i.get("detail") or {}).get("process") or "Unassigned"
        exposure_by_process[proc] += _exposure_of(i)
    exposure_by_process_rows = [
        {"process": k, "exposure": round(v, 2)} for k, v in sorted(exposure_by_process.items(), key=lambda x: -x[1])
    ][:10]

    return {
        "open_total": open_n,
        "by_priority": dict(by_priority),
        "by_type": dict(by_type),
        "by_status": dict(by_status),
        "queue_exposure_usd": round(exposure, 2),
        "mean_age_days": mean_age,
        "oldest_open_age_days": oldest,
        "overdue_pct": overdue_pct,
        "sla_compliance_pct": sla_compliance_pct,
        "stale_open_count": stale,
        "entity_concentration_pct": entity_concentration_pct,
        "top_entity": top_ent,
        "aging_buckets": aging_buckets,
        "decision_rate_7d": decision_rate_7d,
        "escalation_rate_7d": escalation_rate_7d,
        "approval_pending_avg_days": approval_pending_avg_days,
        "audit_note_completeness_pct": audit_note_completeness_pct,
        "median_time_to_first_action_hours": round(sorted(ttf_hours)[len(ttf_hours) // 2], 1) if ttf_hours else None,
        "median_time_to_close_days": round(sorted(ttc_days)[len(ttc_days) // 2], 1) if ttc_days else None,
        "exposure_by_process": exposure_by_process_rows,
        "p0_open": by_priority.get("P0", 0),
        "p1_open": by_priority.get("P1", 0),
    }


async def build_summary(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
    process: Optional[str] = None,
) -> Dict[str, Any]:
    open_items = await _fetch_scoped_items(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
        status="open",
    )
    all_items = await _fetch_scoped_items(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
        status=None,
        limit=500,
    )
    summary = _compute_summary(open_items, all_items)
    summary["as_of"] = as_of_now()
    return summary


async def record_snapshot(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
) -> None:
    summary = await build_summary(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    scope_key = _scope_key(
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    readiness_pct = 0.0
    try:
        cockpit = await cfo_cockpit(db, entity_code=entity_code, period_ym=period_ym)
        readiness_pct = float((cockpit.get("kpis") or {}).get("audit_readiness_pct") or 0)
    except Exception:
        pass
    doc = {
        "scope_key": scope_key,
        "recorded_at": as_of_now(),
        "week_key": datetime.now(timezone.utc).strftime("%G-W%V"),
        "open_total": summary.get("open_total", 0),
        "p0_open": summary.get("p0_open", 0),
        "queue_exposure_usd": summary.get("queue_exposure_usd", 0),
        "audit_readiness_pct": readiness_pct,
        "by_status": summary.get("by_status", {}),
        "by_type": summary.get("by_type", {}),
    }
    await db.cfo_action_queue_snapshots.update_one(
        {"scope_key": scope_key, "week_key": doc["week_key"]},
        {"$set": doc},
        upsert=True,
    )


async def build_trends(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
    weeks: int = 8,
) -> Dict[str, Any]:
    scope_key = _scope_key(
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    cur = (
        db.cfo_action_queue_snapshots.find({"scope_key": scope_key}, {"_id": 0})
        .sort("recorded_at", -1)
        .limit(weeks)
    )
    snaps = [s async for s in cur]
    snaps.reverse()
    if len(snaps) < 2:
        summary = await build_summary(
            db,
            entity_code=entity_code,
            period_ym=period_ym,
            department_id=department_id,
            cost_center_id=cost_center_id,
        )
        pt = {
            "week": datetime.now(timezone.utc).strftime("%G-W%V"),
            "open_total": summary.get("open_total", 0),
            "p0_open": summary.get("p0_open", 0),
            "decisions": 0,
            "escalations": 0,
        }
        snaps = [pt]

    series = []
    for s in snaps:
        by_status = s.get("by_status") or {}
        series.append(
            {
                "week": s.get("week_key") or s.get("recorded_at", "")[:10],
                "open_total": s.get("open_total", 0),
                "p0_open": s.get("p0_open", 0),
                "queue_exposure_usd": s.get("queue_exposure_usd", 0),
                "approved": int(by_status.get("approved", 0)),
                "rejected": int(by_status.get("rejected", 0)),
                "escalated": int(by_status.get("escalated", 0)),
            }
        )

    all_items = await _fetch_scoped_items(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        status=None,
        limit=500,
    )
    type_mix: Dict[str, int] = Counter(i.get("type") for i in all_items if i.get("status") == "open")

    type_mix_series: List[Dict[str, Any]] = []
    for s in snaps:
        by_type = s.get("by_type") or {}
        row: Dict[str, Any] = {"week": s.get("week_key") or (s.get("recorded_at") or "")[:10]}
        row.update({str(k): int(v) for k, v in by_type.items()})
        type_mix_series.append(row)

    throughput = [
        {
            "week": pt["week"],
            "approved": pt.get("approved", 0),
            "rejected": pt.get("rejected", 0),
            "escalated": pt.get("escalated", 0),
        }
        for pt in series
    ]

    return {
        "series": series,
        "type_mix_open": dict(type_mix),
        "type_mix_series": type_mix_series,
        "throughput": throughput,
        "weeks": weeks,
    }


async def top_exposure(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    items = await _fetch_scoped_items(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        status="open",
        limit=200,
    )
    rows = []
    for i in items:
        exp = _exposure_of(i)
        rows.append(
            {
                "id": i.get("id"),
                "title": i.get("title"),
                "exposure": exp,
                "priority": i.get("priority"),
                "type": i.get("type"),
            }
        )
    rows.sort(key=lambda r: -r["exposure"])
    return rows[:limit]


async def entity_process_matrix(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    items = await _fetch_scoped_items(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        status="open",
    )
    grid: Dict[Tuple[str, str], int] = defaultdict(int)
    for i in items:
        ent = i.get("entity") or "unknown"
        proc = i.get("process") or (i.get("detail") or {}).get("process") or "Unassigned"
        grid[(ent, proc)] += 1
    return [{"entity": e, "process": p, "count": c} for (e, p), c in sorted(grid.items(), key=lambda x: -x[1])]


async def ops_linkage(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
    process: Optional[str] = None,
) -> List[Dict[str, Any]]:
    open_items = await _fetch_scoped_items(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
        status="open",
        limit=500,
    )
    by_type = Counter(i.get("type") for i in open_items)

    ops = await _ops_kpis(db, entity_code=entity_code, period_ym=period_ym)
    mapping = {
        "close_critical_tasks_open": "close_critical_task",
        "reconciliations_overdue": "reconciliation_overdue",
        "bank_pending_signoff": "bank_signoff_pending",
        "liquidity_runway_weeks": "treasury_alert",
    }
    rows = []
    for o in ops:
        oid = o.get("id")
        linked = by_type.get(mapping.get(oid, ""), 0)
        rows.append({**o, "linked_queue_count": linked})
    return rows


async def sla_burndown(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
    target_p0: int = 0,
    weeks: int = 8,
) -> Dict[str, Any]:
    items = await _fetch_scoped_items(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        status="open",
        limit=500,
    )
    p0 = sum(1 for i in items if (i.get("priority") or "").upper() == "P0")
    scope_key = _scope_key(
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    cur = (
        db.cfo_action_queue_snapshots.find({"scope_key": scope_key}, {"_id": 0})
        .sort("recorded_at", -1)
        .limit(weeks)
    )
    snaps = [s async for s in cur]
    snaps.reverse()
    series = [
        {
            "week": s.get("week_key") or (s.get("recorded_at") or "")[:10],
            "p0_open": int(s.get("p0_open") or 0),
            "open_total": int(s.get("open_total") or 0),
        }
        for s in snaps
    ]
    if not series:
        series = [{"week": datetime.now(timezone.utc).strftime("%G-W%V"), "p0_open": p0, "open_total": len(items)}]
    return {
        "current_p0": p0,
        "target_p0": target_p0,
        "remaining": max(0, p0 - target_p0),
        "series": series,
    }


async def readiness_correlation(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
) -> Dict[str, Any]:
    cockpit = await cfo_cockpit(db, entity_code=entity_code, period_ym=period_ym)
    readiness = float((cockpit.get("kpis") or {}).get("audit_readiness_pct") or 0)
    summary = await build_summary(db, entity_code=entity_code, period_ym=period_ym)
    series = await readiness_correlation_series(
        db, entity_code=entity_code, period_ym=period_ym, current_readiness=readiness
    )
    return {
        "audit_readiness_pct": readiness,
        "open_total": summary.get("open_total", 0),
        "p0_open": summary.get("p0_open", 0),
        "queue_exposure_usd": summary.get("queue_exposure_usd", 0),
        "series": series,
    }


async def readiness_correlation_series(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    current_readiness: Optional[float] = None,
    weeks: int = 8,
) -> List[Dict[str, Any]]:
    scope_key = _scope_key(entity_code=entity_code, period_ym=period_ym)
    cur = (
        db.cfo_action_queue_snapshots.find({"scope_key": scope_key}, {"_id": 0})
        .sort("recorded_at", -1)
        .limit(weeks)
    )
    snaps = [s async for s in cur]
    snaps.reverse()
    series: List[Dict[str, Any]] = []
    for s in snaps:
        series.append(
            {
                "week": s.get("week_key") or (s.get("recorded_at") or "")[:10],
                "open_total": int(s.get("open_total") or 0),
                "p0_open": int(s.get("p0_open") or 0),
                "audit_readiness_pct": float(s.get("audit_readiness_pct") or 0),
            }
        )
    if current_readiness is not None:
        wk = datetime.now(timezone.utc).strftime("%G-W%V")
        if not series or series[-1].get("week") != wk:
            summary = await build_summary(db, entity_code=entity_code, period_ym=period_ym)
            series.append(
                {
                    "week": wk,
                    "open_total": int(summary.get("open_total") or 0),
                    "p0_open": int(summary.get("p0_open") or 0),
                    "audit_readiness_pct": float(current_readiness),
                }
            )
    return series


async def priority_by_type_stack(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    items = await _fetch_scoped_items(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        status="open",
    )
    grid: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for i in items:
        pri = i.get("priority") or "P3"
        typ = i.get("type") or "unknown"
        grid[pri][typ] += 1
    rows: List[Dict[str, Any]] = []
    for pri in ("P0", "P1", "P2", "P3"):
        if pri not in grid:
            continue
        row: Dict[str, Any] = {"priority": pri}
        row.update(dict(grid[pri]))
        rows.append(row)
    return rows


async def approver_bottleneck(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
    limit: int = 8,
) -> List[Dict[str, Any]]:
    items = await _fetch_scoped_items(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        status="open",
    )
    counts: Dict[str, int] = defaultdict(int)
    for i in items:
        assignee = i.get("assignee_email") or (i.get("detail") or {}).get("owner_email") or "unassigned"
        counts[str(assignee)] += 1
    rows = [{"assignee": k, "open_count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])]
    return rows[:limit]


async def build_dashboard(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
    process: Optional[str] = None,
    record_snapshot_flag: bool = True,
) -> Dict[str, Any]:
    key = _scope_key(
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
    )
    now = time.time()
    hit = _CACHE.get(key)
    if hit and hit[0] > now:
        return hit[1]
    payload = await _build_dashboard_uncached(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
        record_snapshot_flag=record_snapshot_flag,
    )
    _CACHE[key] = (now + _CACHE_TTL, payload)
    return payload


async def _build_dashboard_uncached(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
    process: Optional[str] = None,
    record_snapshot_flag: bool,
) -> Dict[str, Any]:
    if record_snapshot_flag:
        await record_snapshot(
            db,
            entity_code=entity_code,
            period_ym=period_ym,
            department_id=department_id,
            cost_center_id=cost_center_id,
        )
    summary = await build_summary(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
    )
    trends = await build_trends(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    return {
        "as_of": as_of_now(),
        "summary": summary,
        "trends": trends,
        "top_exposure": await top_exposure(
            db,
            entity_code=entity_code,
            period_ym=period_ym,
            department_id=department_id,
            cost_center_id=cost_center_id,
        ),
        "entity_process_matrix": await entity_process_matrix(
            db,
            entity_code=entity_code,
            period_ym=period_ym,
            department_id=department_id,
            cost_center_id=cost_center_id,
        ),
        "ops_linkage": await ops_linkage(
            db,
            entity_code=entity_code,
            period_ym=period_ym,
            department_id=department_id,
            cost_center_id=cost_center_id,
            process=process,
        ),
        "sla_burndown": await sla_burndown(
            db,
            entity_code=entity_code,
            period_ym=period_ym,
            department_id=department_id,
            cost_center_id=cost_center_id,
        ),
        "readiness_correlation": await readiness_correlation(
            db, entity_code=entity_code, period_ym=period_ym
        ),
        "priority_by_type": await priority_by_type_stack(
            db,
            entity_code=entity_code,
            period_ym=period_ym,
            department_id=department_id,
            cost_center_id=cost_center_id,
        ),
        "approver_bottleneck": await approver_bottleneck(
            db,
            entity_code=entity_code,
            period_ym=period_ym,
            department_id=department_id,
            cost_center_id=cost_center_id,
        ),
    }
