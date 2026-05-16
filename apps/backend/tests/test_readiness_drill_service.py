"""Unit tests for audit readiness KPI drill-down detail."""

from app.services.readiness_drill_service import (
    READINESS_ALERT_HREFS,
    _distribution,
    _movers_from_heatmap,
    _narrative_slice,
    _paginate,
    _portfolio_components,
    _risk_band_from_score,
    _waterfall_steps,
    _weakest_cell,
    export_csv_bytes,
    export_xlsx_bytes,
    readiness_drill_v2_enabled,
)


def test_distribution_buckets():
    heatmap = [
        {"readiness": 50},
        {"readiness": 70},
        {"readiness": 85},
        {"readiness": 40},
    ]
    dist = _distribution(heatmap)
    assert sum(d["count"] for d in dist) == 4
    assert dist[0]["bucket"] == "0–60%"
    assert dist[0]["count"] == 2


def test_portfolio_components():
    heatmap = [
        {
            "control_component": 0.5,
            "recon_component": 1.0,
            "evidence_component": 0.8,
            "issue_component": 0.9,
        },
        {
            "control_component": 0.7,
            "recon_component": 0.6,
            "evidence_component": 0.4,
            "issue_component": 0.5,
        },
    ]
    c = _portfolio_components(heatmap)
    assert c["control_pct"] == 60.0
    assert "weights" in c


def test_weakest_cell():
    heatmap = [
        {"entity": "A", "process": "P1", "readiness": 80, "open_high": 0, "exposure": 0},
        {"entity": "B", "process": "P2", "readiness": 25, "open_high": 3, "exposure": 1000},
    ]
    w = _weakest_cell(heatmap)
    assert w["entity"] == "B"
    assert w["process"] == "P2"


def test_movers_wow_mode():
    heatmap = [
        {"entity": "A", "process": "P1", "readiness": 70, "open_high": 0, "exposure": 0},
        {"entity": "B", "process": "P2", "readiness": 40, "open_high": 1, "exposure": 100},
    ]
    prior = {"A|P1": 80.0, "B|P2": 55.0}
    m = _movers_from_heatmap(heatmap, prior)
    assert m["mode"] == "wow"
    assert m["top_deteriorators"][0]["entity"] == "B"
    assert m["top_deteriorators"][0]["delta_pts"] == -15.0
    assert m["top_improvers"][0]["delta_pts"] == -10.0


def test_movers_level_fallback():
    heatmap = [{"entity": "A", "process": "P1", "readiness": 30, "open_high": 0, "exposure": 0}]
    m = _movers_from_heatmap(heatmap, None)
    assert m["mode"] == "level"


def test_readiness_alert_hrefs_mapping():
    assert READINESS_ALERT_HREFS["audit_readiness_pct"] == "/app/kpi/audit_readiness_pct"
    assert READINESS_ALERT_HREFS["high_critical_open_cases"] == "/app/cases?status=open"


def test_paginate():
    items = list(range(25))
    page = _paginate(items, 10, 5)
    assert page["total"] == 25
    assert page["items"] == list(range(5, 15))
    assert page["has_more"] is True


def test_waterfall_steps():
    portfolio = _portfolio_components(
        [
            {
                "control_component": 0.5,
                "recon_component": 0.8,
                "evidence_component": 0.7,
                "issue_component": 0.6,
            }
        ]
    )
    steps = _waterfall_steps(portfolio, 55.0)
    assert steps[0]["kind"] == "start"
    assert steps[-1]["kind"] == "end"
    assert steps[-1]["value"] == 55.0


def test_risk_band_from_score():
    assert _risk_band_from_score(0.8) == "critical"
    assert _risk_band_from_score(0.4) == "moderate"
    assert _risk_band_from_score(0.1) == "stable"


def test_readiness_drill_v2_enabled_default():
    assert readiness_drill_v2_enabled() is True


def test_narrative_slice_kwarg_compatible():
    """Regression: narrative must call build_executive_narrative_ml with keyword-only API."""
    cockpit = {
        "kpis": {"audit_readiness_pct": 60.0},
        "trends": [],
        "heatmap": [{"entity": "A", "process": "P", "readiness": 60}],
        "top_risks": [],
        "top_failing_controls": [],
        "filters_applied": {"entity_code": "A", "period_ym": "2026-05"},
    }
    out = _narrative_slice(cockpit, [])
    assert out.get("model")
    assert out.get("risk_band")


def test_export_xlsx_bytes():
    detail = {
        "as_of": "2026-01-01T00:00:00Z",
        "summary": {"current": 55.5, "prior_value": 60, "delta_pct": -4.5, "risk_band": "elevated"},
        "heatmap": [
            {
                "entity": "US-HQ",
                "process": "Treasury",
                "readiness": 55.5,
                "control_component": 0.5,
                "recon_component": 0.8,
                "evidence_component": 0.7,
                "issue_component": 0.6,
                "open_high": 2,
                "exposure": 50000,
            }
        ],
        "extra_metrics": {"global_control_pass_pct": 50.0, "overdue_reconciliations_count": 3},
    }
    raw = export_xlsx_bytes(detail)
    assert raw[:2] == b"PK"


def test_export_csv_bytes():
    detail = {
        "as_of": "2026-01-01T00:00:00Z",
        "summary": {"current": 55.5, "prior_value": 60, "delta_pct": -4.5},
        "heatmap": [
            {
                "entity": "US-HQ",
                "process": "Treasury",
                "readiness": 55.5,
                "control_component": 0.5,
                "recon_component": 0.8,
                "evidence_component": 0.7,
                "issue_component": 0.6,
                "open_high": 2,
                "exposure": 50000,
            }
        ],
    }
    raw = export_csv_bytes(detail)
    text = raw.decode("utf-8")
    assert "Audit readiness export" in text
    assert "US-HQ" in text
    assert "Treasury" in text
