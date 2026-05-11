"""L4 contract tests for Phase 14 — Forecast vs Actual + Accuracy (HTTP)."""

from __future__ import annotations

import os
import time

import pytest
import requests


from l4_http_common import resolve_react_app_backend_url, wait_until_api_ready


BASE_URL = resolve_react_app_backend_url()
assert BASE_URL, (
    "Set REACT_APP_BACKEND_URL to the API root (e.g. http://127.0.0.1:8000), or define it in "
    "apps/frontend/.env for local pytest."
)
API = f"{BASE_URL.rstrip('/')}/api"


def _wait_api(timeout_s: float = 60.0) -> None:
    wait_until_api_ready(API, timeout_s=timeout_s)


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


class TestForecastContracts:
    def test_forecast_upload_list_vs_actual_accuracy(self, token):
        up = requests.post(
            f"{API}/forecast/upload",
            headers=_h(token),
            json={
                "entity": "IN-HQ",
                "name": "FY26 Forecast QA",
                "currency": "INR",
                "lines": [{"gl_account": "4000", "period_ym": "2026-04", "amount": 120000}],
            },
            timeout=30,
        )
        assert up.status_code == 200, up.text

        li = requests.get(f"{API}/forecast", headers=_h(token), timeout=30)
        assert li.status_code == 200, li.text
        assert isinstance(li.json().get("items"), list)

        va = requests.get(f"{API}/forecast/vs-actual", headers=_h(token), params={"entity_code": "IN-HQ"}, timeout=30)
        assert va.status_code == 200, va.text
        assert isinstance(va.json().get("items"), list)
        assert "as_of" in va.json()
        va_srs = requests.get(f"{API}/forecast-vs-actual", headers=_h(token), params={"entity_code": "IN-HQ"}, timeout=30)
        assert va_srs.status_code == 200, va_srs.text

        ac = requests.get(f"{API}/forecast/accuracy", headers=_h(token), params={"entity_code": "IN-HQ"}, timeout=30)
        assert ac.status_code == 200, ac.text
        assert "as_of" in ac.json()
