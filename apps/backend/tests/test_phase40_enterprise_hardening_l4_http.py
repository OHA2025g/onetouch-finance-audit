"""L4 contract tests for Phase 40 — Enterprise hardening (HTTP)."""

from __future__ import annotations

import os
import time

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set to run HTTP tests"
API = f"{BASE_URL.rstrip('/')}/api"


def _wait_api(timeout_s: float = 180.0) -> None:
    deadline = time.time() + timeout_s
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            requests.get(f"{API}/system/health/live", timeout=2)
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


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def super_admin_token() -> str:
    return _login("superadmin@onetouch.ai", "demo1234")


@pytest.fixture(scope="module")
def controller_token() -> str:
    return _login("controller@onetouch.ai", "demo1234")


class TestEnterpriseHardeningContracts:
    def test_phase40_health_live_public(self):
        _wait_api()
        r = requests.get(f"{API}/system/health/live", timeout=10)
        assert r.status_code == 200, r.text
        assert r.json().get("status") == "live"

    def test_phase40_super_admin_protected_surfaces(self, super_admin_token):
        h = requests.get(f"{API}/system/health", headers=_h(super_admin_token), timeout=30)
        assert h.status_code == 200, h.text
        assert h.json().get("status") == "ok"

        logs = requests.get(f"{API}/system/audit-logs", headers=_h(super_admin_token), params={"limit": 5}, timeout=30)
        assert logs.status_code == 200, logs.text
        assert "items" in logs.json()

        cfg = requests.get(f"{API}/system/security-config", headers=_h(super_admin_token), timeout=30)
        assert cfg.status_code == 200, cfg.text
        assert "config" in cfg.json()

        up = requests.post(
            f"{API}/system/security-config",
            headers=_h(super_admin_token),
            json={"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}},
            timeout=30,
        )
        assert up.status_code == 200, up.text
        assert up.json().get("id") == "singleton"

    def test_phase40_rbac_enforced_for_non_admin(self, controller_token):
        h = requests.get(f"{API}/system/health", headers=_h(controller_token), timeout=30)
        assert h.status_code == 403, h.text

        logs = requests.get(f"{API}/system/audit-logs", headers=_h(controller_token), timeout=30)
        assert logs.status_code == 403, logs.text

        cfg = requests.get(f"{API}/system/security-config", headers=_h(controller_token), timeout=30)
        assert cfg.status_code == 403, cfg.text

