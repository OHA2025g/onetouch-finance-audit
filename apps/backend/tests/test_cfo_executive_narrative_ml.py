"""Unit tests for ML executive narrative."""

from __future__ import annotations

from app.services.cfo_executive_narrative_ml import (
    _composite_risk_score,
    _trend_slope,
    build_executive_narrative_ml,
)


def test_trend_slope_positive():
    series = [{"readiness": 70}, {"readiness": 75}, {"readiness": 80}]
    assert _trend_slope(series, "readiness") > 0


def test_composite_risk_score_range():
    features = {k: 0.9 for k in [
        "readiness_gap", "exposure_norm", "cases_norm", "repeat_norm",
        "evidence_gap", "sla_gap", "trend_readiness_down", "trend_exposure_up",
        "alert_density", "ops_pressure",
    ]}
    s = _composite_risk_score(features)
    assert 0.0 < s < 1.0


def test_build_narrative_has_citations():
    cockpit = {
        "kpis": {
            "audit_readiness_pct": 55.0,
            "unresolved_high_risk_exposure": 10_000_000.0,
            "high_critical_open_cases": 12,
            "repeat_finding_rate_pct": 45.0,
            "evidence_completeness_pct": 20.0,
            "remediation_sla_pct": 88.0,
        },
        "trends": [
            {"week": "W1", "readiness": 60, "exposure": 9_000_000},
            {"week": "W2", "readiness": 55, "exposure": 10_000_000},
        ],
        "top_risks": [
            {
                "id": "ex-1",
                "title": "Duplicate invoice",
                "control_code": "C-AP-01",
                "severity": "high",
                "entity": "US-HQ",
                "process": "Procure-to-Pay",
                "financial_exposure": 500_000,
            }
        ],
        "top_failing_controls": [
            {"code": "C-GL-002", "name": "Backdated JE", "process": "Record-to-Report", "exceptions": 5}
        ],
        "heatmap": [{"entity": "US-HQ", "process": "Record-to-Report", "readiness": 48.0, "open_high": 3, "exposure": 1_000_000}],
    }
    out = build_executive_narrative_ml(
        cockpit=cockpit,
        alerts=[{"id": "a1", "code": "audit_readiness_pct", "title": "Readiness", "message": "Below target"}],
        entity_code="US-HQ",
        period_ym="2026-04",
    )
    assert out["model"] == "onetouch-cfo-ml-v1"
    assert "[#1]" in out["answer"]
    sections = out["sections"]
    assert sections["risk_band"] == "critical"
    assert len(sections["drivers"]) >= 1
    assert len(sections["actions"]) >= 1
    assert sections["action_review"]
    assert len(out["citations"]) >= 1
    assert "ml_meta" in out
    assert out["mode"] == "cfo_ml"
