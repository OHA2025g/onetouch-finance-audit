"""CFO executive briefing — data-driven narrative (weighted ML scoring, no LLM)."""

from __future__ import annotations

import math
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.services.kpi_service import as_of_now

MODEL_ID = "onetouch-cfo-ml-v1"

# Learned-style weights (composite risk model; higher = worse)
FEATURE_WEIGHTS = {
    "readiness_gap": 0.28,
    "exposure_norm": 0.22,
    "cases_norm": 0.18,
    "repeat_norm": 0.12,
    "evidence_gap": 0.10,
    "sla_gap": 0.10,
    "trend_readiness_down": 0.08,
    "trend_exposure_up": 0.12,
    "alert_density": 0.15,
    "ops_pressure": 0.10,
}


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _norm_pct(v: Any, invert: bool = False) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        x = 50.0
    x = _clamp(x, 0.0, 100.0)
    return (100.0 - x) / 100.0 if invert else x / 100.0


def _norm_log_usd(v: Any, cap: float = 250_000_000.0) -> float:
    try:
        x = max(0.0, float(v))
    except (TypeError, ValueError):
        x = 0.0
    if x <= 0:
        return 0.0
    return _clamp(math.log10(x + 1.0) / math.log10(cap + 1.0), 0.0, 1.0)


def _norm_count(v: Any, cap: float = 50.0) -> float:
    try:
        x = max(0.0, float(v))
    except (TypeError, ValueError):
        x = 0.0
    return _clamp(x / cap, 0.0, 1.0)


def _trend_slope(series: List[Dict[str, Any]], key: str) -> float:
    """Simple least-squares slope over index (ML trend feature)."""
    ys = [float(p.get(key) or 0) for p in series if p.get(key) is not None]
    n = len(ys)
    if n < 2:
        return 0.0
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n))
    den = sum((xs[i] - mean_x) ** 2 for i in range(n)) or 1.0
    return num / den


def _composite_risk_score(features: Dict[str, float]) -> float:
    raw = sum(FEATURE_WEIGHTS.get(k, 0.0) * features.get(k, 0.0) for k in FEATURE_WEIGHTS)
    # Squash to 0–1 (logistic-style calibration)
    return 1.0 / (1.0 + math.exp(-6.0 * (raw - 0.45)))


def _risk_band(score: float) -> str:
    if score >= 0.75:
        return "critical"
    if score >= 0.55:
        return "elevated"
    if score >= 0.35:
        return "moderate"
    return "stable"


def _citation(
    *,
    source_type: str,
    source_id: str,
    label: str,
    snippet: str,
    app_path: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "source_type": source_type,
        "source_id": source_id,
        "label": label,
        "snippet": snippet[:220],
        "app_path": app_path,
    }


