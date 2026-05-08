"""L4 roadmap API surface smoke tests (integrations alias, KPI refresh, SRS REST trees)."""

from __future__ import annotations

import os

import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL"):
                    BASE_URL = line.split("=", 1)[1].strip().strip('"')
                    break
    except Exception:
        pass
assert BASE_URL, "REACT_APP_BACKEND_URL not configured"
API = f"{BASE_URL.rstrip('/')}/api"


def _headers():
    r = requests.post(f"{API}/auth/login", json={"email": "cfo@onetouch.ai", "password": "demo1234"}, timeout=30)
    assert r.status_code == 200, r.text
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok, r.text
    return {"Authorization": f"Bearer {tok}"}


def test_integrations_list_alias_matches_connectors():
    h = _headers()
    a = requests.get(f"{API}/connectors", headers=h, timeout=30)
    b = requests.get(f"{API}/integrations", headers=h, timeout=30)
    assert a.status_code == 200 and b.status_code == 200
    assert a.json() == b.json()


def test_kpi_refresh_post():
    h = _headers()
    r = requests.post(f"{API}/kpi/refresh", headers=h, timeout=120)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("status") == "ok"
    assert "cfo_summary" in body


def test_cfo_bff_summary_paths():
    h = _headers()
    for path in (
        "/cfo/summary",
        "/cfo/financial-health",
        "/cfo/risk-summary",
        "/cfo/liquidity-watch",
        "/cfo/working-capital",
        "/cfo/team-performance",
    ):
        r = requests.get(f"{API}{path}", headers=h, timeout=60)
        assert r.status_code == 200, f"{path}: {r.text}"


def test_finance_team_and_rest_trees():
    h = _headers()
    r = requests.get(f"{API}/finance-team/summary", headers=h, timeout=60)
    assert r.status_code == 200, r.text
    for path in (
        "/working-capital/summary",
        "/ar/summary",
        "/ap/summary",
        "/treasury/summary",
        "/budget/versions",
    ):
        rr = requests.get(f"{API}{path}", headers=h, timeout=60)
        assert rr.status_code == 200, f"{path}: {rr.text}"


def test_audit_and_governance_depth():
    h = _headers()
    r = requests.get(f"{API}/audit-depth/gl/accounts", headers=h, timeout=30)
    assert r.status_code == 200, r.text
    j = requests.get(f"{API}/audit-depth/journal-entries?limit=5", headers=h, timeout=30)
    assert j.status_code == 200
    g = requests.get(f"{API}/compliance-depth/rpt/register", headers=h, timeout=30)
    assert g.status_code == 200


def test_wave4_surfaces():
    h = _headers()
    m = requests.get(f"{API}/connectors/matrix", headers=h, timeout=30)
    assert m.status_code == 200
    ei = requests.get(f"{API}/evidence-intelligence/summary", headers=h, timeout=30)
    assert ei.status_code == 200
    tpl = requests.get(f"{API}/reports/templates", headers=h, timeout=30)
    assert tpl.status_code == 200
    live = requests.get(f"{API}/system/health/live", timeout=30)
    assert live.status_code == 200
    assert live.json().get("status") == "live"
