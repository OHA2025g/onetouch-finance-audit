"""Unit tests for CFO command center BFF helpers."""

from __future__ import annotations

from app.services.cfo_command_center_service import _build_alerts, KPI_THRESHOLDS


def test_build_alerts_readiness_breach():
    kpis = {"audit_readiness_pct": 55.0}
    alerts = _build_alerts(kpis, [])
    codes = {a["code"] for a in alerts}
    assert "audit_readiness_pct" in codes


def test_build_alerts_no_breach_when_healthy():
    kpis = {"audit_readiness_pct": 90.0, "high_critical_open_cases": 1}
    alerts = _build_alerts(kpis, [])
    assert not any(a["code"] == "audit_readiness_pct" for a in alerts)


def test_thresholds_defined():
    assert "reconciliations_overdue" in KPI_THRESHOLDS
