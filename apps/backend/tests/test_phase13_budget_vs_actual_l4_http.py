"""L4 contract tests for Phase 13 — Budget vs Actual + variance workflow (HTTP)."""

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


class TestBudgetVsActualContracts:
    def test_budget_vs_actual_dashboard_and_variance_workflow(self, token):
        r0 = requests.get(f"{API}/budget/budget-vs-actual", headers=_h(token), timeout=30)
        assert r0.status_code == 200, r0.text
        assert "as_of" in r0.json()
        assert "data" in r0.json()

        # Ensure a budget exists (variance generator uses latest budget lines)
        up = requests.post(
            f"{API}/budget/upload",
            headers=_h(token),
            json={
                "entity": "IN-HQ",
                "name": "FY26 Budget QA (Phase 13)",
                "currency": "INR",
                "lines": [{"gl_account": "4000", "period_ym": "2026-04", "amount": 100000}],
            },
            timeout=30,
        )
        assert up.status_code == 200, up.text

        r1 = requests.get(f"{API}/budget/variance", headers=_h(token), params={"entity_code": "IN-HQ"}, timeout=30)
        assert r1.status_code == 200, r1.text
        body1 = r1.json()
        assert body1["items"], "expected variance items (seeded or synthesized)"
        vid = body1["items"][0]["id"]

        r2 = requests.get(f"{API}/budget/variance/{vid}", headers=_h(token), timeout=30)
        assert r2.status_code == 200, r2.text
        assert r2.json().get("found") is True

        r3 = requests.post(f"{API}/budget/variance/{vid}/comment", headers=_h(token), json={"text": "QA comment"}, timeout=30)
        assert r3.status_code == 200, r3.text
        assert r3.json().get("status") == "ok"

        r4 = requests.post(
            f"{API}/budget/variance/{vid}/approve-explanation",
            headers=_h(token),
            json={"explanation": "QA explanation approved"},
            timeout=30,
        )
        assert r4.status_code == 200, r4.text
        assert r4.json().get("status") == "ok"

