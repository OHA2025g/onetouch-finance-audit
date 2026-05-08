"""L4 contract tests for Phase 16 — Journal Entry Risk Scoring (HTTP)."""

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


class TestJournalRiskContracts:
    def test_rules_and_list_and_detail_and_review_and_sample(self, token):
        rr = requests.get(f"{API}/journals/risk-rules", headers=_h(token), timeout=30)
        assert rr.status_code == 200, rr.text
        assert rr.json().get("items"), "expected default rules"

        li = requests.get(f"{API}/journals", headers=_h(token), params={"limit": 5, "offset": 0}, timeout=30)
        assert li.status_code == 200, li.text
        items = li.json().get("items") or []
        assert items
        je_id = items[0]["id"]
        assert "risk_score" in items[0]

        hi = requests.get(f"{API}/journals/high-risk", headers=_h(token), params={"limit": 5}, timeout=30)
        assert hi.status_code == 200, hi.text
        assert isinstance(hi.json().get("items"), list)

        det = requests.get(f"{API}/journals/{je_id}", headers=_h(token), timeout=30)
        assert det.status_code == 200, det.text
        assert "risk_score" in det.json()

        rv = requests.post(f"{API}/journals/{je_id}/review", headers=_h(token), json={"decision": "approved", "note": "QA"}, timeout=30)
        assert rv.status_code == 200, rv.text
        assert rv.json().get("status") == "ok"

        smp = requests.post(f"{API}/journals/sample", headers=_h(token), json={"n": 5, "risk_band": "high"}, timeout=30)
        assert smp.status_code == 200, smp.text
        assert isinstance(smp.json().get("items"), list)

