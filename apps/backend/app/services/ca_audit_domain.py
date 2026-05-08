"""Domain logic: materiality benchmarks, audit opinion, continuous assurance scoring."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# Keys returned by compute_benchmark_options — labels for API / UI.
_MATERIALITY_BENCHMARK_META: Dict[str, Tuple[str, float]] = {
    "five_pct_pbt": ("5% of profit before tax", 0.05),
    "one_pct_revenue": ("1% of revenue", 0.01),
    "one_pct_assets": ("1% of total assets", 0.01),
    "half_pct_expenses": ("0.5% of gross expenses", 0.005),
}


def compute_benchmark_options(row: Dict[str, Any]) -> Dict[str, float]:
    """Return candidate materiality amounts from common CA benchmarks."""
    pbt = float(row.get("profit_before_tax") or 0)
    rev = float(row.get("revenue") or 0)
    assets = float(row.get("total_assets") or 0)
    exp = float(row.get("gross_expenses") or 0)
    return {
        "five_pct_pbt": max(0.0, 0.05 * abs(pbt)),
        "one_pct_revenue": max(0.0, 0.01 * abs(rev)),
        "one_pct_assets": max(0.0, 0.01 * abs(assets)),
        "half_pct_expenses": max(0.0, 0.005 * abs(exp)),
    }


def select_default_benchmark(options: Dict[str, float]) -> Tuple[str, float]:
    """Pick the benchmark with the lowest positive value (typical planning heuristic for demo)."""
    positive = [(k, v) for k, v in options.items() if v and v > 0]
    if not positive:
        return ("five_pct_pbt", 0.0)
    k, v = min(positive, key=lambda x: x[1])
    return k, v


def derive_performance_and_trivial(final_materiality: float) -> Tuple[float, float, float]:
    """Performance materiality band 50–75% of final; trivial = 5% of final."""
    if final_materiality <= 0:
        return 0.0, 0.0, 0.0
    perf_low = 0.50 * final_materiality
    perf_high = 0.75 * final_materiality
    trivial = 0.05 * final_materiality
    return perf_low, perf_high, trivial


def build_materiality_benchmarks(options: Dict[str, float], selected_key: str) -> List[Dict[str, Any]]:
    """Structured benchmark rows for the Materiality Engine API."""
    rows: List[Dict[str, Any]] = []
    for key, amount in sorted(options.items(), key=lambda x: x[0]):
        meta = _MATERIALITY_BENCHMARK_META.get(key, (key.replace("_", " "), 0.0))
        label, rule_pct = meta[0], meta[1]
        rows.append(
            {
                "key": key,
                "label": label,
                "rule_pct": rule_pct,
                "amount": round(float(amount), 2),
                "selected": key == selected_key,
            }
        )
    return rows


def performance_materiality_payload(
    low: float, high: float, mid: float, final_materiality: float
) -> Dict[str, Any]:
    return {
        "low": round(float(low), 2),
        "high": round(float(high), 2),
        "mid": round(float(mid), 2),
        "basis_note": "Performance materiality is set at 50–75% of overall materiality for designing substantive procedures.",
        "of_overall_pct_range": "50%–75%",
        "overall_materiality": round(float(final_materiality), 2),
    }


def clearly_trivial_payload(amount: float, final_materiality: float) -> Dict[str, Any]:
    pct = 0.05 if final_materiality else 0.0
    return {
        "amount": round(float(amount), 2),
        "pct_of_final": pct,
        "basis_note": "Clearly trivial misstatements are often capped around 5% of overall materiality; items below this may not require adjustment.",
    }


def materiality_impact_explanation(
    final_m: float,
    perf_mid: float,
    trivial: float,
    override_applied: bool,
) -> str:
    if final_m <= 0:
        return "Enter financial benchmarks and calculate materiality to establish planning thresholds."
    parts = [
        f"Overall planning materiality is {final_m:,.2f}.",
        f"Substantive procedures are typically designed using performance materiality near {perf_mid:,.2f} (midpoint of 50–75% of overall).",
        f"Misstatements below {trivial:,.2f} are often treated as clearly trivial unless qualitative factors apply.",
    ]
    if override_applied:
        parts.append("A manual override is applied; document the rationale in the workpapers.")
    return " ".join(parts)


def materiality_assessment_payload(
    engagement_id: str,
    record_id: str,
    row: Dict[str, Any],
    benchmarks: List[Dict[str, Any]],
    performance: Dict[str, Any],
    trivial: Dict[str, Any],
    explanation: str,
) -> Dict[str, Any]:
    calc = float(row.get("calculated_materiality") or 0)
    final_m = float(row.get("final_materiality") or 0)
    override_amt = row.get("override_amount")
    override_applied = override_amt is not None and abs(float(override_amt or 0) - calc) > 1e-6
    return {
        "engagement_id": engagement_id,
        "materiality_record_id": record_id,
        "benchmark_selected": row.get("benchmark_selected") or "",
        "calculated_materiality": round(calc, 2),
        "final_materiality": round(final_m, 2),
        "override_applied": bool(override_applied),
        "override_amount": float(override_amt) if override_amt is not None else None,
        "override_reason": row.get("override_reason"),
        "approval_status": row.get("approval_status") or "draft",
        "prepared_by": row.get("prepared_by"),
        "reviewed_by": row.get("reviewed_by"),
        "approved_by": row.get("approved_by"),
        "benchmarks": benchmarks,
        "performance_materiality": performance,
        "clearly_trivial_threshold": trivial,
        "impact_explanation": explanation,
    }


def flag_exceptions_against_materiality(
    exceptions: List[Dict[str, Any]], final_materiality: float, trivial_threshold: float
) -> List[Dict[str, Any]]:
    """Mark exceptions whose financial exposure exceeds trivial or overall materiality."""
    fm = float(final_materiality or 0)
    tr = float(trivial_threshold or 0)
    out: List[Dict[str, Any]] = []
    for ex in exceptions:
        fe = float(ex.get("financial_exposure") or 0)
        ex_overall = fm > 0 and fe >= fm
        ex_trivial = tr > 0 and fe >= tr
        hint = "high" if ex_overall else ("watch" if ex_trivial else "below_trivial")
        out.append(
            {
                "exception_id": ex.get("id"),
                "summary": ex.get("summary") or ex.get("title") or ex.get("source_record_ref"),
                "financial_exposure": round(fe, 2),
                "exceeds_overall_materiality": ex_overall,
                "exceeds_trivial_threshold": ex_trivial,
                "severity_hint": hint,
            }
        )
    out.sort(key=lambda x: x["financial_exposure"], reverse=True)
    return out


def enrich_materiality_record(
    row: Dict[str, Any],
    engagement_id: str,
    exceptions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Attach engine view-models to a stored ca_materiality document."""
    out = dict(row)
    opts = dict(row.get("benchmark_options") or {})
    if not opts:
        opts = compute_benchmark_options(row)
    sel = row.get("benchmark_selected") or select_default_benchmark(opts)[0]
    if sel not in opts:
        sel, _ = select_default_benchmark(opts)
    benchmarks = build_materiality_benchmarks(opts, sel)
    fm = float(row.get("final_materiality") or 0)
    lo = float(row.get("performance_materiality_low") or 0)
    hi = float(row.get("performance_materiality_high") or 0)
    mid = float(row.get("performance_materiality") or 0.0)
    if not mid and (lo or hi):
        mid = (lo + hi) / 2.0
    trivial_amt = float(row.get("trivial_threshold") or 0)
    override_amt = row.get("override_amount")
    calc_amt = float(row.get("calculated_materiality") or 0)
    override_applied = override_amt is not None and abs(float(override_amt or 0) - calc_amt) > 1e-6
    perf = performance_materiality_payload(lo, hi, mid, fm)
    trivial = clearly_trivial_payload(trivial_amt, fm)
    expl = materiality_impact_explanation(fm, mid, trivial_amt, override_applied)
    rid = row.get("id") or ""
    out["benchmarks"] = benchmarks
    out["performance_materiality"] = perf
    out["clearly_trivial_threshold"] = trivial
    out["materiality_assessment"] = materiality_assessment_payload(
        engagement_id, rid, row, benchmarks, perf, trivial, expl
    )
    out["impact_explanation"] = expl
    if exceptions is not None:
        out["exception_materiality_flags"] = flag_exceptions_against_materiality(exceptions, fm, trivial_amt)
    return out


