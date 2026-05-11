"""L4 contract tests for Phase 19 — Vendor Risk & Procurement Audit (HTTP)."""

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


class TestVendorRiskContracts:
    def test_vendor_risk_endpoints_and_create_case(self, token):
        s = requests.get(f"{API}/vendor-risk/summary", headers=_h(token), timeout=30)
        assert s.status_code == 200, s.text
        assert "kpis" in s.json()
        assert "as_of" in s.json()

        vlist = requests.get(f"{API}/vendor-risk/vendors", headers=_h(token), params={"limit": 5, "offset": 0}, timeout=30)
        assert vlist.status_code == 200, vlist.text
        items = vlist.json().get("items") or []
        assert items
        vid = items[0]["id"]

        vdet = requests.get(f"{API}/vendor-risk/vendors/{vid}", headers=_h(token), timeout=30)
        assert vdet.status_code == 200, vdet.text
        assert vdet.json().get("found") is True

        dups = requests.get(f"{API}/vendor-risk/duplicates", headers=_h(token), timeout=30)
        assert dups.status_code == 200, dups.text

        bca = requests.get(f"{API}/vendor-risk/bank-change-alerts", headers=_h(token), timeout=30)
        assert bca.status_code == 200, bca.text
        assert isinstance(bca.json().get("items"), list)

        npo = requests.get(f"{API}/vendor-risk/non-po-spend", headers=_h(token), timeout=30)
        assert npo.status_code == 200, npo.text
        assert isinstance(npo.json().get("items"), list)

        adv = requests.get(f"{API}/vendor-risk/advances", headers=_h(token), timeout=30)
        assert adv.status_code == 200, adv.text

        cc = requests.post(f"{API}/vendor-risk/{vid}/create-case", headers=_h(token), json={"title": "QA vendor risk case"}, timeout=30)
        assert cc.status_code == 200, cc.text
        assert cc.json().get("status") == "ok"

