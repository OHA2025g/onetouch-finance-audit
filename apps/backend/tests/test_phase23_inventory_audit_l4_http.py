"""L4 contract tests for Phase 23 — Inventory Audit & Valuation (HTTP)."""

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
    return _login("auditor@onetouch.ai", "demo1234")


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


class TestInventoryAuditContracts:
    def test_inventory_audit_endpoints_and_create_case(self, token):
        s = requests.get(f"{API}/inventory-audit/summary", headers=_h(token), timeout=30)
        assert s.status_code == 200, s.text
        assert "kpis" in s.json()

        ag = requests.get(f"{API}/inventory-audit/ageing", headers=_h(token), timeout=30)
        assert ag.status_code == 200, ag.text
        assert isinstance(ag.json().get("items"), list)

        sm = requests.get(f"{API}/inventory-audit/slow-moving", headers=_h(token), timeout=30)
        assert sm.status_code == 200, sm.text
        assert isinstance(sm.json().get("items"), list)

        ve = requests.get(f"{API}/inventory-audit/valuation-exceptions", headers=_h(token), timeout=30)
        assert ve.status_code == 200, ve.text
        items = ve.json().get("items") or []
        assert isinstance(items, list)
        if items:
            inv_id = items[0]["id"]
            cc = requests.post(f"{API}/inventory-audit/{inv_id}/create-case", headers=_h(token), json={"title": "QA inventory case"}, timeout=30)
            assert cc.status_code == 200, cc.text
            assert cc.json().get("status") == "ok"