def risk_scores(likelihood: int, impact: int, control_eff: Optional[int]) -> Dict[str, Any]:
    inherent = likelihood * impact
    residual = inherent
    if control_eff is not None:
        residual = max(1, int(round(inherent * (control_eff / 5.0))))
    rating = "low"
    if inherent >= 15 or residual >= 12:
        rating = "critical"
    elif inherent >= 10 or residual >= 8:
        rating = "high"
    elif inherent >= 6 or residual >= 5:
        rating = "medium"
    return {"inherent_risk_score": inherent, "residual_risk_score": residual, "risk_rating": rating}


def suggest_opinion(observations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Rule-based opinion suggestion from observations."""
    unresolved = [o for o in observations if not o.get("resolved")]
    material = [o for o in unresolved if o.get("material")]
    pervasive = any(o.get("pervasive") for o in material)
    disclaimer = any(o.get("source") == "manual" and "evidence" in (o.get("title") or "").lower() for o in unresolved)

    if disclaimer and len(material) >= 2:
        kind = "disclaimer"
        rationale = "Insufficient appropriate audit evidence indicated for multiple areas."
    elif pervasive:
        kind = "adverse"
        rationale = "Material and pervasive misstatements or scope limitations."
    elif len(material) >= 1:
        kind = "qualified"
        rationale = "Material but not pervasive issues remain unresolved."
    else:
        kind = "unqualified"
        rationale = "No unresolved material issues detected in linked observations."
    return {"suggested_opinion": kind, "rationale": rationale, "counts": {"unresolved": len(unresolved), "material": len(material)}}


def continuous_assurance_scores(
    engagement: Dict[str, Any],
    risks: List[Dict[str, Any]],
    materiality: Optional[Dict[str, Any]],
    exceptions: List[Dict[str, Any]],
    cases_open: int,
    compliance_pct: float,
    wp_signed_pct: float,
) -> Dict[str, Any]:
    """Heuristic 0–100 scores for executive dashboards."""
    risk_high = sum(1 for r in risks if r.get("risk_rating") in ("high", "critical"))
    risk_score = max(0.0, 100.0 - min(100.0, risk_high * 12.0))

    control_eff_scores = [r.get("control_effectiveness_score") or 3 for r in risks]
    ctrl_avg = sum(control_eff_scores) / max(1, len(control_eff_scores))
    control_effectiveness_score = min(100.0, max(0.0, ctrl_avg / 5.0 * 100.0))

    compliance_score = max(0.0, min(100.0, compliance_pct))
    evidence_score = max(0.0, min(100.0, wp_signed_pct))

    mat = float(materiality.get("final_materiality") or 0) if materiality else 0.0
    flagged = 0
    for ex in exceptions:
        try:
            fe = float(ex.get("financial_exposure") or 0)
            if mat and fe >= mat:
                flagged += 1
        except (TypeError, ValueError):
            continue
    fraud_risk_score = max(0.0, 100.0 - min(100.0, flagged * 15.0 + risk_high * 5.0))
    fs_risk_score = max(0.0, 100.0 - min(100.0, flagged * 10.0 + (100.0 - compliance_score) * 0.3))

    readiness = (
        0.25 * risk_score
        + 0.20 * control_effectiveness_score
        + 0.20 * compliance_score
        + 0.20 * evidence_score
        + 0.15 * fs_risk_score
    )
    overall = (readiness + control_effectiveness_score + compliance_score + evidence_score + fraud_risk_score + fs_risk_score) / 6.0

    return {
        "audit_readiness_score": round(readiness, 1),
        "control_effectiveness_score": round(control_effectiveness_score, 1),
        "compliance_score": round(compliance_score, 1),
        "evidence_completeness_score": round(evidence_score, 1),
        "fraud_risk_score": round(fraud_risk_score, 1),
        "financial_statement_risk_score": round(fs_risk_score, 1),
        "continuous_assurance_score": round(overall, 1),
        "engagement_status": engagement.get("status"),
        "risk_level": engagement.get("risk_level"),
    }


def default_wp_folders() -> List[Dict[str, Any]]:
    names = [
        "Planning",
        "Risk Assessment",
        "Financial Statements",
        "Controls Testing",
        "Substantive Testing",
        "Compliance",
        "Reporting",
    ]
    return [{"id": f"fld-{i+1}", "name": n, "parent_id": None} for i, n in enumerate(names)]
