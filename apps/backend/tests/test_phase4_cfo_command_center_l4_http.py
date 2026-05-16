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

import time

import pytest
import requests

from l4_http_common import resolve_react_app_backend_url, wait_until_api_ready


BASE_URL = resolve_react_app_backend_url()
assert BASE_URL, (
    "Set REACT_APP_BACKEND_URL to the API root (e.g. http://127.0.0.1:8000), or define it in apps/frontend/.env."
)
API = f"{BASE_URL.rstrip('/')}/api"


CREDS = {"cfo": ("cfo@onetouch.ai", "demo1234")}


def _wait_api(timeout_s: float = 60.0) -> None:
    wait_until_api_ready(API, timeout_s=timeout_s)


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

    def test_command_center_bff_contract(self, token):
        r = requests.get(
            f"{API}/cfo/command-center",
            headers=_h(token),
            params={"entity_code": "US-HQ", "no_cache": True},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "cockpit" in body
        assert isinstance(body.get("hero_kpis"), list)
        assert isinstance(body.get("ops_kpis"), list)
        assert isinstance(body.get("action_queue"), dict)
        assert isinstance(body.get("alerts"), list)
        assert "what_changed" in body
        assert "as_of" in body
        hero = body["hero_kpis"]
        if hero:
            assert "id" in hero[0]
        trends = (body.get("cockpit") or {}).get("trends") or []
        assert isinstance(trends, list)

    def test_command_center_process_filter(self, token):
        r = requests.get(
            f"{API}/cfo/command-center",
            headers=_h(token),
            params={"entity_code": "US-HQ", "process": "Record-to-Report", "no_cache": True},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("filters_applied", {}).get("process") == "Record-to-Report"
