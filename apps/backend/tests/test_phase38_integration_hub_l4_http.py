"""L4 contract tests for Phase 38 — Production Integration Hub (HTTP)."""

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


def _wait_api(timeout_s: float = 180.0) -> None:
    wait_until_api_ready(API, timeout_s=timeout_s)


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

