"""L4 contract tests for Phase 11 — 13-week cash forecasting (HTTP)."""

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


class TestCashForecastContracts:
    def test_cash_position_and_forecast_and_alerts(self, token):
        r0 = requests.get(f"{API}/treasury/cash-position", headers=_h(token), timeout=30)
        assert r0.status_code == 200, r0.text
        assert "cash_balance" in r0.json()
        assert "as_of" in r0.json()

        r1 = requests.get(f"{API}/treasury/forecast-13-week", headers=_h(token), timeout=30)
        assert r1.status_code == 200, r1.text
        body1 = r1.json()
        assert isinstance(body1.get("weeks"), list)
        assert len(body1["weeks"]) == 13
        assert "as_of" in body1

        r2 = requests.get(f"{API}/treasury/shortfall-alerts", headers=_h(token), timeout=30)
        assert r2.status_code == 200, r2.text
        assert isinstance(r2.json().get("items"), list)

    def test_scenario_and_payment_prioritization(self, token):
        r3 = requests.post(
            f"{API}/treasury/scenario",
            headers=_h(token),
            json={"name": "QA scenario", "assumptions": {"inflow_multiplier": 1.0}},
            timeout=30,
        )
        assert r3.status_code == 200, r3.text
        assert r3.json().get("status") == "ok"

        r4 = requests.get(f"{API}/treasury/payment-prioritization", headers=_h(token), params={"limit": 5}, timeout=30)
        assert r4.status_code == 200, r4.text
        assert isinstance(r4.json().get("items"), list)

