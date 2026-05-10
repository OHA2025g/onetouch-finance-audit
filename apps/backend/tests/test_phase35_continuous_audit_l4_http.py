"""L4 contract tests for Phase 35 — Continuous Audit Rules Engine (HTTP)."""

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
    return _login("controller@onetouch.ai", "demo1234")


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


class TestContinuousAuditContracts:
    def test_phase35_rules_run_exceptions_case_and_perf(self, token):
        r = requests.get(f"{API}/continuous-audit/rules", headers=_h(token), timeout=60)
        assert r.status_code == 200, r.text
        rules = r.json().get("items") or []
        assert rules
        rid = rules[0]["id"]

        run = requests.post(f"{API}/continuous-audit/rules/{rid}/run", headers=_h(token), json={"scope": "qa"}, timeout=60)
        assert run.status_code == 200, run.text
        assert run.json().get("status") == "ok"

        ex = requests.get(f"{API}/continuous-audit/exceptions", headers=_h(token), params={"limit": 5}, timeout=60)
        assert ex.status_code == 200, ex.text
        items = ex.json().get("items") or []
        assert items
        ex_id = items[0]["id"]

        cc = requests.post(f"{API}/continuous-audit/exceptions/{ex_id}/case", headers=_h(token), json={"title": "QA continuous audit case"}, timeout=60)
        assert cc.status_code == 200, cc.text
        assert cc.json().get("status") == "ok"

        perf = requests.get(f"{API}/continuous-audit/rule-performance", headers=_h(token), timeout=60)
        assert perf.status_code == 200, perf.text
        assert "items" in perf.json()

        runs = requests.get(f"{API}/continuous-audit/runs", headers=_h(token), params={"limit": 10}, timeout=60)
        assert runs.status_code == 200, runs.text
        rb = runs.json()
        assert "items" in rb and isinstance(rb["items"], list)
        assert rb["items"], "expected at least one rule run after /rules/{id}/run"

