"""L4 contract tests for Phase 18 — Bank Reconciliation Automation (HTTP)."""

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


class TestBankReconContracts:
    def test_upload_list_match_unmatched_classify_signoff(self, token):
        up = requests.post(
            f"{API}/bank-recon/upload-statement",
            headers=_h(token),
            json={
                "entity": "US-HQ",
                "bank_account_id": "BA-100",
                "statement_period": "2026-04",
                "items": [
                    {"date": "2026-04-05", "amount": 5000, "direction": "outbound", "reference": "WIRE-90001"},
                    {"date": "2026-04-06", "amount": 1200, "direction": "outbound", "reference": "CARD-XYZ-1"},
                ],
            },
            timeout=30,
        )
        assert up.status_code == 200, up.text
        st_id = up.json()["statement_id"]

        li = requests.get(f"{API}/bank-recon/statements", headers=_h(token), params={"entity_code": "US-HQ"}, timeout=30)
        assert li.status_code == 200, li.text
        assert isinstance(li.json().get("items"), list)

        am = requests.post(f"{API}/bank-recon/{st_id}/auto-match", headers=_h(token), timeout=30)
        assert am.status_code == 200, am.text
        assert am.json().get("status") == "ok"

        um = requests.get(f"{API}/bank-recon/{st_id}/unmatched", headers=_h(token), timeout=30)
        assert um.status_code == 200, um.text
        assert isinstance(um.json().get("items"), list)

        cl = requests.post(
            f"{API}/bank-recon/{st_id}/classify",
            headers=_h(token),
            json={"items": [{"reference": "CARD-XYZ-1", "classification": "bank_fee", "notes": "QA"}]},
            timeout=30,
        )
        assert cl.status_code == 200, cl.text

        so = requests.post(
            f"{API}/bank-recon/{st_id}/signoff",
            headers=_h(token),
            json={"notes": "QA signoff", "acknowledge_residual_exceptions": True},
            timeout=30,
        )
        assert so.status_code == 200, so.text
        assert so.json().get("status") == "ok"

