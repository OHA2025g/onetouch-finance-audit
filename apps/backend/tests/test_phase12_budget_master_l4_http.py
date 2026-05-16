"""L4 contract tests for Phase 12 — Budget upload & master (HTTP)."""

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


class TestBudgetContracts:
    def test_budget_upload_rejects_invalid_lines(self, token):
        bad = requests.post(
            f"{API}/budget/upload",
            headers=_h(token),
            json={"entity": "IN-HQ", "name": "Bad lines", "lines": [{"amount": 1}]},
            timeout=30,
        )
        assert bad.status_code == 400, bad.text

    def test_budget_upload_list_get_approve_lock_unlock(self, token):
        up = requests.post(
            f"{API}/budget/upload",
            headers=_h(token),
            json={
                "entity": "IN-HQ",
                "name": "FY26 Budget QA",
                "currency": "INR",
                "lines": [{"gl_account": "4000", "period_ym": "2026-04", "amount": 100000}],
            },
            timeout=30,
        )
        assert up.status_code == 200, up.text
        bid = up.json()["budget_id"]

        li = requests.get(f"{API}/budget", headers=_h(token), timeout=30)
        assert li.status_code == 200, li.text
        assert isinstance(li.json().get("items"), list)

        get1 = requests.get(f"{API}/budget/{bid}", headers=_h(token), timeout=30)
        assert get1.status_code == 200, get1.text
        assert get1.json().get("found") is True

        lk_before = requests.post(f"{API}/budget/{bid}/lock", headers=_h(token), timeout=30)
        assert lk_before.status_code == 409, lk_before.text

        ap = requests.post(f"{API}/budget/{bid}/approve", headers=_h(token), timeout=30)
        assert ap.status_code == 200, ap.text
        assert ap.json().get("status") == "ok"

        lk = requests.post(f"{API}/budget/{bid}/lock", headers=_h(token), timeout=30)
        assert lk.status_code == 200, lk.text
        assert lk.json().get("status") == "ok"

        ul = requests.post(f"{API}/budget/{bid}/unlock", headers=_h(token), timeout=30)
        assert ul.status_code == 200, ul.text
        assert ul.json().get("status") == "ok"

    def test_budget_versions_returns_governance_counts(self, token):
        ver = requests.get(f"{API}/budget/versions", headers=_h(token), timeout=30)
        assert ver.status_code == 200, ver.text
        body = ver.json()
        assert "governance" in body
        gov = body["governance"]
        assert set(gov.keys()) >= {"uploads", "draft", "approved", "locked"}
        assert gov["uploads"] == body.get("count", len(body.get("items") or []))

