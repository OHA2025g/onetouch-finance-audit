"""Light unit checks for executive review KPI helpers (no Mongo required)."""
from __future__ import annotations

from app.services.ca_executive_review_service import compute_issue_funnel, compute_remediation_sla


def test_issue_funnel_empty():
    out = compute_issue_funnel(risks=[], cases=[], deficiencies=[], observations=[])
    assert out["open_cases"]["total"] == 0
    assert out["risks_high_critical"]["total"] == 0


def test_issue_funnel_open_case_counts():
    cases = [
        {"status": "open", "severity": "high", "opened_at": "2026-01-01T00:00:00+00:00"},
        {"status": "closed", "severity": "critical", "opened_at": "2026-01-02T00:00:00+00:00"},
    ]
    out = compute_issue_funnel(risks=[], cases=cases, deficiencies=[], observations=[])
    assert out["open_cases"]["total"] == 1


def test_remediation_sla_partial_closure():
    cases = [
        {
            "status": "closed",
            "severity": "critical",
            "opened_at": "2026-01-01T00:00:00+00:00",
            "closed_at": "2026-01-02T00:00:00+00:00",
        },
    ]
    sla = compute_remediation_sla(cases)
    assert sla["closed_measured"] == 1
    assert sla["closed_within_sla"] == 1
