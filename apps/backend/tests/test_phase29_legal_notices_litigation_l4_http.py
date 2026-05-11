"""L4 contract tests for Phase 29 — Legal notices & litigation (HTTP)."""

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


class TestLegalNoticesLitigationContracts:
    def test_phase29_legal_surfaces(self, token):
        n = requests.get(f"{API}/legal/notices", headers=_h(token), params={"limit": 5}, timeout=30)
        assert n.status_code == 200, n.text
        notices = n.json().get("items") or []
        assert notices
        notice_id = notices[0]["id"]

        l = requests.get(f"{API}/legal/litigations", headers=_h(token), params={"limit": 5}, timeout=30)
        assert l.status_code == 200, l.text
        lits = l.json().get("items") or []
        assert lits
        lit_id = lits[0]["id"]

        h = requests.get(f"{API}/legal/hearings", headers=_h(token), params={"litigation_id": lit_id}, timeout=30)
        assert h.status_code == 200, h.text

        r1 = requests.post(f"{API}/legal/{notice_id}/response", headers=_h(token), json={"text": "QA response", "status": "responded"}, timeout=30)
        assert r1.status_code == 200, r1.text

        r2 = requests.post(
            f"{API}/legal/{lit_id}/provision-assessment",
            headers=_h(token),
            json={"likelihood": "possible", "recommended_provision": 12345, "notes": "QA provision"},
            timeout=30,
        )
        assert r2.status_code == 200, r2.text

        ex = requests.get(f"{API}/legal/exposure-report", headers=_h(token), timeout=30)
        assert ex.status_code == 200, ex.text
        assert "headline" in ex.json()

