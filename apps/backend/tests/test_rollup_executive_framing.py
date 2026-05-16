"""Unit tests for rollup executive framing (no DB)."""

from app.services.rollup_service import build_executive_framing


def test_build_executive_framing_headline_and_worst():
    m = {
        "audit_readiness_pct": 82.5,
        "unresolved_high_risk_exposure": 1_250_000,
        "open_critical_cases": 3,
    }
    worst = [
        {"name": "APAC", "id": "apac", "exposure": 900_000, "readiness": 70.0, "kind": "region"},
        {"name": "EMEA", "id": "emea", "exposure": 100_000, "readiness": 88.0, "kind": "region"},
    ]
    out = build_executive_framing(metrics=m, reporting_ccy="USD", worst_segments=worst, node_name="Demo Org")
    assert "82.5%" in out["headline"]
    assert "3 open critical" in out["headline"]
    assert len(out["worst_segments"]) == 2
    assert out["worst_segments"][0]["label"] == "APAC"


def test_build_executive_framing_truncates_worst_three():
    worst = [{"name": f"S{i}", "exposure": float(i), "kind": "x"} for i in range(10)]
    out = build_executive_framing(metrics={"audit_readiness_pct": 1, "unresolved_high_risk_exposure": 0, "open_critical_cases": 0}, reporting_ccy="USD", worst_segments=worst)
    assert len(out["worst_segments"]) == 3
