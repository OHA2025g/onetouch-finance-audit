"""L4 contract tests for Phase 33 — Master Data Quality command center (HTTP)."""

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


class TestMasterDataQualityContracts:
    def test_phase33_mdq_endpoints(self, token):
        s = requests.get(f"{API}/master-data-quality/summary", headers=_h(token), timeout=60)
        assert s.status_code == 200, s.text
        assert "open_by_severity" in s.json()

        v = requests.get(f"{API}/master-data-quality/vendors", headers=_h(token), params={"limit": 5}, timeout=60)
        assert v.status_code == 200, v.text

        c = requests.get(f"{API}/master-data-quality/customers", headers=_h(token), params={"limit": 5}, timeout=60)
        assert c.status_code == 200, c.text

        e = requests.get(f"{API}/master-data-quality/employees", headers=_h(token), params={"limit": 5}, timeout=60)
        assert e.status_code == 200, e.text

        g = requests.get(f"{API}/master-data-quality/gl", headers=_h(token), params={"limit": 5}, timeout=60)
        assert g.status_code == 200, g.text

        d = requests.get(f"{API}/master-data-quality/duplicates", headers=_h(token), params={"limit": 10}, timeout=60)
        assert d.status_code == 200, d.text

        ca = requests.get(f"{API}/master-data-quality/change-audit", headers=_h(token), params={"limit": 5}, timeout=60)
        assert ca.status_code == 200, ca.text

        # Create case from first vendor finding if available
        items = v.json().get("items") or []
        if items:
            fid = items[0]["id"]
            cc = requests.post(f"{API}/master-data-quality/{fid}/create-case", headers=_h(token), json={"title": "QA MDQ case"}, timeout=60)
            assert cc.status_code == 200, cc.text
            assert cc.json().get("status") == "ok"

