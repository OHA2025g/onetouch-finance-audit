"""L4 contract tests for Phase 8 — Working Capital Command Center (HTTP)."""

from __future__ import annotations

import os
import time

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set to run HTTP tests"
API = f"{BASE_URL.rstrip('/')}/api"


def _wait_api(timeout_s: float = 60.0) -> None:
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
    return _login("cfo@onetouch.ai", "demo1234")


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


class TestWorkingCapitalContracts:
    def test_summary_contract(self, token):
        r = requests.get(f"{API}/working-capital/summary", headers=_h(token), timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "data" in body and isinstance(body["data"], dict)
        assert "as_of" in body
        wc = body["data"]
        assert "kpis" in wc and isinstance(wc["kpis"], dict)

    def test_ccc_blocked_cash_bridge_entity_view(self, token):
        r1 = requests.get(f"{API}/working-capital/ccc", headers=_h(token), timeout=30)
        assert r1.status_code == 200, r1.text
        assert "data" in r1.json()

        r2 = requests.get(f"{API}/working-capital/blocked-cash", headers=_h(token), timeout=30)
        assert r2.status_code == 200, r2.text
        b = r2.json()
        assert "kpis" in b and "blocked_cash_total" in b["kpis"]
        assert "as_of" in b

        r3 = requests.get(f"{API}/working-capital/bridge", headers=_h(token), timeout=30)
        assert r3.status_code == 200, r3.text
        br = r3.json()
        assert isinstance(br.get("bridge"), list)
        assert "as_of" in br

        r4 = requests.get(f"{API}/working-capital/entity-view", headers=_h(token), timeout=60)
        assert r4.status_code == 200, r4.text
        ev = r4.json()
        assert isinstance(ev.get("items"), list)
        assert isinstance(ev.get("count"), int)
        assert "as_of" in ev
