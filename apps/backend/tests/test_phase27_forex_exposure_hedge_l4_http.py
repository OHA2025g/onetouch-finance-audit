"""L4 contract tests for Phase 27 — Forex exposure & hedge tracking (HTTP)."""

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


class TestForexExposureHedgeContracts:
    def test_phase27_forex_endpoints_and_case(self, token):
        s = requests.get(f"{API}/forex/summary", headers=_h(token), timeout=30)
        assert s.status_code == 200, s.text
        assert "items" in s.json()

        ex = requests.get(f"{API}/forex/exposures", headers=_h(token), params={"limit": 5}, timeout=30)
        assert ex.status_code == 200, ex.text
        exposures = ex.json().get("items") or []
        assert exposures
        exp_id = exposures[0]["id"]
        pair = exposures[0]["pair"]

        hd = requests.get(f"{API}/forex/hedges", headers=_h(token), params={"limit": 5}, timeout=30)
        assert hd.status_code == 200, hd.text

        ur = requests.get(f"{API}/forex/unhedged-risk", headers=_h(token), timeout=30)
        assert ur.status_code == 200, ur.text
        assert "items" in ur.json()

        gl = requests.get(f"{API}/forex/gain-loss", headers=_h(token), timeout=30)
        assert gl.status_code == 200, gl.text
        assert "realized_pl" in gl.json()

        newh = requests.post(
            f"{API}/forex/hedges",
            headers=_h(token),
            json={"entity": exposures[0]["entity"], "pair": pair, "exposure_id": exp_id, "notional_base": 10000},
            timeout=30,
        )
        assert newh.status_code == 200, newh.text
        assert newh.json().get("status") == "ok"

        cc = requests.post(f"{API}/forex/{exp_id}/create-case", headers=_h(token), json={"title": "QA FX case"}, timeout=30)
        assert cc.status_code == 200, cc.text
        assert cc.json().get("status") == "ok"

