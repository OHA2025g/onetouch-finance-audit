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

    def test_summary_dashboard_export_and_bulk(self, tokens):
        for path in ("/cfo/action-queue/summary", "/cfo/action-queue/dashboard", "/cfo/action-queue/trends"):
            r = requests.get(f"{API}{path}", headers=_h(tokens["cfo"]), timeout=60)
            assert r.status_code == 200, f"{path}: {r.text}"
        dash = requests.get(f"{API}/cfo/action-queue/dashboard", headers=_h(tokens["cfo"]), timeout=60).json()
        assert "summary" in dash
        assert "entity_process_matrix" in dash
        assert "sla_burndown" in dash
        trends = dash.get("trends") or {}
        assert "throughput" in trends or "series" in trends

        rx = requests.get(
            f"{API}/cfo/action-queue/export",
            headers=_h(tokens["cfo"]),
            params={"format": "xlsx"},
            timeout=60,
        )
        assert rx.status_code == 200, rx.text
        assert "spreadsheetml" in (rx.headers.get("content-type") or "")

        rlist = requests.get(
            f"{API}/cfo/action-queue",
            headers=_h(tokens["cfo"]),
            params={"refresh": True, "limit": 5, "sort": "materiality"},
            timeout=60,
        )
        assert rlist.status_code == 200, rlist.text
        ids = [x["id"] for x in (rlist.json().get("items") or [])[:2]]
        if len(ids) >= 2:
            rb = requests.post(
                f"{API}/cfo/action/bulk",
                headers=_h(tokens["cfo"]),
                json={"ids": ids, "action": "escalate", "note": "L4 bulk test"},
                timeout=60,
            )
            assert rb.status_code == 200, rb.text
            assert rb.json().get("succeeded", 0) >= 1

    def test_cursor_pagination(self, tokens):
        r1 = requests.get(
            f"{API}/cfo/action-queue",
            headers=_h(tokens["cfo"]),
            params={"refresh": True, "limit": 3, "sort": "score"},
            timeout=60,
        )
        assert r1.status_code == 200, r1.text
        b1 = r1.json()
        if not b1.get("has_more") or not b1.get("next_cursor"):
            pytest.skip("not enough items for cursor pagination smoke test")
        r2 = requests.get(
            f"{API}/cfo/action-queue",
            headers=_h(tokens["cfo"]),
            params={"limit": 3, "sort": "score", "cursor": b1["next_cursor"]},
            timeout=60,
        )
        assert r2.status_code == 200, r2.text
        ids1 = {x["id"] for x in b1.get("items") or []}
        ids2 = {x["id"] for x in r2.json().get("items") or []}
        assert ids1.isdisjoint(ids2), "cursor page should not repeat prior ids"

    def test_scoped_entity_list(self, tokens):
        r = requests.get(
            f"{API}/cfo/action-queue",
            headers=_h(tokens["cfo"]),
            params={"refresh": True, "limit": 50, "entity_code": "US-HQ"},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        for it in r.json().get("items") or []:
            ent = it.get("entity") or (it.get("detail") or {}).get("entity")
            assert ent in (None, "US-HQ"), f"unexpected entity {ent!r} for US-HQ scope"
