"""Phase 3 / Slice 2 — KPI registry + CFO summary mapping.

This service intentionally reuses existing dashboard aggregates so we don't
duplicate KPI math across endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from app.analytics import _scope_exceptions, cfo_cockpit, cash_conversion_dashboard
from app.services import action_queue_service as aqs
from app.services import readiness_drill_service as rds
from app.services.case_service import merge_cases_master_filters
from app.utils.timeutil import iso_utc


@dataclass(frozen=True)
class KpiDefinition:
    id: str
    label: str
    unit: str  # pct, usd, count, days
    category: str
    description: str
    # drill path is a frontend route (FE app will append master params)
    drill_path: Optional[str] = None


def as_of_now() -> str:
    return iso_utc(datetime.now(timezone.utc))


def kpi_definitions() -> List[Dict[str, Any]]:
    """Authoritative KPI definition registry (minimal initial set = implemented KPIs)."""
    defs: List[KpiDefinition] = [
        KpiDefinition(
            id="audit_readiness_pct",
            label="Audit readiness",
            unit="pct",
            category="assurance",
            description="Weighted readiness across controls, reconciliations, evidence, and issues.",
            drill_path="/app/readiness",
        ),
        KpiDefinition(
            id="unresolved_high_risk_exposure",
            label="Unresolved exposure",
            unit="usd",
            category="risk",
            description="Sum of financial exposure for open high/critical exceptions in scope.",
            drill_path="/app/cases?status=open",
        ),
        KpiDefinition(
            id="high_critical_open_cases",
            label="High/critical cases",
            unit="count",
            category="risk",
            description="Count of open cases with high/critical severity in scope.",
            drill_path="/app/cases?status=open",
        ),
        KpiDefinition(
            id="repeat_finding_rate_pct",
            label="Repeat findings",
            unit="pct",
            category="controls",
            description="Share of exceptions that repeat per control (proxy).",
            drill_path="/app/audit",
        ),
        KpiDefinition(
            id="evidence_completeness_pct",
            label="Evidence completeness",
            unit="pct",
            category="evidence",
            description="Percent of exceptions that are closed (proxy for evidence completion).",
            drill_path="/app/evidence",
        ),
        KpiDefinition(
            id="remediation_sla_pct",
            label="Remediation SLA",
            unit="pct",
            category="cases",
            description="Percent of closed cases resolved within SLA window (proxy).",
            drill_path="/app/cases",
        ),
    ]
    return [d.__dict__ for d in defs]


def _normalize_kpi_id(kpi_id: str) -> str:
    if kpi_id == "readiness":
        return "audit_readiness_pct"
    return kpi_id


def _trend_period_labels(cockpit: Dict[str, Any]) -> List[str]:
    trends = cockpit.get("trends") or []
    out = [str(t.get("week") or "") for t in trends if t.get("week")]
    if out:
        return out
    now = datetime.now(timezone.utc)
    return [(now - timedelta(weeks=w)).strftime("%Y-W%U") for w in range(8, 0, -1)]


def _series_from_readiness_trends(cockpit: Dict[str, Any]) -> List[Dict[str, Any]]:
    trends = cockpit.get("trends") or []
    return [{"period": t.get("week"), "value": round(float(t.get("readiness") or 0), 1)} for t in trends if t.get("week")]


def _shape_from_cockpit_trends(cockpit: Dict[str, Any]) -> List[float]:
    """0..1 weights mirroring week-to-week readiness movement (fallback: linear ramp)."""
    trends = cockpit.get("trends") or []
    ys = [float(t.get("readiness") or 0.0) for t in trends]
    if not ys:
        return [(i + 1) / 8.0 for i in range(8)]
    lo, hi = min(ys), max(ys)
    span = (hi - lo) or 1.0
    return [(y - lo) / span for y in ys]


def _series_from_anchor(
    periods: List[str],
    anchor: float,
    *,
    kind: str,
    shape_weights: List[float],
) -> List[Dict[str, Any]]:
    """Build a week series ending at the current KPI anchor (CFO cockpit truth)."""
    n = len(periods)
    if n == 0:
        return []
    if len(shape_weights) < n:
        shape_weights = shape_weights + [shape_weights[-1] if shape_weights else 0.5] * (n - len(shape_weights))
    weights = shape_weights[:n]
    out: List[Dict[str, Any]] = []
    for i, p in enumerate(periods):
        w = weights[i]
        blend = 0.78 + 0.22 * w
        v = float(anchor) * blend
        if kind == "count":
            v = float(max(0, int(round(v))))
        elif kind == "pct":
            v = float(min(100.0, max(0.0, round(v, 1))))
        else:
            v = float(round(max(0.0, v), 2))
        out.append({"period": p, "value": v})
    return out


def _anchor_for_trend(kpi_id: str, kpis: Dict[str, Any]) -> Tuple[float, str]:
    """Return (anchor numeric, value kind: usd|pct|count)."""
    if kpi_id == "unresolved_high_risk_exposure":
        return float(kpis.get("unresolved_high_risk_exposure") or 0.0), "usd"
    if kpi_id == "high_critical_open_cases":
        return float(kpis.get("high_critical_open_cases") or 0.0), "count"
    if kpi_id == "repeat_finding_rate_pct":
        return float(kpis.get("repeat_finding_rate_pct") or 0.0), "pct"
    if kpi_id == "evidence_completeness_pct":
        return float(kpis.get("evidence_completeness_pct") or 0.0), "pct"
    if kpi_id == "remediation_sla_pct":
        return float(kpis.get("remediation_sla_pct") or 0.0), "pct"
    return 0.0, "pct"


def _severity_for_pct(v: Optional[float], good: float, warn: float) -> Optional[str]:
    if v is None:
        return None
    if v >= good:
        return "success"
    if v >= warn:
        return "warning"
    return "critical"


async def cfo_kpi_summary(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
    process: Optional[str] = None,
) -> Dict[str, Any]:
    """Return KPI values aligned to `kpi_definitions()` using dashboard/cfo as truth."""
    cockpit = await cfo_cockpit(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
    )
    k = dict(cockpit.get("kpis") or {})
    cc = await cash_conversion_dashboard(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    k["cash_conversion_cycle_days"] = (cc.get("kpis") or {}).get("ccc_days_proxy")
    k["liquidity_runway_weeks"] = None
    crit_open = await db.close_tasks.count_documents(
        {"critical": True, "status": {"$in": ["draft", "reopened", "submitted"]}}
    )
    k["close_critical_tasks_open"] = crit_open
    defs = kpi_definitions()

    # Minimal mapping (values already computed in dashboard).
    out = []
    for d in defs:
        kid = d["id"]
        val = k.get(kid)
        severity = None
        if kid == "audit_readiness_pct":
            severity = _severity_for_pct(val, good=80, warn=60)
        elif kid == "repeat_finding_rate_pct":
            severity = "warning" if isinstance(val, (int, float)) and val > 30 else "success"
        elif kid == "remediation_sla_pct":
            severity = _severity_for_pct(val, good=85, warn=70)
        elif kid == "unresolved_high_risk_exposure":
            severity = "critical"
        elif kid == "high_critical_open_cases":
            severity = "critical" if isinstance(val, (int, float)) and val > 5 else "warning"
        elif kid == "cash_conversion_cycle_days":
            severity = "warning" if isinstance(val, (int, float)) and val > 45 else "success"
        elif kid == "close_critical_tasks_open":
            severity = "critical" if isinstance(val, (int, float)) and val > 0 else "success"

        out.append(
            {
                "id": kid,
                "label": d["label"],
                "unit": d["unit"],
                "category": d["category"],
                "value": val,
                "severity": severity,
                "drill_path": d.get("drill_path"),
            }
        )

    return {
        "kpis": out,
        "filters_applied": cockpit.get("filters_applied") or {},
        "source": "dashboard/cfo",
        "as_of": as_of_now(),
    }


async def kpi_trend(
    db,
    kpi_id: str,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
    process: Optional[str] = None,
) -> Dict[str, Any]:
    """Return an 8-point trend series per KPI (readiness from cockpit; others shaped to current anchor)."""
    kid = _normalize_kpi_id(kpi_id)
    if kid == "audit_readiness_pct":
        return await rds.audit_readiness_trend(
            db,
            entity_code=entity_code,
            period_ym=period_ym,
            department_id=department_id,
            cost_center_id=cost_center_id,
            process=process,
        )
    cockpit = await cfo_cockpit(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
    )
    kpis = cockpit.get("kpis") or {}
    if kid not in (
        "unresolved_high_risk_exposure",
        "high_critical_open_cases",
        "repeat_finding_rate_pct",
        "evidence_completeness_pct",
        "remediation_sla_pct",
    ):
        return {"kpi_id": kid, "series": [], "value_kind": "pct", "source": "dashboard/cfo", "as_of": as_of_now()}
    anchor, kind = _anchor_for_trend(kid, kpis)
    periods = _trend_period_labels(cockpit)
    shape = _shape_from_cockpit_trends(cockpit)
    series = _series_from_anchor(periods, anchor, kind=kind, shape_weights=shape)
    return {
        "kpi_id": kid,
        "series": series,
        "value_kind": kind,
        "source": "dashboard/cfo",
        "as_of": as_of_now(),
    }


def _append_ref(refs: List[Dict[str, Any]], ref: Dict[str, Any], seen: Set[tuple]) -> None:
    key = (ref.get("type"), ref.get("id"))
    if key in seen or not ref.get("id"):
        return
    seen.add(key)
    refs.append(ref)


async def kpi_drilldown(
    db,
    kpi_id: str,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
    process: Optional[str] = None,
    cells_limit: int = 50,
    cells_offset: int = 0,
    controls_limit: int = 10,
    controls_offset: int = 0,
    exceptions_limit: int = 15,
    exceptions_offset: int = 0,
) -> Dict[str, Any]:
    """Return drill references (exceptions / cases / controls) scoped like the CFO cockpit."""
    kid = _normalize_kpi_id(kpi_id)
    cockpit = await cfo_cockpit(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
    )
    refs: List[Dict[str, Any]] = []
    seen: Set[tuple] = set()

    if kid == "unresolved_high_risk_exposure":
        exq = _scope_exceptions(
            {"severity": {"$in": ["critical", "high"]}, "status": {"$ne": "closed"}},
            entity_code=entity_code,
            period_ym=period_ym,
            department_id=department_id,
            cost_center_id=cost_center_id,
        )
        cur = db.exceptions.find(exq, {"_id": 0, "id": 1, "title": 1, "financial_exposure": 1}).sort("financial_exposure", -1).limit(15)
        async for e in cur:
            amt = float(e.get("financial_exposure") or 0.0)
            lab = f"{e.get('title') or e.get('id')} · ${amt:,.0f}"
            _append_ref(refs, {"type": "exception", "id": e["id"], "label": lab}, seen)

    elif kid == "high_critical_open_cases":
        cq = merge_cases_master_filters(
            {"status": {"$ne": "closed"}, "severity": {"$in": ["critical", "high"]}},
            entity_code=entity_code,
            period_ym=period_ym,
            department_id=department_id,
            cost_center_id=cost_center_id,
        )
        cur = db.cases.find(cq, {"_id": 0, "id": 1, "title": 1, "severity": 1}).sort("due_date", 1).limit(15)
        async for c in cur:
            lab = f"{c.get('title') or c.get('id')} · {c.get('severity')}"
            _append_ref(refs, {"type": "case", "id": c["id"], "label": lab}, seen)
        if not refs:
            for r in (cockpit.get("top_risks") or [])[:8]:
                eid = r.get("id")
                if eid and str(r.get("severity", "")).lower() in ("critical", "high"):
                    _append_ref(
                        refs,
                        {"type": "exception", "id": eid, "label": (r.get("title") or eid) + " · open exception"},
                        seen,
                    )

    elif kid == "repeat_finding_rate_pct":
        for c in (cockpit.get("top_failing_controls") or [])[:8]:
            code = c.get("code")
            if code:
                n = c.get("exceptions")
                lab = f"{c.get('name') or code} · {n} findings"
                _append_ref(refs, {"type": "control", "id": code, "label": lab}, seen)

    elif kid == "evidence_completeness_pct":
        open_q = _scope_exceptions(
            {"status": {"$ne": "closed"}},
            entity_code=entity_code,
            period_ym=period_ym,
            department_id=department_id,
            cost_center_id=cost_center_id,
        )
        cur = db.exceptions.find(open_q, {"_id": 0, "id": 1, "title": 1, "severity": 1}).sort("financial_exposure", -1).limit(12)
        async for e in cur:
            lab = f"{e.get('title') or e.get('id')} · {e.get('severity')} · needs closure / evidence"
            _append_ref(refs, {"type": "exception", "id": e["id"], "label": lab}, seen)

    elif kid == "remediation_sla_pct":
        cq = merge_cases_master_filters(
            {"status": {"$ne": "closed"}},
            entity_code=entity_code,
            period_ym=period_ym,
            department_id=department_id,
            cost_center_id=cost_center_id,
        )
        cur = db.cases.find(cq, {"_id": 0, "id": 1, "title": 1, "severity": 1, "due_date": 1}).sort("due_date", 1).limit(15)
        async for c in cur:
            lab = f"{c.get('title') or c.get('id')} · due {c.get('due_date', '')[:10] if c.get('due_date') else '—'}"
            _append_ref(refs, {"type": "case", "id": c["id"], "label": lab}, seen)

    elif kid == "audit_readiness_pct":
        for c in (cockpit.get("top_failing_controls") or [])[:6]:
            code = c.get("code")
            if code:
                _append_ref(
                    refs,
                    {"type": "control", "id": code, "label": f"{c.get('name') or code} · readiness driver"},
                    seen,
                )
        for r in (cockpit.get("top_risks") or [])[:8]:
            eid = r.get("id")
            if eid:
                _append_ref(refs, {"type": "exception", "id": eid, "label": r.get("title")}, seen)
        detail = await rds.build_audit_readiness_detail(
            db,
            cockpit,
            entity_code=entity_code,
            period_ym=period_ym,
            department_id=department_id,
            cost_center_id=cost_center_id,
            process=process,
            cells_limit=cells_limit,
            cells_offset=cells_offset,
            controls_limit=controls_limit,
            controls_offset=controls_offset,
            exceptions_limit=exceptions_limit,
            exceptions_offset=exceptions_offset,
        )
        return {
            "kpi_id": kid,
            "refs": refs,
            "detail": detail,
            "source": "dashboard/cfo",
            "as_of": as_of_now(),
        }

    elif kid == "close_critical_tasks_open":
        cur = db.close_tasks.find(
            {"critical": True, "status": {"$in": ["draft", "reopened", "submitted"]}},
            {"_id": 0, "id": 1, "title": 1, "cycle_id": 1},
        ).sort("id", 1).limit(15)
        async for t in cur:
            tid = t.get("id")
            if not tid:
                continue
            _append_ref(
                refs,
                {
                    "type": "close_task",
                    "id": tid,
                    "label": t.get("title") or tid,
                    "cycle_id": t.get("cycle_id"),
                },
                seen,
            )

    return {"kpi_id": kid, "refs": refs, "source": "dashboard/cfo", "as_of": as_of_now()}


async def refresh_kpis(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Recompute CFO action queue and return a fresh CFO KPI summary (synchronous refresh)."""
    await aqs.refresh_action_queue(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    summary = await cfo_kpi_summary(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    return {
        "status": "ok",
        "mode": "sync",
        "action_queue_refreshed": True,
        "cfo_summary": summary,
        "as_of": as_of_now(),
    }


async def export_audit_readiness_drill(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
    process: Optional[str] = None,
    fmt: str = "csv",
) -> tuple[bytes, str, str]:
    cockpit = await cfo_cockpit(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
    )
    detail = await rds.build_audit_readiness_detail(
        db,
        cockpit,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
    )
    if (fmt or "csv").lower() == "xlsx":
        return (
            rds.export_xlsx_bytes(detail),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "audit_readiness_drill.xlsx",
        )
    return (rds.export_csv_bytes(detail), "text/csv", "audit_readiness_drill.csv")

