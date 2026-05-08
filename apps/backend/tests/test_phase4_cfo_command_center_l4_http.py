"""L4 contract tests for Phase 4 — CFO Command Center 2.0 (HTTP).

Validates the public API surfaces expected by the Phase 4 spec:
- GET /api/cfo/summary
- GET /api/cfo/financial-health
- GET /api/cfo/risk-summary
- GET /api/cfo/liquidity-watch
- GET /api/cfo/working-capital
- GET /api/cfo/team-performance

All responses must be auth-protected and include stable top-level keys + as_of.
"""

from __future__ import annotations

import os
import time

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set to run HTTP tests"
API = f"{BASE_URL.rstrip('/')}/api"


CREDS = {"cfo": ("cfo@onetouch.ai", "demo1234")}

def _wait_api(timeout_s: float = 60.0) -> None:
    """Avoid flakiness: container may be restarting while pytest starts."""
    deadline = time.time() + timeout_s
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            requests.get(f"{API}/system/health", timeout=2)
            return
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(0.5)
    raise AssertionError(f"API not reachable within {timeout_s}s: {last_err}")


def _login(email: str, password: str) -> str:
    _wait_api()
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def token() -> str:
    email, password = CREDS["cfo"]
    return _login(email, password)


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


class TestCfoCommandCenterContracts:
    def test_summary_contract(self, token):
        r = requests.get(f"{API}/cfo/summary", headers=_h(token), timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body.get("kpis"), dict)
        assert isinstance(body.get("top_risks"), list)
        assert isinstance(body.get("top_failing_controls"), list)
        assert isinstance(body.get("heatmap"), list)
        assert "as_of" in body

    def test_financial_health_contract(self, token):
        r = requests.get(f"{API}/cfo/financial-health", headers=_h(token), timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "cockpit_kpis" in body
        assert "controller_kpis" in body
        assert isinstance(body.get("heatmap"), list)
        assert "filters_applied" in body
        assert "as_of" in body

    def test_risk_summary_contract(self, token):
        r = requests.get(f"{API}/cfo/risk-summary", headers=_h(token), timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body.get("top_risks"), list)
        assert isinstance(body.get("top_failing_controls"), list)
        assert "kpis" in body
        assert "filters_applied" in body
        assert "as_of" in body

    def test_liquidity_watch_contract(self, token):
        r = requests.get(f"{API}/cfo/liquidity-watch", headers=_h(token), timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "treasury" in body
        assert "filters_applied" in body
        assert "as_of" in body

    def test_working_capital_contract(self, token):
        r = requests.get(f"{API}/cfo/working-capital", headers=_h(token), timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "working_capital" in body
        assert "filters_applied" in body
        assert "as_of" in body

    def test_team_performance_contract(self, token):
        r = requests.get(f"{API}/cfo/team-performance", headers=_h(token), timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body.get("cycles"), dict)
        assert "filters_applied" in body
        assert "as_of" in body
