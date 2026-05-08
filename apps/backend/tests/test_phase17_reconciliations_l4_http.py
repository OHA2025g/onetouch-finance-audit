"""L4 contract tests for Phase 17 — Reconciliation Management Suite (HTTP)."""

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


class TestReconciliationsContracts:
    def test_create_list_get_workflow_and_case(self, token):
        cr = requests.post(
            f"{API}/reconciliations",
            headers=_h(token),
            json={"entity": "US-HQ", "reconciliation_type": "Bank", "period": "2026-04", "variance_amount": 1234.56, "due_date": "2026-05-10"},
            timeout=30,
        )
        assert cr.status_code == 200, cr.text
        rid = cr.json()["reconciliation_id"]

        li = requests.get(f"{API}/reconciliations", headers=_h(token), params={"limit": 5}, timeout=30)
        assert li.status_code == 200, li.text
        assert isinstance(li.json().get("items"), list)

        ge = requests.get(f"{API}/reconciliations/{rid}", headers=_h(token), timeout=30)
        assert ge.status_code == 200, ge.text
        assert ge.json().get("reconciliation", {}).get("id") == rid

        ev = requests.post(f"{API}/reconciliations/{rid}/evidence", headers=_h(token), json={"type": "link", "url": "https://example.com", "notes": "QA"}, timeout=30)
        assert ev.status_code == 200, ev.text

        sb = requests.post(f"{API}/reconciliations/{rid}/submit", headers=_h(token), timeout=30)
        assert sb.status_code == 200, sb.text

        ap = requests.post(f"{API}/reconciliations/{rid}/approve", headers=_h(token), timeout=30)
        assert ap.status_code == 200, ap.text

        ro = requests.post(f"{API}/reconciliations/{rid}/reopen", headers=_h(token), json={"reason": "QA reopen"}, timeout=30)
        assert ro.status_code == 200, ro.text

        cc = requests.post(f"{API}/reconciliations/{rid}/create-case", headers=_h(token), json={"title": "QA case"}, timeout=30)
        assert cc.status_code == 200, cc.text
        assert cc.json().get("status") == "ok"

