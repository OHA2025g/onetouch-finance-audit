"""L4 contract tests for Phase 21 — O2C Audit (HTTP)."""

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


class TestO2CAuditContracts:
    def test_o2c_endpoints_and_create_case(self, token):
        s = requests.get(f"{API}/o2c/summary", headers=_h(token), timeout=30)
        assert s.status_code == 200, s.text
        assert "kpis" in s.json()
        assert "as_of" in s.json()

        cl = requests.get(f"{API}/o2c/customers", headers=_h(token), params={"limit": 5, "offset": 0}, timeout=30)
        assert cl.status_code == 200, cl.text
        items = cl.json().get("items") or []
        assert items
        cid = items[0]["id"]

        cd = requests.get(f"{API}/o2c/customers/{cid}", headers=_h(token), timeout=30)
        assert cd.status_code == 200, cd.text
        assert cd.json().get("found") is True

        rc = requests.get(f"{API}/o2c/revenue-cutoff", headers=_h(token), timeout=30)
        assert rc.status_code == 200, rc.text
        assert isinstance(rc.json().get("items"), list)

        br = requests.get(f"{API}/o2c/credit-limit-breaches", headers=_h(token), timeout=30)
        assert br.status_code == 200, br.text
        assert isinstance(br.json().get("items"), list)

        cn = requests.get(f"{API}/o2c/customer-concentration", headers=_h(token), timeout=30)
        assert cn.status_code == 200, cn.text
        assert isinstance(cn.json().get("items"), list)

        cc = requests.post(f"{API}/o2c/{cid}/create-case", headers=_h(token), json={"title": "QA O2C case"}, timeout=30)
        assert cc.status_code == 200, cc.text
        assert cc.json().get("status") == "ok"

