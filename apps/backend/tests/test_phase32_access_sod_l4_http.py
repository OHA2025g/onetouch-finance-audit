"""L4 contract tests for Phase 32 — Access & SoD certification (HTTP)."""

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


class TestAccessSoDContracts:
    def test_phase32_access_endpoints(self, token):
        u = requests.get(f"{API}/access/users", headers=_h(token), params={"limit": 5}, timeout=30)
        assert u.status_code == 200, u.text
        assert (u.json().get("items") or [])

        r = requests.get(f"{API}/access/roles", headers=_h(token), timeout=30)
        assert r.status_code == 200, r.text
        assert (r.json().get("items") or [])

        sr = requests.get(f"{API}/access/sod-rules", headers=_h(token), timeout=30)
        assert sr.status_code == 200, sr.text

        sc = requests.get(f"{API}/access/sod-conflicts", headers=_h(token), timeout=30)
        assert sc.status_code == 200, sc.text
        assert "items" in sc.json()

        du = requests.get(f"{API}/access/dormant-users", headers=_h(token), params={"dormant_days": 90}, timeout=30)
        assert du.status_code == 200, du.text

        pu = requests.get(f"{API}/access/privileged-users", headers=_h(token), timeout=30)
        assert pu.status_code == 200, pu.text

        camp = requests.post(f"{API}/access/certification-campaign", headers=_h(token), json={"entity": "US-HQ"}, timeout=30)
        assert camp.status_code == 200, camp.text
        cid = camp.json().get("campaign_id")
        assert cid

        # Pull one item directly from db via listing users -> deterministic item id (seed pattern)
        # We know one user exists: U-1001
        item_id = f"CERTITEM-{cid}-U-1001"
        dec = requests.post(
            f"{API}/access/certification-item/{item_id}/decision",
            headers=_h(token),
            json={"decision": "approve", "note": "QA approve"},
            timeout=30,
        )
        assert dec.status_code == 200, dec.text
        assert dec.json().get("status") == "ok"

