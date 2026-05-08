"""L4 contract tests for Phase 39 — Board, Audit Committee and CFO Report Automation (HTTP)."""

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
    return _login("cfo@onetouch.ai", "demo1234")


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


class TestBoardReportingContracts:
    def test_phase39_reports_end_to_end(self, token):
        tpls = requests.get(f"{API}/reports/templates", headers=_h(token), timeout=60)
        assert tpls.status_code == 200, tpls.text
        items = tpls.json().get("items") or []
        assert items

        # generate
        g = requests.post(
            f"{API}/reports/generate",
            headers=_h(token),
            json={"template_id": "tpl-audit-committee-pack", "format": "pdf", "filters": {"entity_code": "US-HQ"}},
            timeout=120,
        )
        assert g.status_code == 200, g.text
        rid = g.json().get("id")
        assert rid

        # get
        one = requests.get(f"{API}/reports/{rid}", headers=_h(token), timeout=60)
        assert one.status_code == 200, one.text
        assert one.json().get("template_id") == "tpl-audit-committee-pack"

        # export pdf
        ep = requests.post(f"{API}/reports/{rid}/export", headers=_h(token), json={"format": "pdf"}, timeout=120)
        assert ep.status_code == 200, ep.text
        assert ep.headers.get("content-type", "").startswith("application/pdf")
        assert len(ep.content) > 100

        # export xlsx
        ex = requests.post(f"{API}/reports/{rid}/export", headers=_h(token), json={"format": "xlsx"}, timeout=120)
        assert ex.status_code == 200, ex.text
        assert "spreadsheetml" in (ex.headers.get("content-type", "") or "")
        assert len(ex.content) > 100

        # signoff
        so = requests.post(f"{API}/reports/{rid}/signoff", headers=_h(token), json={"note": "QA signoff"}, timeout=60)
        assert so.status_code == 200, so.text
        assert so.json().get("status") == "signed_off"

        # versions
        vs = requests.get(f"{API}/reports/versions", headers=_h(token), params={"template_id": "tpl-audit-committee-pack"}, timeout=60)
        assert vs.status_code == 200, vs.text
        assert "items" in vs.json()

