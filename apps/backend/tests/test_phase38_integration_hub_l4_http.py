"""L4 contract tests for Phase 38 — Production Integration Hub (HTTP)."""

from __future__ import annotations

import os
import time

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set to run HTTP tests"
API = f"{BASE_URL.rstrip('/')}/api"


def _wait_api(timeout_s: float = 180.0) -> None:
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


class TestIntegrationHubContracts:
    def test_phase38_connectors_crud_and_runs(self, token):
        # List via SRS path
        ls = requests.get(f"{API}/integrations/connectors", headers=_h(token), timeout=60)
        assert ls.status_code == 200, ls.text

        mx = requests.get(f"{API}/integrations/connectors/matrix", headers=_h(token), timeout=60)
        assert mx.status_code == 200, mx.text
        mj = mx.json()
        assert "configured" in mj and "catalog" in mj

        # Create connector
        cr = requests.post(
            f"{API}/integrations/connectors",
            headers=_h(token),
            json={"provider": "sap", "name": "QA SAP connector", "status": "inactive"},
            timeout=60,
        )
        assert cr.status_code == 200, cr.text
        cid = cr.json().get("id")
        assert cid

        # Patch/update
        up = requests.patch(
            f"{API}/integrations/connectors/{cid}",
            headers=_h(token),
            json={"name": "QA SAP connector v2", "status": "inactive"},
            timeout=60,
        )
        assert up.status_code == 200, up.text

        # Test
        t = requests.post(f"{API}/integrations/connectors/{cid}/test", headers=_h(token), timeout=60)
        assert t.status_code == 200, t.text

        # Sync + backfill (mock adapters)
        s = requests.post(f"{API}/integrations/connectors/{cid}/sync", headers=_h(token), timeout=120)
        assert s.status_code == 200, s.text
        assert s.json().get("id")

        b = requests.post(f"{API}/integrations/connectors/{cid}/backfill", headers=_h(token), timeout=120)
        assert b.status_code == 200, b.text

        # Health + runs
        h = requests.get(f"{API}/integrations/connectors/{cid}/health", headers=_h(token), timeout=60)
        assert h.status_code == 200, h.text

        runs = requests.get(f"{API}/integrations/connectors/{cid}/runs", headers=_h(token), timeout=60)
        assert runs.status_code == 200, runs.text

        # Sync logs
        logs = requests.get(f"{API}/integrations/connectors/sync-logs", headers=_h(token), timeout=60)
        assert logs.status_code == 200, logs.text
        assert "items" in logs.json()

