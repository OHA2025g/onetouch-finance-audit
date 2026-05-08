"""L4 contract tests for Phase 7 — Finance Team Performance surfaces (HTTP)."""

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


class TestFinanceTeamContracts:
    def test_summary(self, token):
        r = requests.get(f"{API}/finance-team/summary", headers=_h(token), timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "cycles" in body and isinstance(body["cycles"], dict)
        assert "close_tasks_open" in body
        assert "controller" in body
        assert "cockpit_kpis" in body
        assert "action_queue_total" in body
        assert "as_of" in body

    def test_workload_sla_rework_bottlenecks_scorecards(self, token):
        for path, key in [
            ("/finance-team/workload", "pending_tasks"),
            ("/finance-team/sla", "approved_pct"),
            ("/finance-team/rework", "reopened_pct"),
            ("/finance-team/bottlenecks", "pending"),
            ("/finance-team/scorecards", "scorecards"),
        ]:
            r = requests.get(f"{API}{path}", headers=_h(token), timeout=30)
            assert r.status_code == 200, f"{path}: {r.status_code} {r.text}"
            body = r.json()
            assert key in body
            assert "as_of" in body
