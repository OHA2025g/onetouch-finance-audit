"""L4 HTTP tests for rollup visualization endpoints (Entity Rollup UI).

Validates stable contracts for:
- GET /rollups/chart/hierarchy
- GET /rollups/chart/scatter
- GET /rollups/snapshots/history
"""

from __future__ import annotations

import os
import uuid

import pytest
import requests

from l4_http_common import resolve_react_app_backend_url, wait_until_api_ready

_L4_BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "").strip() or (resolve_react_app_backend_url() or "")
pytestmark = pytest.mark.skipif(
    not _L4_BASE,
    reason="REACT_APP_BACKEND_URL not set and apps/frontend/.env missing — skip L4 HTTP contract tests",
)
BASE_URL = _L4_BASE
API = f"{BASE_URL.rstrip('/')}/api"

CREDS = {"cfo": ("cfo@onetouch.ai", "demo1234")}


def _wait_api(timeout_s: float = 60.0) -> None:
    wait_until_api_ready(API, timeout_s=timeout_s)


def _login(email: str, password: str) -> str:
    _wait_api()
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def cfo_token() -> str:
    email, password = CREDS["cfo"]
    return _login(email, password)


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def _root_node_id(hier_body: dict) -> str | None:
    if hier_body.get("error"):
        return None
    root = hier_body.get("root") or hier_body.get("node")
    if not root or not root.get("id"):
        return None
    return str(root["id"])


class TestRollupsVizEndpoints:
    def test_chart_hierarchy_returns_children_contract(self, cfo_token: str):
        rh = requests.get(f"{API}/rollups/hierarchy", headers=_h(cfo_token), timeout=30)
        assert rh.status_code == 200, rh.text
        nid = _root_node_id(rh.json())
        if not nid:
            pytest.skip("organization hierarchy not seeded")

        metric = "unresolved_high_risk_exposure"
        r = requests.get(
            f"{API}/rollups/chart/hierarchy",
            headers=_h(cfo_token),
            params={"node_id": nid, "metric": metric},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("metric_key") == metric
        assert body.get("node_id") == nid
        assert isinstance(body.get("children"), list)

    def test_chart_scatter_returns_points_contract(self, cfo_token: str):
        rh = requests.get(f"{API}/rollups/hierarchy", headers=_h(cfo_token), timeout=30)
        assert rh.status_code == 200, rh.text
        nid = _root_node_id(rh.json())
        if not nid:
            pytest.skip("organization hierarchy not seeded")

        r = requests.get(
            f"{API}/rollups/chart/scatter",
            headers=_h(cfo_token),
            params={"node_id": nid},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("node_id") == nid
        pts = body.get("points")
        assert isinstance(pts, list)
        for p in pts[:8]:
            assert isinstance(p.get("entity_code"), str)

    def test_snapshots_history_returns_series_and_sparklines(self, cfo_token: str):
        rh = requests.get(f"{API}/rollups/hierarchy", headers=_h(cfo_token), timeout=30)
        assert rh.status_code == 200, rh.text
        nid = _root_node_id(rh.json())
        if not nid:
            pytest.skip("organization hierarchy not seeded")

        r = requests.get(
            f"{API}/rollups/snapshots/history",
            headers=_h(cfo_token),
            params={"node_id": nid, "limit": 24},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("node_id") == nid
        assert isinstance(body.get("series"), list)
        assert isinstance(body.get("sparklines"), dict)
        assert "audit_readiness_pct" in body["sparklines"]
        assert isinstance(body.get("deltas_latest_pair"), dict)
        assert isinstance(body.get("points_count"), int)

    def test_unknown_node_returns_404_for_chart_hierarchy(self, cfo_token: str):
        fake = f"rollup-node-missing-{uuid.uuid4().hex[:10]}"
        r = requests.get(
            f"{API}/rollups/chart/hierarchy",
            headers=_h(cfo_token),
            params={"node_id": fake},
            timeout=30,
        )
        assert r.status_code == 404, r.text
