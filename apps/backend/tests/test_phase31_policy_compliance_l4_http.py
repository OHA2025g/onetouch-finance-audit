"""L4 contract tests for Phase 31 — Policy compliance & attestation (HTTP)."""

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


class TestPolicyComplianceContracts:
    def test_phase31_policies_attestation_and_breach_case(self, token):
        pl = requests.get(f"{API}/policies", headers=_h(token), timeout=30)
        assert pl.status_code == 200, pl.text
        items = pl.json().get("items") or []
        assert items
        pid = items[0]["id"]

        camp = requests.post(
            f"{API}/policies/attestation-campaign",
            headers=_h(token),
            json={"entity": "GLOBAL", "policy_ids": [pid], "users": ["controller@onetouch.ai"]},
            timeout=30,
        )
        assert camp.status_code == 200, camp.text
        campaign_id = camp.json().get("campaign_id")
        assert campaign_id

        ack = requests.post(
            f"{API}/policies/{pid}/acknowledge",
            headers=_h(token),
            json={"entity": "GLOBAL", "campaign_id": campaign_id, "note": "QA ack"},
            timeout=30,
        )
        assert ack.status_code == 200, ack.text

        at = requests.get(f"{API}/policies/attestations", headers=_h(token), timeout=30)
        assert at.status_code == 200, at.text

        br = requests.get(f"{API}/policies/breaches", headers=_h(token), timeout=30)
        assert br.status_code == 200, br.text
        breaches = br.json().get("items") or []
        assert breaches
        bid = breaches[0]["id"]

        cc = requests.post(f"{API}/policies/breaches/{bid}/create-case", headers=_h(token), json={"title": "QA policy breach case"}, timeout=30)
        assert cc.status_code == 200, cc.text
        assert cc.json().get("status") == "ok"

