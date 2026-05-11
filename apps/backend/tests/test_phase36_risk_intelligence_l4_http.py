"""L4 contract tests for Phase 36 — Risk Intelligence scoring (HTTP)."""

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
    return _login("controller@onetouch.ai", "demo1234")


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


class TestRiskIntelligenceContracts:
    def test_phase36_risk_intelligence(self, token):
        s = requests.get(f"{API}/risk-intelligence/summary", headers=_h(token), timeout=60)
        assert s.status_code == 200, s.text
        assert "counts_by_band" in s.json()

        sc = requests.get(f"{API}/risk-intelligence/scores", headers=_h(token), params={"limit": 5}, timeout=60)
        assert sc.status_code == 200, sc.text
        items = sc.json().get("items") or []
        assert items
        one = items[0]

        det = requests.get(f"{API}/risk-intelligence/{one['object_type']}/{one['object_id']}", headers=_h(token), timeout=60)
        assert det.status_code == 200, det.text

        hm = requests.get(f"{API}/risk-intelligence/heatmap", headers=_h(token), timeout=60)
        assert hm.status_code == 200, hm.text
        assert "items" in hm.json()

        rc = requests.post(f"{API}/risk-intelligence/recalculate", headers=_h(token), json={"limit_per_type": 10}, timeout=120)
        assert rc.status_code == 200, rc.text
        assert rc.json().get("status") == "ok"

        fb = requests.post(
            f"{API}/risk-intelligence/{one['object_id']}/feedback",
            headers=_h(token),
            json={"object_type": one["object_type"], "label": "needs_review", "note": "QA feedback"},
            timeout=60,
        )
        assert fb.status_code == 200, fb.text
        assert fb.json().get("status") == "ok"

