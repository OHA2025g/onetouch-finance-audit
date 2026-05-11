"""L4 contract tests for Phase 25 — Fixed Assets & Capex audit (HTTP)."""

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


class TestFixedAssetsCapexContracts:
    def test_fixed_assets_endpoints_and_create_case(self, token):
        s = requests.get(f"{API}/fixed-assets-audit/summary", headers=_h(token), timeout=30)
        assert s.status_code == 200, s.text
        assert "kpis" in s.json()

        a = requests.get(f"{API}/fixed-assets-audit/assets", headers=_h(token), params={"limit": 5}, timeout=30)
        assert a.status_code == 200, a.text
        assets = a.json().get("items") or []
        assert assets
        asset_id = assets[0]["id"]

        de = requests.get(f"{API}/fixed-assets-audit/depreciation-exceptions", headers=_h(token), timeout=30)
        assert de.status_code == 200, de.text

        cw = requests.get(f"{API}/fixed-assets-audit/cwip-ageing", headers=_h(token), timeout=30)
        assert cw.status_code == 200, cw.text

        co = requests.get(f"{API}/fixed-assets-audit/capex-overrun", headers=_h(token), timeout=30)
        assert co.status_code == 200, co.text

        ds = requests.get(f"{API}/fixed-assets-audit/disposals", headers=_h(token), timeout=30)
        assert ds.status_code == 200, ds.text

        cc = requests.post(f"{API}/fixed-assets-audit/{asset_id}/create-case", headers=_h(token), json={"title": "QA FA case"}, timeout=30)
        assert cc.status_code == 200, cc.text
        assert cc.json().get("status") == "ok"

