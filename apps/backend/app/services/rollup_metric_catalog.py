"""Static metric definitions and rollup targets for CFO entity rollups API/UI."""

from __future__ import annotations

from typing import Any, Dict

ROLLUP_SCHEMA_VERSION = 2

# Dashboard targets for bullet charts / variance messaging (demo defaults).
ROLLUP_TARGETS: Dict[str, float] = {
    "audit_readiness_pct": 85.0,
    "remediation_sla_pct": 90.0,
    "evidence_completeness_pct": 92.0,
    "repeat_finding_rate_pct": 15.0,  # lower is better — interpreted in UI
}

METRIC_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "audit_readiness_pct": {
        "label": "Audit readiness",
        "sources": ["readiness_scores", "process × entity compute"],
        "description": "Average process readiness score for cells in scope.",
    },
    "unresolved_high_risk_exposure": {
        "label": "Unresolved high-severity exposure",
        "sources": ["exceptions"],
        "description": (
            "Sum of financial_exposure on open critical/high exceptions, converted into reporting currency "
            "(default USD) using exception exposure_currency when set, else the legal entity functional currency "
            "and reporting_currency_rates (USD base)."
        ),
    },
    "open_critical_cases": {
        "label": "Open critical cases",
        "sources": ["cases"],
        "description": "Cases not closed with severity marked critical.",
    },
    "open_cases": {
        "label": "Open cases",
        "sources": ["cases"],
        "description": "All cases in scope that are not closed.",
    },
    "control_failure_rate": {
        "label": "Control failure rate",
        "sources": ["controls"],
        "description": "Derived from last-run pass rates across processes tied to exceptions in scope.",
    },
    "repeat_finding_rate_pct": {
        "label": "Repeat finding rate",
        "sources": ["exceptions"],
        "description": "Share of findings where the same control_code appears more than once.",
    },
    "remediation_sla_pct": {
        "label": "Remediation SLA (closed ≤7d)",
        "sources": ["cases"],
        "description": "Among closed cases with timestamps, share closed within 7 days of opened_at.",
    },
    "evidence_completeness_pct": {
        "label": "Evidence completeness",
        "sources": ["exceptions"],
        "description": "Share of exceptions in scope with status closed (proxy for evidenced).",
    },
    "median_open_case_age_days": {
        "label": "Median age — open cases",
        "sources": ["cases"],
        "description": "Median calendar days from opened_at to now for non-closed cases.",
    },
    "median_open_exception_age_days": {
        "label": "Median age — open exceptions",
        "sources": ["exceptions"],
        "description": "Median age from detected_at (fallback opened_at) for open exceptions.",
    },
    "pct_open_cases_past_due": {
        "label": "% open cases past due",
        "sources": ["cases"],
        "description": "Open cases past due_date when present; else SLA inferred from severity.",
    },
    "case_severity_mix": {
        "label": "Case severity mix",
        "sources": ["cases"],
        "description": "Open case counts by severity bucket.",
    },
    "exception_severity_mix_open": {
        "label": "Open exception severity mix",
        "sources": ["exceptions"],
        "description": "Open exception counts by severity.",
    },
    "distinct_controls_with_open_exceptions": {
        "label": "Distinct failing controls",
        "sources": ["exceptions"],
        "description": "Unique control_code values on open exceptions in scope.",
    },
    "top_repeat_control_codes": {
        "label": "Top repeat control codes",
        "sources": ["exceptions"],
        "description": "Controls with more than one finding, ranked by recurrence.",
    },
    "remediation_close_buckets": {
        "label": "Remediation time buckets",
        "sources": ["cases"],
        "description": "Distribution of days-to-close for resolved cases.",
    },
    "exposure_concentration_hhi": {
        "label": "Exposure concentration (HHI)",
        "sources": ["exceptions"],
        "description": "Herfindahl-Hirschman-style concentration of high-severity exposure across entities (0–1 scale).",
    },
    "top_entities_by_exposure": {
        "label": "Top entities by exposure",
        "sources": ["exceptions"],
        "description": "Legal entities ranked by unresolved critical/high exposure after FX conversion to reporting currency.",
    },
    "action_queue_open_count": {
        "label": "CFO action queue (open)",
        "sources": ["cfo_action_queue"],
        "description": "Items materialized to the CFO queue in scope that are not approved/rejected.",
    },
    "action_queue_open_exposure_usd": {
        "label": "Queue exposure (USD)",
        "sources": ["cfo_action_queue"],
        "description": "Sum of exposure fields on open queue items when present.",
    },
    "close_readiness_items_open": {
        "label": "Month-end / recon items open",
        "sources": ["reconciliations"],
        "description": "Non-balanced or overdue reconciliations in entity scope (when recon feed present).",
    },
}

DRILL_PATH_META: Dict[str, Any] = {
    "reporting_currency_default": "USD",
    "levels": [
        {"key": "organization", "label": "Organization"},
        {"key": "region", "label": "Region"},
        {"key": "legal_entity", "label": "Legal entity"},
        {
            "key": "process",
            "label": "Business unit / process",
            "note": (
                "Process dimension acts as the BU proxy for drill-down until a dedicated business_unit "
                "master is wired into hierarchy."
            ),
        },
    ],
}

BOUNDARIES_COPY: Dict[str, str] = {
    "fx": (
        "Unresolved exposure is converted to reporting currency (USD) using optional exception exposure_currency, "
        "otherwise seeded functional currency per legal entity (US-HQ/SG-APAC→USD, UK-OPS→GBP, IN-SVC→INR) "
        "and reporting_currency_rates (USD base × quote rate = USD per one unit of quote)."
    ),
    "datasets": (
        "Cases drive backlog and SLA tiles; exceptions drive exposure and repeat-control tiles; "
        "controls feed failure-rate estimates; readiness_scores feed audit readiness."
    ),
}


def metric_label(key: str) -> str:
    return (METRIC_DEFINITIONS.get(key) or {}).get("label") or key.replace("_", " ").title()
