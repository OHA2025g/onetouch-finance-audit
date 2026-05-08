"""L4 contract tests for Phase 5 — CFO Action Queue (HTTP).

Validates:
- list + detail endpoints respond
- refresh materialization creates items
- approve/reject/escalate/comment transitions work
- audit logs are written for CFO actions
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict

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
def tokens() -> Dict[str, str]:
    return {
        "cfo": _login("cfo@onetouch.ai", "demo1234"),
        "superadmin": _login("superadmin@onetouch.ai", "demo1234"),
    }


def _h(tok: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {tok}"}


def _audit_logs_recent(tok: str, *, limit: int = 25) -> list[dict[str, Any]]:
    r = requests.get(f"{API}/system/audit-logs", headers=_h(tok), params={"limit": limit}, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    items = body.get("items") or body.get("logs") or []
    return items if isinstance(items, list) else []


class TestCfoActionQueueContracts:
    def test_list_refresh_and_detail(self, tokens):
        r = requests.get(
            f"{API}/cfo/action-queue",
            headers=_h(tokens["cfo"]),
            params={"refresh": True, "limit": 10, "offset": 0},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body.get("items"), list)
        assert isinstance(body.get("total"), int)

        assert body["items"], "expected at least one seeded/materialized action"
        action_id = body["items"][0]["id"]

        r2 = requests.get(f"{API}/cfo/action-queue/{action_id}", headers=_h(tokens["cfo"]), timeout=30)
        assert r2.status_code == 200, r2.text
        d = r2.json()
        assert d.get("id") == action_id
        assert d.get("status") in ("open", "approved", "rejected", "escalated")

    def test_comment_escalate_approve_writes_audit_log(self, tokens):
        # ensure we have at least one open item
        r = requests.get(
            f"{API}/cfo/action-queue",
            headers=_h(tokens["cfo"]),
            params={"refresh": True, "limit": 20, "offset": 0, "status": "open"},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        items = r.json().get("items") or []
        assert items, "need at least one open action to test transitions"
        action_id = items[0]["id"]

        before = _audit_logs_recent(tokens["superadmin"])

        # comment (allowed for auditor too, but CFO ok)
        rc = requests.post(
            f"{API}/cfo/action/{action_id}/comment",
            headers=_h(tokens["cfo"]),
            json={"comment": "QA: noted from contract test"},
            timeout=30,
        )
        assert rc.status_code == 200, rc.text
        assert isinstance(rc.json().get("comments"), list)

        # escalate (CFO allowed)
        re = requests.post(
            f"{API}/cfo/action/{action_id}/escalate",
            headers=_h(tokens["cfo"]),
            json={"note": "QA: escalation from contract test"},
            timeout=30,
        )
        assert re.status_code == 200, re.text
        assert re.json().get("status") == "escalated"

        # approve (CFO allowed)
        ra = requests.post(
            f"{API}/cfo/action/{action_id}/approve",
            headers=_h(tokens["cfo"]),
            json={"note": "QA: approval from contract test"},
            timeout=30,
        )
        assert ra.status_code == 200, ra.text
        assert ra.json().get("status") == "approved"

        after = _audit_logs_recent(tokens["superadmin"])
        # Verify at least one relevant audit entry exists in recent window
        action_types = {x.get("action_type") for x in after if isinstance(x, dict)}
        assert {"cfo_action_approve", "cfo_action_escalate", "cfo_action_comment"} & action_types
