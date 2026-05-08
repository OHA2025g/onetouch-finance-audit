"""Phase 3 / Slice 2 — KPI registry + CFO summary mapping.

This service intentionally reuses existing dashboard aggregates so we don't
duplicate KPI math across endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.analytics import cfo_cockpit, cash_conversion_dashboard
from app.services import action_queue_service as aqs
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
            drill_path="/app/cases?status=open&severity=critical",
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
) -> Dict[str, Any]:
    """Return KPI values aligned to `kpi_definitions()` using dashboard/cfo as truth."""
    cockpit = await cfo_cockpit(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
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
) -> Dict[str, Any]:
    """Return a trend series where available (currently readiness trend only)."""
    cockpit = await cfo_cockpit(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    if kpi_id in ("audit_readiness_pct", "readiness"):
        return {
            "kpi_id": "audit_readiness_pct",
            "series": cockpit.get("trends") or [],
            "source": "dashboard/cfo",
            "as_of": as_of_now(),
        }
    return {
        "kpi_id": kpi_id,
        "series": [],
        "source": "dashboard/cfo",
        "as_of": as_of_now(),
        "note": "Trend not implemented for this KPI yet.",
    }


async def kpi_drilldown(
    db,
    kpi_id: str,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Return drill references (exceptions/cases/controls) where available."""
    cockpit = await cfo_cockpit(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    refs: List[Dict[str, Any]] = []
    # Exception-backed drivers (shared top-risk slice is the best stable drill target today).
    exception_kpis = {
        "unresolved_high_risk_exposure",
        "high_critical_open_cases",
        "evidence_completeness_pct",
        "remediation_sla_pct",
        "audit_readiness_pct",
    }
    if kpi_id in exception_kpis:
        for r in (cockpit.get("top_risks") or [])[:10]:
            eid = r.get("id")
            if eid:
                refs.append({"type": "exception", "id": eid, "label": r.get("title")})
    # Control-backed drivers.
    if kpi_id in ("repeat_finding_rate_pct", "audit_readiness_pct"):
        for c in (cockpit.get("top_failing_controls") or [])[:6]:
            code = c.get("code")
            if code:
                refs.append({"type": "control", "id": code, "label": c.get("name")})
    # Critical close tasks — link to the owning cycle in the UI.
    if kpi_id == "close_critical_tasks_open":
        cur = db.close_tasks.find(
            {"critical": True, "status": {"$in": ["draft", "reopened", "submitted"]}},
            {"_id": 0, "id": 1, "title": 1, "cycle_id": 1},
        ).sort("id", 1).limit(15)
        async for t in cur:
            tid = t.get("id")
            if not tid:
                continue
            refs.append(
                {
                    "type": "close_task",
                    "id": tid,
                    "label": t.get("title") or tid,
                    "cycle_id": t.get("cycle_id"),
                }
            )
    return {"kpi_id": kpi_id, "refs": refs, "source": "dashboard/cfo", "as_of": as_of_now()}


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

