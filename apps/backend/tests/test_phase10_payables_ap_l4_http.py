"""L4 contract tests for Phase 10 — Payables & AP Ageing (HTTP)."""

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


class TestPayablesContracts:
    def test_ap_ageing_and_vendors_and_invoices(self, token):
        r0 = requests.get(f"{API}/working-capital/ap-ageing", headers=_h(token), timeout=30)
        assert r0.status_code == 200, r0.text
        assert isinstance(r0.json().get("ap_ageing"), list)
        assert "as_of" in r0.json()

        r1 = requests.get(f"{API}/ap/vendors", headers=_h(token), params={"limit": 5, "offset": 0}, timeout=30)
        assert r1.status_code == 200, r1.text
        body1 = r1.json()
        assert body1["items"], "expected seeded vendors"
        vid = body1["items"][0]["id"]

        r2 = requests.get(f"{API}/ap/vendors/{vid}", headers=_h(token), timeout=30)
        assert r2.status_code == 200, r2.text
        assert r2.json().get("found") is True

        r3 = requests.get(f"{API}/ap/invoices", headers=_h(token), params={"limit": 5}, timeout=30)
        assert r3.status_code == 200, r3.text
        assert isinstance(r3.json().get("items"), list)

    def test_payment_calendar_prioritization_and_hold(self, token):
        r4 = requests.get(f"{API}/ap/payment-calendar", headers=_h(token), params={"limit": 5}, timeout=30)
        assert r4.status_code == 200, r4.text
        assert isinstance(r4.json().get("items"), list)

        r5 = requests.get(f"{API}/ap/payment-prioritization", headers=_h(token), params={"limit": 5}, timeout=30)
        assert r5.status_code == 200, r5.text
        assert isinstance(r5.json().get("items"), list)

        # create a hold against any invoice (if list is empty, fetch from invoices seed)
        invs = r5.json().get("items") or []
        if not invs:
            invs = requests.get(f"{API}/ap/invoices", headers=_h(token), params={"limit": 1}, timeout=30).json().get("items") or []
        assert invs
        inv = invs[0]
        rh = requests.post(
            f"{API}/ap/payment-hold",
            headers=_h(token),
            json={"invoice_id": inv["id"], "reason": "QA hold", "entity": inv.get("entity")},
            timeout=30,
        )
        assert rh.status_code == 200, rh.text
        assert rh.json().get("status") == "ok"
