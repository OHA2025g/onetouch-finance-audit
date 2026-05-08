"""L4 contract tests for Phase 22 — Credit Notes analytics (HTTP)."""

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


class TestCreditNotesContracts:
    def test_credit_notes_endpoints_and_review_and_case(self, token):
        s = requests.get(f"{API}/credit-notes/summary", headers=_h(token), timeout=30)
        assert s.status_code == 200, s.text
        assert "kpis" in s.json()

        li = requests.get(f"{API}/credit-notes", headers=_h(token), params={"limit": 5}, timeout=30)
        assert li.status_code == 200, li.text
        items = li.json().get("items") or []
        assert items
        cn_id = items[0]["id"]

        hr = requests.get(f"{API}/credit-notes/high-risk", headers=_h(token), timeout=30)
        assert hr.status_code == 200, hr.text

        rr = requests.get(f"{API}/credit-notes/revenue-reversals", headers=_h(token), timeout=30)
        assert rr.status_code == 200, rr.text

        rv = requests.post(f"{API}/credit-notes/{cn_id}/review", headers=_h(token), json={"decision": "reviewed", "note": "QA"}, timeout=30)
        assert rv.status_code == 200, rv.text
        assert rv.json().get("status") == "ok"

        cc = requests.post(f"{API}/credit-notes/{cn_id}/create-case", headers=_h(token), json={"title": "QA credit note case"}, timeout=30)
        assert cc.status_code == 200, cc.text
        assert cc.json().get("status") == "ok"

