"""L4 contract tests for Phase 9 — Receivables & AR Ageing (HTTP)."""

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


class TestReceivablesContracts:
    def test_ar_ageing_and_customers_and_invoices(self, token):
        r0 = requests.get(f"{API}/working-capital/ar-ageing", headers=_h(token), timeout=30)
        assert r0.status_code == 200, r0.text
        body0 = r0.json()
        assert isinstance(body0.get("ar_ageing"), list)
        assert "as_of" in body0

        r1 = requests.get(f"{API}/ar/customers", headers=_h(token), params={"limit": 5, "offset": 0}, timeout=30)
        assert r1.status_code == 200, r1.text
        body1 = r1.json()
        assert isinstance(body1.get("items"), list)
        assert body1["items"], "expected phase2-seeded customers"
        cid = body1["items"][0]["id"]

        r2 = requests.get(f"{API}/ar/customers/{cid}", headers=_h(token), timeout=30)
        assert r2.status_code == 200, r2.text
        assert r2.json().get("found") is True

        r3 = requests.get(f"{API}/ar/invoices", headers=_h(token), params={"limit": 5}, timeout=30)
        assert r3.status_code == 200, r3.text
        body3 = r3.json()
        assert isinstance(body3.get("items"), list)

    def test_dispute_promised_payment_collection_case(self, token):
        # pick an invoice for workflow payloads
        r = requests.get(f"{API}/ar/invoices", headers=_h(token), params={"limit": 1}, timeout=30)
        assert r.status_code == 200, r.text
        invs = r.json().get("items") or []
        assert invs
        inv = invs[0]

        rd = requests.post(
            f"{API}/ar/dispute",
            headers=_h(token),
            json={"invoice_id": inv["id"], "reason": "QA dispute", "amount": inv.get("amount")},
            timeout=30,
        )
        assert rd.status_code == 200, rd.text
        assert rd.json().get("status") == "ok"

        rp = requests.post(
            f"{API}/ar/promised-payment",
            headers=_h(token),
            json={"invoice_id": inv["id"], "promised_date": inv.get("due_date"), "note": "QA promised payment"},
            timeout=30,
        )
        assert rp.status_code == 200, rp.text
        assert rp.json().get("status") == "ok"

        rc = requests.post(
            f"{API}/ar/collection-case",
            headers=_h(token),
            json={"invoice_id": inv["id"], "customer_id": inv.get("customer_id"), "entity": inv.get("entity"), "exposure": inv.get("amount")},
            timeout=30,
        )
        assert rc.status_code == 200, rc.text
        assert rc.json().get("status") == "ok"
