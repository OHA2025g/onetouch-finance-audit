"""L4 contract tests for Phase 28 — Related Party Transactions (HTTP)."""

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


class TestRPTContracts:
    def test_phase28_rpt_workflows(self, token):
        rp = requests.get(f"{API}/rpt/related-parties", headers=_h(token), params={"limit": 5}, timeout=30)
        assert rp.status_code == 200, rp.text
        parties = rp.json().get("items") or []
        assert parties
        rp_id = parties[0]["id"]

        tx = requests.get(f"{API}/rpt/transactions", headers=_h(token), params={"limit": 5, "related_party_id": rp_id}, timeout=30)
        assert tx.status_code == 200, tx.text
        items = tx.json().get("items") or []
        assert items
        tx_id = items[0]["id"]

        ap = requests.post(f"{API}/rpt/transactions/{tx_id}/approval", headers=_h(token), json={"decision": "approved", "note": "QA approve"}, timeout=30)
        assert ap.status_code == 200, ap.text

        doc = requests.post(
            f"{API}/rpt/transactions/{tx_id}/document",
            headers=_h(token),
            json={"type": "arm_length", "name": "AL note", "uri": "s3://mock/arm_length.pdf"},
            timeout=30,
        )
        assert doc.status_code == 200, doc.text
        assert doc.json().get("status") == "ok"

        out = requests.get(f"{API}/rpt/outstanding-balances", headers=_h(token), timeout=30)
        assert out.status_code == 200, out.text
        assert "items" in out.json()

        chk = requests.get(f"{API}/rpt/disclosure-checklist", headers=_h(token), timeout=30)
        assert chk.status_code == 200, chk.text
        assert "checklist" in chk.json()

        rep = requests.get(f"{API}/rpt/audit-committee-report", headers=_h(token), timeout=30)
        assert rep.status_code == 200, rep.text
        assert "headline" in rep.json()

