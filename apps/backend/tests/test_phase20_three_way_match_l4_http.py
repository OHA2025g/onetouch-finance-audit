"""L4 contract tests for Phase 20 — Three-Way Match Engine (HTTP)."""

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


class TestThreeWayMatchContracts:
    def test_tolerances_run_summary_exceptions_and_case(self, token):
        gt = requests.get(f"{API}/three-way-match/tolerances", headers=_h(token), timeout=30)
        assert gt.status_code == 200, gt.text
        assert "tolerances" in gt.json()

        st = requests.post(f"{API}/three-way-match/tolerances", headers=_h(token), json={"amount_tolerance_pct": 5, "amount_tolerance_abs": 500}, timeout=30)
        assert st.status_code == 200, st.text
        assert st.json().get("status") == "ok"

        rn = requests.post(f"{API}/three-way-match/run", headers=_h(token), timeout=60)
        assert rn.status_code == 200, rn.text
        assert rn.json().get("status") == "ok"

        sm = requests.get(f"{API}/three-way-match/summary", headers=_h(token), timeout=30)
        assert sm.status_code == 200, sm.text
        assert "open_exceptions" in sm.json()

        exl = requests.get(f"{API}/three-way-match/exceptions", headers=_h(token), params={"limit": 5}, timeout=30)
        assert exl.status_code == 200, exl.text
        items = exl.json().get("items") or []
        assert isinstance(items, list)
        if items:
            ex_id = items[0]["id"]
            det = requests.get(f"{API}/three-way-match/{ex_id}", headers=_h(token), timeout=30)
            assert det.status_code == 200, det.text

            cc = requests.post(f"{API}/three-way-match/{ex_id}/create-case", headers=_h(token), json={"title": "QA TWM case"}, timeout=30)
            assert cc.status_code == 200, cc.text
            assert cc.json().get("status") == "ok"

