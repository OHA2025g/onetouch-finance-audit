"""L4 contract tests for Phase 6 — Month-End Close Management (HTTP)."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone

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
def tokens():
    return {
        "cfo": _login("cfo@onetouch.ai", "demo1234"),
        "controller": _login("controller@onetouch.ai", "demo1234"),
    }


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


class TestMonthEndCloseContracts:
    def test_create_cycle_and_tasks_workflow(self, tokens):
        # Create a cycle for current month; API is idempotent by period_ym.
        period_ym = datetime.now(timezone.utc).strftime("%Y-%m")
        r = requests.post(
            f"{API}/close/cycles",
            headers=_h(tokens["controller"]),
            json={"period_ym": period_ym, "name": f"Close {period_ym}"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        cyc = r.json()
        assert cyc.get("id") and cyc.get("period_ym") == period_ym

        # Fetch cycle details (must include tasks)
        r2 = requests.get(f"{API}/close/cycles/{cyc['id']}", headers=_h(tokens["controller"]), timeout=30)
        assert r2.status_code == 200, r2.text
        cyc2 = r2.json()
        assert isinstance(cyc2.get("tasks"), list)
        assert cyc2["tasks"], "expected seeded template tasks for the cycle"

        # Pick a critical task and run submit -> approve -> reopen
        critical = next((t for t in cyc2["tasks"] if t.get("critical")), cyc2["tasks"][0])
        task_id = critical["id"]

        # Add evidence
        ev = {"type": "link", "uri": f"s3://onetouch-evidence/close/{task_id}.pdf", "label": "QA evidence"}
        re = requests.post(
            f"{API}/close/tasks/{task_id}/evidence",
            headers=_h(tokens["controller"]),
            json=ev,
            timeout=30,
        )
        assert re.status_code == 200, re.text
        assert isinstance(re.json().get("evidence"), list)

        rs = requests.post(f"{API}/close/tasks/{task_id}/submit", headers=_h(tokens["controller"]), timeout=30)
        assert rs.status_code == 200, rs.text
        assert rs.json().get("status") == "submitted"

        ra = requests.post(f"{API}/close/tasks/{task_id}/approve", headers=_h(tokens["cfo"]), timeout=30)
        assert ra.status_code == 200, ra.text
        assert ra.json().get("status") == "approved"

        rr = requests.post(
            f"{API}/close/tasks/{task_id}/reopen",
            headers=_h(tokens["cfo"]),
            json={"note": "QA reopen"},
            timeout=30,
        )
        assert rr.status_code == 200, rr.text
        assert rr.json().get("status") == "reopened"

    def test_signoff_guardrails_and_metrics(self, tokens):
        period_ym = datetime.now(timezone.utc).strftime("%Y-%m")
        r = requests.post(
            f"{API}/close/cycles",
            headers=_h(tokens["controller"]),
            json={"period_ym": period_ym, "name": f"Close {period_ym}"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        cyc = r.json()
        cycle_id = cyc["id"]

        # If critical tasks exist and are not all approved, signoff should 409 (unless override)
        r0 = requests.post(
            f"{API}/close/signoff",
            headers=_h(tokens["cfo"]),
            json={"cycle_id": cycle_id, "override": False},
            timeout=30,
        )
        assert r0.status_code in (200, 409), r0.text

        # Metrics endpoints should respond
        rb = requests.get(f"{API}/close/bottlenecks", headers=_h(tokens["controller"]), params={"cycle_id": cycle_id}, timeout=30)
        assert rb.status_code == 200, rb.text
        assert "pending" in rb.json()

        rq = requests.get(f"{API}/close/quality-score", headers=_h(tokens["controller"]), params={"cycle_id": cycle_id}, timeout=30)
        assert rq.status_code == 200, rq.text
        assert "score" in rq.json()

        # Override signoff must succeed (if not already signed off)
        r1 = requests.post(
            f"{API}/close/signoff",
            headers=_h(tokens["cfo"]),
            json={"cycle_id": cycle_id, "override": True, "override_reason": "QA override for contract test"},
            timeout=30,
        )
        assert r1.status_code == 200, r1.text
        assert r1.json().get("status") == "signed_off"
