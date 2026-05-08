"""L4 contract tests for Phase 2 Unified finance model.

These are HTTP tests (requests) that validate production-like behavior:
- typed list contracts exist and are stable
- pagination/search works for master lists
- entity scope enforcement toggle blocks cross-entity queries
- master audit trail and master DQ endpoints respond
"""

from __future__ import annotations

import os
import time
import requests
import pytest


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set to run HTTP tests"
API = f"{BASE_URL.rstrip('/')}/api"


CREDS = {
    "superadmin": ("superadmin@onetouch.ai", "demo1234"),
    "cfo": ("cfo@onetouch.ai", "demo1234"),
}

def _wait_api(timeout_s: float = 60.0) -> None:
    """Avoid flakiness: container may be restarting while pytest starts."""
    deadline = time.time() + timeout_s
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            # Any response indicates the server is accepting connections.
            requests.get(f"{API}/system/health", timeout=2)
            return
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(0.5)
    raise AssertionError(f"API not reachable within {timeout_s}s: {last_err}")


def _login(email, password):
    _wait_api()
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def tokens():
    return {k: _login(e, p) for k, (e, p) in CREDS.items()}


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


class TestMastersContracts:
    def test_customers_employees_bank_accounts_exist(self, tokens):
        for endpoint in ("/masters/customers", "/masters/employees", "/masters/bank-accounts"):
            r = requests.get(f"{API}{endpoint}", headers=_h(tokens["cfo"]), params={"limit": 5, "offset": 0}, timeout=30)
            assert r.status_code == 200, r.text
            body = r.json()
            assert isinstance(body.get("items"), list)
            # Phase 2 seed should ensure these are non-empty
            assert len(body["items"]) > 0
            assert "as_of" in body

    def test_vendors_pagination_and_search(self, tokens):
        r = requests.get(f"{API}/masters/vendors", headers=_h(tokens["cfo"]), params={"limit": 5, "offset": 0}, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body.get("items"), list)
        assert body.get("count") == len(body["items"])
        assert "as_of" in body

        if body["items"]:
            first = body["items"][0]
            code = first.get("vendor_code") or ""
            r2 = requests.get(
                f"{API}/masters/vendors",
                headers=_h(tokens["cfo"]),
                params={"q": code[:6], "limit": 10, "offset": 0},
                timeout=30,
            )
            assert r2.status_code == 200, r2.text
            assert isinstance(r2.json().get("items"), list)

    def test_transactions_contract(self, tokens):
        r = requests.get(f"{API}/masters/transactions", headers=_h(tokens["cfo"]), params={"limit": 3, "offset": 0}, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body.get("items"), list)
        assert "as_of" in body


class TestEntityScopeEnforcement:
    def test_toggle_entity_scope_on_and_blocks_cross_entity(self, tokens):
        # enable enforcement
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r.status_code == 200, r.text

        # CFO user seeded as entity US-HQ; requesting UK-OPS should be blocked
        r2 = requests.get(
            f"{API}/masters/vendors",
            headers=_h(tokens["cfo"]),
            params={"entity_code": "UK-OPS", "limit": 5, "offset": 0},
            timeout=30,
        )
        assert r2.status_code == 403, r2.text

        # and the same applies to other Phase 2 master lists
        for endpoint in ("/masters/customers", "/masters/employees", "/masters/bank-accounts"):
            rX = requests.get(
                f"{API}{endpoint}",
                headers=_h(tokens["cfo"]),
                params={"entity_code": "UK-OPS", "limit": 5, "offset": 0},
                timeout=30,
            )
            assert rX.status_code == 403, rX.text

        # requesting without entity_code should be restricted to assigned entity (200)
        r3 = requests.get(f"{API}/masters/vendors", headers=_h(tokens["cfo"]), params={"limit": 5}, timeout=30)
        assert r3.status_code == 200, r3.text

        # disable enforcement to avoid affecting other tests
        cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
        r4 = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)
        assert r4.status_code == 200, r4.text


class TestAuditAndDQSurfaces:
    def test_audit_trail_endpoint(self, tokens):
        r = requests.get(f"{API}/masters/audit-trail", headers=_h(tokens["cfo"]), params={"limit": 5}, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body.get("items"), list)

    def test_master_dq_endpoints(self, tokens):
        # recompute requires super admin
        r0 = requests.post(f"{API}/dq/masters/recompute", headers=_h(tokens["superadmin"]), json={}, timeout=60)
        assert r0.status_code == 200, r0.text

        r1 = requests.get(f"{API}/dq/masters/summary", headers=_h(tokens["cfo"]), timeout=30)
        assert r1.status_code == 200, r1.text
        r2 = requests.get(f"{API}/dq/masters/findings", headers=_h(tokens["cfo"]), params={"limit": 10}, timeout=30)
        assert r2.status_code == 200, r2.text

