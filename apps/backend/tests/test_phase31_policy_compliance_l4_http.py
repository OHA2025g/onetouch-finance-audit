"""L4 contract tests for Phase 31 — Policy compliance & attestation (HTTP)."""

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

