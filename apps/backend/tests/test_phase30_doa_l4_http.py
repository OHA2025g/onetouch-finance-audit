"""L4 contract tests for Phase 30 — Delegation of Authority engine (HTTP)."""

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


class TestDoAContracts:
    def test_phase30_doa_endpoints(self, token):
        m = requests.get(f"{API}/doa/matrix", headers=_h(token), timeout=30)
        assert m.status_code == 200, m.text
        assert (m.json().get("items") or [])

        r = requests.get(f"{API}/doa/rules", headers=_h(token), timeout=30)
        assert r.status_code == 200, r.text
        assert (r.json().get("items") or [])

        v = requests.post(
            f"{API}/doa/validate-transaction",
            headers=_h(token),
            json={"entity": "US-HQ", "category": "payment", "amount": 99999999, "currency": "INR"},
            timeout=30,
        )
        assert v.status_code == 200, v.text
        body = v.json()
        assert body.get("breach_created") is True
        breach_id = body.get("breach_id")
        assert breach_id

        b = requests.get(f"{API}/doa/breaches", headers=_h(token), timeout=30)
        assert b.status_code == 200, b.text
        assert (b.json().get("items") or [])

        ap = requests.post(
            f"{API}/doa/breaches/{breach_id}/exception-approval",
            headers=_h(token),
            json={"decision": "approved", "note": "QA approval"},
            timeout=30,
        )
        assert ap.status_code == 200, ap.text
        assert ap.json().get("status") == "ok"