def _worst_heatmap_cell(heatmap: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not heatmap:
        return None
    return min(heatmap, key=lambda r: float(r.get("readiness") or 100))


def _exposure_limit_for_severity(severity: str) -> float:
    s = (severity or "").lower()
    if s == "critical":
        return 1_500_000.0
    if s == "high":
        return 1_500_000.0
    if s == "medium":
        return 500_000.0
    return 250_000.0


def _format_risk_driver(r: Dict[str, Any], ref_num: int) -> str:
    proc = r.get("process") or "Process"
    title = (r.get("title") or "Open exception").strip()
    sev = (r.get("severity") or "n/a").lower()
    exp = float(r.get("financial_exposure") or 0)
    limit = _exposure_limit_for_severity(sev)
    if exp > 0 and exp >= limit * 0.5:
        detail = f"{title} exposure ${exp:,.0f} over ${limit:,.0f} limit ({sev} severity)"
    else:
        detail = f"{title} ({sev} severity)"
    return f"[#{ref_num}] {proc}: {detail}"


def _format_control_driver(c: Dict[str, Any], ref_num: int) -> str:
    code = c.get("code") or "control"
    return f"[#{ref_num}] Control {code} accounts for {int(c.get('exceptions') or 0)} open exceptions"


def build_executive_narrative_ml(
    *,
    cockpit: Dict[str, Any],
    alerts: List[Dict[str, Any]],
    ops_kpis: Optional[List[Dict[str, Any]]] = None,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    process: Optional[str] = None,
    action_queue_summary: Optional[Dict[str, Any]] = None,
    top_queue_items: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Produce committee-ready narrative + citations from cockpit telemetry only."""
    k = cockpit.get("kpis") or {}
    trends = cockpit.get("trends") or []
    top_risks = cockpit.get("top_risks") or []
    top_controls = cockpit.get("top_failing_controls") or []
    heatmap = cockpit.get("heatmap") or []
    ops = ops_kpis or []

    readiness = float(k.get("audit_readiness_pct") or 0)
    exposure = float(k.get("unresolved_high_risk_exposure") or 0)
    cases = float(k.get("high_critical_open_cases") or 0)
    repeat = float(k.get("repeat_finding_rate_pct") or 0)
    evidence = float(k.get("evidence_completeness_pct") or 0)
    sla = float(k.get("remediation_sla_pct") or 0)

    slope_r = _trend_slope(trends, "readiness")
    slope_e = _trend_slope(trends, "exposure")

    ops_pressure = 0.0
    for o in ops:
        try:
            v = float(o.get("value") or 0)
        except (TypeError, ValueError):
            v = 0
        if o.get("id") == "reconciliations_overdue" and v > 0:
            ops_pressure += min(1.0, v / 5.0) * 0.4
        if o.get("id") == "close_critical_tasks_open" and v > 0:
            ops_pressure += 0.35
        if o.get("id") == "bank_pending_signoff" and v > 0:
            ops_pressure += min(1.0, v / 3.0) * 0.25
    ops_pressure = _clamp(ops_pressure, 0.0, 1.0)

    features = {
        "readiness_gap": _norm_pct(readiness, invert=True),
        "exposure_norm": _norm_log_usd(exposure),
        "cases_norm": _norm_count(cases, cap=30.0),
        "repeat_norm": _norm_pct(repeat, invert=False),
        "evidence_gap": _norm_pct(evidence, invert=True),
        "sla_gap": _norm_pct(sla, invert=True),
        "trend_readiness_down": _clamp(-slope_r / 5.0, 0.0, 1.0) if slope_r < 0 else 0.0,
        "trend_exposure_up": _clamp(slope_e / 500_000.0, 0.0, 1.0) if slope_e > 0 else 0.0,
        "alert_density": _clamp(len(alerts) / 6.0, 0.0, 1.0),
        "ops_pressure": ops_pressure,
    }
    risk_score = _composite_risk_score(features)
    band = _risk_band(risk_score)

    citations: List[Dict[str, Any]] = []
    drivers: List[str] = []

    scope_lbl = entity_code or "enterprise"
    period_lbl = period_ym or "current period"
    proc_lbl = f" · {process}" if process else ""

    for i, r in enumerate(top_risks[:3]):
        cid = str(r.get("id") or f"risk-{i}")
        citations.append(
            _citation(
                source_type="exception",
                source_id=cid,
                label=f"{r.get('control_code', '')} — {r.get('title', 'Open exception')[:60]}",
                snippet=f"{r.get('severity', '').upper()} · {r.get('entity', '')} · exposure ${float(r.get('financial_exposure') or 0):,.0f}",
                app_path=f"/app/evidence/{cid}",
            )
        )
        drivers.append(_format_risk_driver(r, len(citations)))

    for i, c in enumerate(top_controls[:2]):
        code = str(c.get("code") or f"ctrl-{i}")
        citations.append(
            _citation(
                source_type="control",
                source_id=code,
                label=f"{code} — {c.get('name', 'Control')[:50]}",
                snippet=f"{int(c.get('exceptions') or 0)} open exceptions · {c.get('process', '')}",
                app_path=f"/app/drill/control/{code}",
            )
        )
        drivers.append(_format_control_driver(c, len(citations)))

    worst = _worst_heatmap_cell(heatmap)
    if worst:
        ent = worst.get("entity", "")
        proc = worst.get("process", "")
        citations.append(
            _citation(
                source_type="readiness",
                source_id=f"{ent}|{proc}",
                label=f"Lowest readiness: {proc} @ {ent}",
                snippet=f"Readiness {worst.get('readiness')}% · open high {worst.get('open_high', 0)} · exposure ${float(worst.get('exposure') or 0):,.0f}",
                app_path=f"/app/cases?process={proc}&entity={ent}",
            )
        )
        drivers.append(f"[#{len(citations)}] Weakest process×entity cell: {proc} / {ent} at {worst.get('readiness')}% readiness")

    for a in alerts[:3]:
        citations.append(
            _citation(
                source_type="kpi_alert",
                source_id=str(a.get("id") or a.get("code")),
                label=a.get("title", "Threshold alert"),
                snippet=a.get("message", ""),
                app_path=a.get("href"),
            )
        )

    for qi in (top_queue_items or [])[:3]:
        qid = str(qi.get("id") or "")
        if not qid:
            continue
        citations.append(
            _citation(
                source_type="cfo_action",
                source_id=qid,
                label=(qi.get("title") or "Queue item")[:80],
                snippet=f"{qi.get('priority', '')} · {qi.get('type', '')} · {qi.get('status', '')}",
                app_path=f"/app/cfo-action-queue?action_id={qid}",
            )
        )
        drivers.append(
            f"[#{len(citations)}] Queue: {(qi.get('title') or qid)[:70]} ({qi.get('priority', '')})"
        )

    trend_txt = ""
    if len(trends) >= 2:
        if slope_r > 0.5:
            trend_txt = " Readiness trend is improving week over week."
        elif slope_r < -0.5:
            trend_txt = " Readiness has declined over the last several weeks."
        if slope_e > 100_000:
            trend_txt += " Unresolved exposure is trending upward."

    scope_title = f"Executive briefing for {scope_lbl} ({period_lbl}{proc_lbl})"
    queue_txt = ""
    qs = action_queue_summary or {}
    if qs.get("open_total") is not None:
        queue_txt = (
            f" The CFO action queue has {int(qs.get('open_total') or 0)} open items"
            f" ({int(qs.get('p0_open') or 0)} P0) with ${float(qs.get('queue_exposure_usd') or 0):,.0f} exposure in-queue."
        )
    summary_body = (
        f"Our composite assurance risk score is {risk_score:.0%} ({band} band). "
        f"Audit readiness stands at {readiness:.1f}% with ${exposure:,.0f} in unresolved high/critical exposure "
        f"across {int(cases)} open high/critical cases. Remediation SLA is {sla:.1f}% and evidence completeness is {evidence:.1f}%."
        f"{trend_txt}{queue_txt}"
    )
    p1 = f"{scope_title}. {summary_body}"

    driver_lines = drivers[:5] if drivers else ["No material open drivers in the current scope."]
    p2 = "Primary drivers ranked by model impact:\n" + "\n".join(f"• {d}" for d in driver_lines)

    actions: List[str] = []
    if band in ("critical", "elevated"):
        actions.append("Escalate top exposure items to the audit committee pre-read.")
    if readiness < 70:
        actions.append("Require process owners to sign off readiness gaps below 70% before close.")
    if any(o.get("id") == "reconciliations_overdue" and float(o.get("value") or 0) > 0 for o in ops):
        actions.append("Clear overdue reconciliations to unlock R2R/Treasury readiness components.")
    if any(o.get("id") == "close_critical_tasks_open" and float(o.get("value") or 0) > 0 for o in ops):
        actions.append("Close critical month-end tasks blocking sign-off.")
    if repeat > 40:
        actions.append("Target repeat findings with root-cause remediation on top failing controls.")
    if not actions:
        actions.append("Maintain current control cadence; continue monitoring weekly snapshot deltas.")

    needs_review = band in ("critical", "elevated") or readiness < 65 or exposure >= 50_000_000
    action_review = (
        "Committee or CFO sign-off recommended before period close." if needs_review else None
    )
    action_footer = f"\n\nACTION_REVIEW: {action_review}" if action_review else ""

    p3 = "Recommended actions:\n" + "\n".join(f"• {a}" for a in actions[:5]) + action_footer

    answer = f"{p1}\n\n{p2}\n\n{p3}"
    confidence = _clamp(0.55 + 0.35 * (1.0 - risk_score) + 0.05 * min(len(citations), 5), 0.35, 0.95)

    return {
        "session_id": str(uuid.uuid4()),
        "question": "ML executive briefing",
        "answer": answer,
        "sections": {
            "scope_title": scope_title,
            "summary": summary_body.strip(),
            "risk_score_pct": round(risk_score * 100, 1),
            "risk_band": band,
            "drivers": driver_lines,
            "actions": actions[:5],
            "action_review": action_review,
            "queue_summary": qs if qs else None,
        },
        "confidence": round(confidence, 2),
        "model": MODEL_ID,
        "citations": citations,
        "needs_human_review": needs_review,
        "created_at": as_of_now(),
        "mode": "cfo_ml",
        "ml_meta": {
            "risk_score": round(risk_score, 4),
            "risk_band": band,
            "features": {k: round(v, 4) for k, v in features.items()},
            "algorithm": "weighted_logistic_composite + OLS trend slopes",
        },
    }
