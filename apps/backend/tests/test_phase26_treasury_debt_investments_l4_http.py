"""L4 contract tests for Phase 26 — Treasury debt & investments (HTTP)."""

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


class TestTreasuryDebtInvestmentsContracts:
    def test_phase26_treasury_surfaces(self, token):
        s = requests.get(f"{API}/treasury/summary", headers=_h(token), timeout=30)
        assert s.status_code == 200, s.text
        body = s.json()
        assert "data" in body

        d = requests.get(f"{API}/treasury/debt", headers=_h(token), params={"limit": 5}, timeout=30)
        assert d.status_code == 200, d.text
        debts = d.json().get("items") or []
        assert debts
        debt_id = debts[0]["id"]

        rp = requests.get(f"{API}/treasury/repayment-schedule", headers=_h(token), params={"debt_id": debt_id}, timeout=30)
        assert rp.status_code == 200, rp.text

        inv = requests.get(f"{API}/treasury/investments", headers=_h(token), params={"limit": 5}, timeout=30)
        assert inv.status_code == 200, inv.text
        inv_items = inv.json().get("items") or []
        assert inv_items

        cov = requests.get(f"{API}/treasury/covenants", headers=_h(token), timeout=30)
        assert cov.status_code == 200, cov.text

        sig = requests.get(f"{API}/treasury/bank-signatories", headers=_h(token), timeout=30)
        assert sig.status_code == 200, sig.text

        cc = requests.post(f"{API}/treasury/{debt_id}/create-case", headers=_h(token), json={"title": "QA treasury case"}, timeout=30)
        assert cc.status_code == 200, cc.text
        assert cc.json().get("status") == "ok"

