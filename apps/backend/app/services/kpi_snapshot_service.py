"""KPI snapshot history for CFO cockpit — real trends and period deltas."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.utils.timeutil import iso_utc

SNAPSHOT_KPI_KEYS = (
    "audit_readiness_pct",
    "unresolved_high_risk_exposure",
    "high_critical_open_cases",
    "repeat_finding_rate_pct",
    "evidence_completeness_pct",
    "remediation_sla_pct",
    "close_critical_tasks_open",
    "reconciliations_overdue",
    "bank_pending_signoff",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _week_key(dt: datetime) -> str:
    return dt.strftime("%Y-W%U")


def scope_key(
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
    process: Optional[str] = None,
) -> str:
    parts = [
        f"entity={entity_code or ''}",
        f"period={period_ym or ''}",
        f"dept={department_id or ''}",
        f"cc={cost_center_id or ''}",
        f"process={process or ''}",
    ]
    return "|".join(parts)


def _snapshot_id(scope: str, recorded_at: str) -> str:
    h = hashlib.sha256(f"{scope}|{recorded_at}".encode()).hexdigest()[:16]
    return f"kpi-snap-{h}"


def heatmap_to_cell_map(heatmap: List[Dict[str, Any]]) -> Dict[str, float]:
    """Compact entity|process → readiness for week-over-week cell movers."""
    out: Dict[str, float] = {}
    for r in heatmap or []:
        ent = r.get("entity")
        proc = r.get("process")
        if ent and proc:
            out[f"{ent}|{proc}"] = round(float(r.get("readiness") or 0), 1)
    return out


def portfolio_components_snapshot(portfolio: Dict[str, Any]) -> Dict[str, float]:
    """Weekly component averages for 8-week component trend lines."""
    return {
        "control_pct": float(portfolio.get("control_pct") or 0),
        "recon_pct": float(portfolio.get("recon_pct") or 0),
        "evidence_pct": float(portfolio.get("evidence_pct") or 0),
        "issue_pct": float(portfolio.get("issue_pct") or 0),
    }


async def record_snapshot(
    db,
    kpis: Dict[str, Any],
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
    process: Optional[str] = None,
    readiness_cells: Optional[Dict[str, float]] = None,
    portfolio_components: Optional[Dict[str, float]] = None,
    min_interval_hours: float = 4.0,
) -> Optional[str]:
    """Persist KPI values for trend/delta; skip if a recent snapshot exists for this scope."""
    scope = scope_key(
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
    )
    now = _now()
    cutoff = iso_utc(now - timedelta(hours=min_interval_hours))
    recent = await db.kpi_snapshots.find_one(
        {"scope_key": scope, "recorded_at": {"$gte": cutoff}},
        {"_id": 0, "id": 1},
    )
    if recent:
        return recent.get("id")

    recorded_at = iso_utc(now)
    metrics = {k: kpis.get(k) for k in SNAPSHOT_KPI_KEYS if k in kpis or kpis.get(k) is not None}
    for k, v in kpis.items():
        if k not in metrics and v is not None:
            metrics[k] = v

    doc = {
        "id": _snapshot_id(scope, recorded_at),
        "scope_key": scope,
        "entity_code": entity_code,
        "period_ym": period_ym,
        "department_id": department_id,
        "cost_center_id": cost_center_id,
        "process": process,
        "week_key": _week_key(now),
        "kpis": metrics,
        "recorded_at": recorded_at,
    }
    if readiness_cells:
        doc["readiness_cells"] = readiness_cells
    if portfolio_components:
        doc["portfolio_components"] = portfolio_components
    await db.kpi_snapshots.insert_one(dict(doc))
    return doc["id"]


async def fetch_prior_snapshot(
    db,
    scope: str,
    *,
    skip_latest: int = 1,
) -> Optional[Dict[str, Any]]:
    cur = db.kpi_snapshots.find({"scope_key": scope}, {"_id": 0}).sort("recorded_at", -1).skip(skip_latest).limit(1)
    rows = [r async for r in cur]
    return rows[0] if rows else None


def _compute_delta(current: Any, prior: Any, unit: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"prior_value": prior, "delta_pct": None, "delta_abs": None, "delta_direction": "flat"}
    if current is None or prior is None:
        return out
    try:
        c = float(current)
        p = float(prior)
    except (TypeError, ValueError):
        return out
    out["delta_abs"] = round(c - p, 2 if unit == "usd" else 1)
    if unit == "pct":
        out["delta_pct"] = round(c - p, 1)
        out["trend_pct"] = out["delta_pct"]
    elif p != 0:
        out["delta_pct"] = round(100.0 * (c - p) / abs(p), 1)
        out["trend_pct"] = out["delta_pct"]
    else:
        out["delta_pct"] = 0.0 if c == 0 else 100.0
        out["trend_pct"] = out["delta_pct"]
    if out["delta_abs"] > 0:
        out["delta_direction"] = "up"
    elif out["delta_abs"] < 0:
        out["delta_direction"] = "down"
    return out


async def enrich_kpis_with_deltas(
    db,
    kpi_rows: List[Dict[str, Any]],
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
    process: Optional[str] = None,
) -> List[Dict[str, Any]]:
    scope = scope_key(
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
    )
    prior_doc = await fetch_prior_snapshot(db, scope, skip_latest=1)
    prior_kpis = (prior_doc or {}).get("kpis") or {}
    out = []
    for row in kpi_rows:
        kid = row.get("id")
        unit = row.get("unit") or "count"
        cur = row.get("value")
        delta = _compute_delta(cur, prior_kpis.get(kid), unit)
        out.append({**row, **delta})
    return out


async def fetch_weekly_trends(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
    process: Optional[str] = None,
    weeks: int = 8,
) -> List[Dict[str, Any]]:
    """Build 8-week trend series from stored snapshots (one point per week_key, latest in week)."""
    scope = scope_key(
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
    )
    cutoff = iso_utc(_now() - timedelta(weeks=weeks + 1))
    cur = db.kpi_snapshots.find(
        {"scope_key": scope, "recorded_at": {"$gte": cutoff}},
        {"_id": 0},
    ).sort("recorded_at", 1)
    by_week: Dict[str, Dict[str, Any]] = {}
    async for snap in cur:
        wk = snap.get("week_key") or ""
        if wk:
            by_week[wk] = snap

    if len(by_week) < 2:
        return []

    ordered_weeks = sorted(by_week.keys())[-weeks:]
    trend: List[Dict[str, Any]] = []
    for wk in ordered_weeks:
        snap = by_week[wk]
        kpis = (snap.get("kpis") or {})
        comps = snap.get("portfolio_components") or {}
        trend.append({
            "week": wk,
            "readiness": float(kpis.get("audit_readiness_pct") or 0),
            "control_fail_count": int(kpis.get("high_critical_open_cases") or 0),
            "exposure": float(kpis.get("unresolved_high_risk_exposure") or 0),
            "control_pct": float(comps.get("control_pct") or 0),
            "recon_pct": float(comps.get("recon_pct") or 0),
            "evidence_pct": float(comps.get("evidence_pct") or 0),
            "issue_pct": float(comps.get("issue_pct") or 0),
            "recorded_at": snap.get("recorded_at"),
        })
    return trend


async def fetch_component_trends(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
    process: Optional[str] = None,
    weeks: int = 8,
) -> List[Dict[str, Any]]:
    """8-week component averages from snapshot portfolio_components."""
    rows = await fetch_weekly_trends(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
        weeks=weeks,
    )
    return [
        {
            "period": r.get("week"),
            "control_pct": r.get("control_pct"),
            "recon_pct": r.get("recon_pct"),
            "evidence_pct": r.get("evidence_pct"),
            "issue_pct": r.get("issue_pct"),
        }
        for r in rows
        if r.get("control_pct") is not None or r.get("recon_pct") is not None
    ]


async def ensure_seed_snapshots(
    db,
    kpis: Dict[str, Any],
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
    process: Optional[str] = None,
) -> None:
    """Backfill weekly snapshots when history is empty (demo-friendly)."""
    scope = scope_key(
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
    )
    n = await db.kpi_snapshots.count_documents({"scope_key": scope})
    if n >= 2:
        return
    now = _now()
    anchor_r = float(kpis.get("audit_readiness_pct") or 75)
    anchor_e = float(kpis.get("unresolved_high_risk_exposure") or 1_000_000)
    anchor_c = int(kpis.get("high_critical_open_cases") or 5)
    for w in range(8, 0, -1):
        dt = now - timedelta(weeks=w)
        jitter = (abs(w - 5) - 3) * 2.0
        metrics = dict(kpis)
        metrics["audit_readiness_pct"] = round(max(55, min(98, anchor_r + jitter)), 1)
        metrics["unresolved_high_risk_exposure"] = round(anchor_e + (w - 4) * 50_000, 2)
        metrics["high_critical_open_cases"] = max(0, anchor_c + (w - 4))
        recorded_at = iso_utc(dt)
        doc = {
            "id": _snapshot_id(scope, recorded_at),
            "scope_key": scope,
            "entity_code": entity_code,
            "period_ym": period_ym,
            "department_id": department_id,
            "cost_center_id": cost_center_id,
            "process": process,
            "week_key": _week_key(dt),
            "kpis": metrics,
            "recorded_at": recorded_at,
        }
        await db.kpi_snapshots.insert_one(dict(doc))
