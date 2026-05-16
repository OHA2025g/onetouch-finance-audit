"""Audit workspace summary + trends API shape."""
import os

import pytest
import requests

from l4_http_common import resolve_react_app_backend_url, wait_until_api_ready

from app.services.audit_workspace_service import catalog_pass_fail_not_run, control_is_stale

_L4_BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "").strip() or (resolve_react_app_backend_url() or "")
API = f"{_L4_BASE.rstrip('/')}/api" if _L4_BASE else ""
_skip_http = pytest.mark.skipif(
    not _L4_BASE,
    reason="REACT_APP_BACKEND_URL not set — skip audit workspace HTTP tests",
)


def _login_cfo() -> str:
    wait_until_api_ready(API, timeout_s=60.0)
    r = requests.post(
        f"{API}/auth/login",
        json={"email": "cfo@onetouch.ai", "password": "demo1234"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def cfo_token():
    return _login_cfo()


def test_pass_rate_uses_ran_controls_only():
    pfn = {"pass": 2, "fail": 1, "not_run": 5}
    ran = pfn["pass"] + pfn["fail"]
    rate = round(100.0 * pfn["pass"] / ran, 1)
    assert rate == 66.7


def test_catalog_pass_fail_not_run_unit():
    controls = [
        {"last_run_at": "2026-01-01T00:00:00+00:00", "last_run_pass": True},
        {"last_run_at": "2026-01-01T00:00:00+00:00", "last_run_pass": False},
        {"last_run_at": None},
    ]
    pfn = catalog_pass_fail_not_run(controls)
    assert pfn == {"pass": 1, "fail": 1, "not_run": 1}


def test_control_is_stale_unit():
    old = {"last_run_at": "2020-01-01T00:00:00+00:00", "frequency": "daily"}
    assert control_is_stale(old) is True
    fresh = {"last_run_at": "2099-01-01T00:00:00+00:00", "frequency": "daily"}
    assert control_is_stale(fresh) is False


@_skip_http
def test_audit_dashboard_includes_summary_and_trends(cfo_token):
    headers = {"Authorization": f"Bearer {cfo_token}"}
    r = requests.get(f"{API}/dashboard/audit", headers=headers, timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert "controls" in data and len(data["controls"]) >= 1
    summary = data.get("summary")
    assert summary is not None
    for key in (
        "audit_readiness_pct",
        "open_exceptions_count",
        "open_exposure_usd",
        "pass_fail_not_run",
        "pass_rate_pct",
        "stale_control_count",
        "critical_failing_count",
        "by_process",
        "top_failing_controls",
        "heatmap",
        "control_count",
    ):
        assert key in summary, key
    if summary["by_process"]:
        row = summary["by_process"][0]
        assert "process" in row and "control_count" in row
        assert isinstance(row["control_count"], int)
    if summary.get("heatmap"):
        assert "fail_count" in summary["heatmap"][0]
    pfn = summary["pass_fail_not_run"]
    assert set(pfn.keys()) >= {"pass", "fail", "not_run"}
    trends = data.get("trends")
    assert trends is not None
    assert isinstance(trends.get("series"), list)
    assert trends.get("days", 0) >= 7


@_skip_http
def test_audit_trends_endpoint(cfo_token):
    headers = {"Authorization": f"Bearer {cfo_token}"}
    r = requests.get(f"{API}/dashboard/audit/trends", headers=headers, params={"days": 14}, timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert data.get("days") == 14
    assert isinstance(data.get("series"), list)
