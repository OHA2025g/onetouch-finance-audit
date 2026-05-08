"""CFO-facing advisory copy: deterministic narratives from engagement telemetry (AI-style, no external call required)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def _bullets(items: List[str], max_n: int = 6) -> List[str]:
    return [x for x in items if x][:max_n]


def build_advisory_narratives(
    engagement: Dict[str, Any],
    risks: List[Dict[str, Any]],
    open_cases: List[Dict[str, Any]],
    deficiencies: List[Dict[str, Any]],
    observations: List[Dict[str, Any]],
    compliance_reqs: List[Dict[str, Any]],
    materiality: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Produce CFO-language sections for dashboards and packs."""
    entity = engagement.get("entity_name") or "the company"
    fy = engagement.get("financial_year") or ""

    risk_lines = [
        f"{r.get('risk_title') or r.get('title', 'Risk')} — rated {r.get('risk_rating', 'n/a')} ({r.get('process_area', 'process')} · {r.get('financial_statement_area', 'FS')})"
        for r in risks[:12]
    ]
    if not risk_lines:
        risk_lines = ["No registered inherent risks — confirm RACM completeness for this engagement."]

    ctrl_lines = []
    for d in deficiencies[:8]:
        ctrl_lines.append(f"Address {d.get('title') or d.get('description', 'deficiency')[:80]} — owner action and retest date.")
    if not ctrl_lines:
        ctrl_lines.append("No open control deficiencies logged — maintain testing evidence for key SOX/IFC assertions.")

    cost_hints = []
    if len(open_cases) > 5:
        cost_hints.append("High case volume often correlates with manual exception handling — automate reconciliations and tighten cut-off.")
    if any((r.get("risk_rating") in ("high", "critical")) for r in risks):
        cost_hints.append("Elevated fraud/process risks: consider targeted analytics subscriptions and shared service controls to reduce repeat findings.")
    if not cost_hints:
        cost_hints.append("Review duplicate vendor masters and payment run approvals to reduce leakage and rework.")

    mat_amt = (materiality or {}).get("final_materiality")
    mgmt_letter = (
        f"Dear Management,\n\nFollowing our audit of {entity} for FY {fy}, we highlight themes for governance follow-up:\n"
        + "\n".join(f"• {o.get('title', 'Observation')}" for o in observations[:8] if not o.get("resolved"))
        or "• No open formal observations — continue quarterly control self-certification and variance reviews.\n"
    )
    mgmt_letter += (
        f"\n\nMateriality context: overall planning threshold is {mat_amt if mat_amt is not None else 'TBD'} "
        "(see materiality working paper for benchmarks and overrides).\n\nYours sincerely,\nStatutory Auditor (draft)"
    )

    nc = [r for r in compliance_reqs if r.get("status") == "non-compliant"]
    cfo_findings: List[str] = []
    for o in observations[:6]:
        if o.get("resolved"):
            continue
        sev = o.get("severity", "medium")
        cfo_findings.append(
            f"{o.get('title', 'Item')}: what it means for you — severity {sev}. "
            f"{'Action: agree remediation timeline with audit committee.' if sev in ('high', 'critical') else 'Monitor through management reporting.'}"
        )
    for c in open_cases[:4]:
        cfo_findings.append(
            f"Case {c.get('id', '')[:8]}… ({c.get('status', 'open')}): operational follow-up; ensure root cause and control fix are documented."
        )
    for r in nc[:4]:
        cfo_findings.append(f"Compliance: {r.get('title', 'Requirement')[:100]} — status non-compliant; evidence and disclosure gap to close.")

    if not cfo_findings:
        cfo_findings.append("No material open items surfaced in this snapshot — suitable for a clean audit committee briefing.")

    return {
        "key_risks_summary": _bullets(risk_lines, 8),
        "control_improvements": _bullets(ctrl_lines, 8),
        "cost_optimization": _bullets(cost_hints, 6),
        "management_letter_draft": mgmt_letter.strip(),
        "findings_cfo_language": _bullets(cfo_findings, 10),
    }
