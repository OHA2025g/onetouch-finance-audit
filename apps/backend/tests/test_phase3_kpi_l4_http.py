"""L4 contract tests for Phase 3 KPI engine (HTTP).

These validate production-like behavior for CFO KPI surfaces:
- KPI definitions contract exists and is stable
- CFO KPI summary returns a typed list with as_of
- trend/drilldown endpoints respond and include as_of
- refresh endpoint is callable and returns fresh summary payload
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


class TestKpiContracts:
    def test_definitions_contract(self, token):
        r = requests.get(f"{API}/kpi/definitions", headers=_h(token), timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body.get("items"), list)
        assert isinstance(body.get("count"), int)
        assert body.get("count") == len(body["items"])
        assert "as_of" in body
        if body["items"]:
            first = body["items"][0]
            assert "id" in first and "label" in first and "unit" in first

    def test_cfo_summary_contract(self, token):
        r = requests.get(f"{API}/kpi/cfo-summary", headers=_h(token), timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body.get("kpis"), list)
        assert "filters_applied" in body
        assert "as_of" in body
        if body["kpis"]:
            row = body["kpis"][0]
            assert "id" in row and "label" in row and "unit" in row

    def test_trend_and_drilldown(self, token):
        # audit_readiness_pct has an implemented trend series
        r = requests.get(f"{API}/kpi/trend/audit_readiness_pct", headers=_h(token), timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("kpi_id") in ("audit_readiness_pct", "readiness")
        assert isinstance(body.get("series"), list)
        assert "as_of" in body

        r2 = requests.get(f"{API}/kpi/drilldown/high_critical_open_cases", headers=_h(token), timeout=30)
        assert r2.status_code == 200, r2.text
        body2 = r2.json()
        assert body2.get("kpi_id") == "high_critical_open_cases"
        assert isinstance(body2.get("refs"), list)
        assert "as_of" in body2

    def test_refresh_contract(self, token):
        r = requests.post(f"{API}/kpi/refresh", headers=_h(token), timeout=60)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("status") == "ok"
        assert body.get("action_queue_refreshed") is True
        assert "cfo_summary" in body
        assert "as_of" in body
