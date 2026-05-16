"""L4 contract tests for Phase 18 — Bank Reconciliation Automation (HTTP)."""

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


class TestBankReconContracts:
    def test_summary_endpoint(self, token):
        r = requests.get(f"{API}/bank-recon/summary", headers=_h(token), params={"entity_code": "US-HQ"}, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "kpis" in body
        assert "as_of" in body

    def test_upload_csv_and_get_detail(self, token):
        up = requests.post(
            f"{API}/bank-recon/upload-statement/csv",
            headers=_h(token),
            json={
                "entity": "US-HQ",
                "bank_account_id": "BA-CSV",
                "statement_period": "2026-05",
                "csv_text": "date,amount,direction,reference\n2026-05-01,99,outbound,CSV-REF-1\n",
            },
            timeout=30,
        )
        assert up.status_code == 200, up.text
        st_id = up.json()["statement_id"]
        detail = requests.get(f"{API}/bank-recon/{st_id}", headers=_h(token), timeout=30)
        assert detail.status_code == 200, detail.text
        assert detail.json().get("statement", {}).get("id") == st_id

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

