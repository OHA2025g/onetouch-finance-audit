"""L4 contract tests for Phase 24 — Physical Verification (HTTP)."""

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
    return _login("auditor@onetouch.ai", "demo1234")


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


class TestPhysicalVerificationContracts:
    def test_cycle_upload_variance_reason_approve_case(self, token):
        cr = requests.post(f"{API}/physical-verification/cycles", headers=_h(token), json={"entity": "US-HQ", "name": "QA PV cycle"}, timeout=30)
        assert cr.status_code == 200, cr.text
        cycle_id = cr.json()["cycle_id"]

        li = requests.get(f"{API}/physical-verification/cycles", headers=_h(token), timeout=30)
        assert li.status_code == 200, li.text

        # Ensure inventory exists (Phase 23 synth); pick one sku from valuation-exceptions
        ve = requests.get(f"{API}/inventory-audit/valuation-exceptions", headers=_h(token), timeout=30).json().get("items") or []
        assert ve, "need at least one inventory item"
        sku = ve[0]["sku"]
        book_qty = float(ve[0].get("qty_on_hand") or 0.0)
        counted = book_qty + 5

        up = requests.post(
            f"{API}/physical-verification/{cycle_id}/upload-count",
            headers=_h(token),
            json={"items": [{"sku": sku, "counted_qty": counted}]},
            timeout=30,
        )
        assert up.status_code == 200, up.text

        var = requests.get(f"{API}/physical-verification/{cycle_id}/variance", headers=_h(token), timeout=30)
        assert var.status_code == 200, var.text
        vars_ = var.json().get("items") or []
        assert vars_
        vid = vars_[0]["id"]

        rs = requests.post(f"{API}/physical-verification/variance/{vid}/reason", headers=_h(token), json={"reason": "counting_error"}, timeout=30)
        assert rs.status_code == 200, rs.text

        ap = requests.post(f"{API}/physical-verification/variance/{vid}/approve", headers=_h(token), timeout=30)
        assert ap.status_code == 200, ap.text

        cc = requests.post(f"{API}/physical-verification/variance/{vid}/create-case", headers=_h(token), json={"title": "QA PV case"}, timeout=30)
        assert cc.status_code == 200, cc.text
        assert cc.json().get("status") == "ok"

