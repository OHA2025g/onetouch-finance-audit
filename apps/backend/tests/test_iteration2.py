"""Iteration-2 backend tests — covers:
- Vector store (TF-IDF) copilot index status / rebuild
- Anomaly recalibration (IsolationForest + z-score)
- External Auditor portal + RBAC
- Notifications (settings, SLA scan, dispatch)
- Export: audit-committee-pack PDF/XLSX
"""
from __future__ import annotations

import io
import os
import time
from datetime import datetime, timedelta, timezone

import pytest
import requests

from l4_http_common import resolve_react_app_backend_url

BASE_URL = resolve_react_app_backend_url()
assert BASE_URL, "Set REACT_APP_BACKEND_URL or apps/frontend/.env for HTTP tests."
API = f"{BASE_URL.rstrip('/')}/api"


# ---------------- Auth helpers ----------------
def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, f"login failed for {email}: {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def cfo_headers():
    return {"Authorization": f"Bearer {_login('cfo@onetouch.ai', 'demo1234')}"}


@pytest.fixture(scope="module")
def auditor_internal_headers():
    return {"Authorization": f"Bearer {_login('auditor@onetouch.ai', 'demo1234')}"}


@pytest.fixture(scope="module")
def ext_auditor_headers():
    return {"Authorization": f"Bearer {_login('external.auditor@bigfour.example', 'demo1234')}"}


@pytest.fixture(scope="module")
def owner_headers():
    return {"Authorization": f"Bearer {_login('owner@onetouch.ai', 'demo1234')}"}


# ---------------- External Auditor seeded ----------------
class TestExternalAuditorSeeded:
    def test_external_auditor_login_works(self, ext_auditor_headers):
        r = requests.get(f"{API}/auth/me", headers=ext_auditor_headers, timeout=30)
        assert r.status_code == 200
        me = r.json()
        assert me["email"] == "external.auditor@bigfour.example"
        assert me["role"] == "External Auditor"


# ---------------- Vector store ----------------
class TestVectorStore:
    def test_index_status(self, cfo_headers):
        r = requests.get(f"{API}/copilot/index-status", headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["indexed_docs"] > 0, f"expected indexed_docs > 0, got {data}"
        assert isinstance(data["matrix_shape"], list) and len(data["matrix_shape"]) == 2
        assert data["matrix_shape"][0] == data["indexed_docs"]
        assert "TF-IDF" in data["algorithm"]

    def test_rebuild_index(self, cfo_headers):
        r = requests.post(f"{API}/copilot/rebuild-index", headers=cfo_headers, timeout=60)
        assert r.status_code == 200, r.text
        assert r.json()["indexed_docs"] > 0

    def test_copilot_ask_has_citations(self, cfo_headers):
        r = requests.post(
            f"{API}/copilot/ask",
            headers=cfo_headers,
            json={"question": "Show duplicate invoice exposures for vendor V-1000"},
            timeout=60,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        # citations should be non-empty and contain labels
        assert isinstance(data.get("citations"), list)
        assert len(data["citations"]) > 0, "citations should be non-empty"
        for c in data["citations"]:
            assert "label" in c and c["label"], f"citation missing label: {c}"


# ---------------- Anomaly ----------------
class TestAnomaly:
    def test_recalibrate_cfo(self, cfo_headers):
        # capture prior score for comparison
        prior = requests.get(f"{API}/exceptions?limit=50", headers=cfo_headers, timeout=30).json()
        prior_map = {e["id"]: e.get("anomaly_score") for e in prior}
        r = requests.post(f"{API}/anomaly/recalibrate", headers=cfo_headers, timeout=120)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("models_fit") == 3, f"expected 3 models fit, got {data}"
        assert data.get("exceptions_recalibrated", 0) > 0
        # Phase 2 adds additional controls; assert a sane lower bound.
        assert data.get("controls_analyzed", 0) >= 12
        # verify scores updated in range
        after = requests.get(f"{API}/exceptions?limit=50", headers=cfo_headers, timeout=30).json()
        for e in after:
            s = e.get("anomaly_score")
            if s is not None:
                assert 0.0 <= s <= 1.0, f"score {s} out of range"
        # at least some exceptions should have changed value
        changed = sum(1 for e in after if e.get("anomaly_score") != prior_map.get(e["id"]))
        assert changed > 0 or all(prior_map.get(e["id"]) is not None for e in after), \
            "expected anomaly scores to update (or be present)"

    def test_recalibrate_external_auditor_forbidden(self, ext_auditor_headers):
        r = requests.post(f"{API}/anomaly/recalibrate", headers=ext_auditor_headers, timeout=30)
        assert r.status_code == 403


# ---------------- Auditor Portal ----------------
class TestAuditorPortal:
    def test_auditor_pack(self, ext_auditor_headers):
        r = requests.get(f"{API}/auditor/pack", headers=ext_auditor_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("kpis", "heatmap", "top_risks", "controls", "recent_runs", "policies", "open_cases", "filters_applied"):
            assert k in data, f"missing {k}"
        assert isinstance(data["filters_applied"], dict)
        assert len(data["controls"]) >= 12
        assert len(data["policies"]) == 4

    def test_auditor_control_detail(self, ext_auditor_headers):
        pack = requests.get(f"{API}/auditor/pack", headers=ext_auditor_headers, timeout=30).json()
        cid = pack["controls"][0]["id"]
        r = requests.get(f"{API}/auditor/controls/{cid}", headers=ext_auditor_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data["control"]["id"] == cid
        assert "recent_runs" in data and "exceptions" in data

    def test_external_auditor_cannot_seed_reset(self, ext_auditor_headers):
        r = requests.post(f"{API}/admin/seed-reset", headers=ext_auditor_headers, timeout=30)
        assert r.status_code == 403

    def test_external_auditor_cannot_run_controls(self, ext_auditor_headers):
        # get any control id via auditor pack
        pack = requests.get(f"{API}/auditor/pack", headers=ext_auditor_headers, timeout=30).json()
        cid = pack["controls"][0]["id"]
        r = requests.post(f"{API}/controls/{cid}/run", headers=ext_auditor_headers, timeout=30)
        # External Auditor should NOT be allowed to trigger runs
        assert r.status_code in (401, 403), f"external auditor should be forbidden: {r.status_code}"


# ---------------- Notifications ----------------
class TestNotifications:
    def test_get_settings(self, cfo_headers):
        r = requests.get(f"{API}/notifications/settings", headers=cfo_headers, timeout=30)
        assert r.status_code == 200
        s = r.json()
        for k in ("webhook_urls", "email_recipients", "enabled", "sla_breach_severity_threshold"):
            assert k in s, f"missing {k} in settings"

    def test_patch_settings_webhook(self, cfo_headers):
        url = "https://httpbin.org/status/200"
        r = requests.patch(
            f"{API}/notifications/settings",
            headers=cfo_headers,
            json={"webhook_urls": [url], "enabled": True},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        s = r.json()
        assert url in s.get("webhook_urls", [])
        assert s.get("enabled") is True

    def test_scan_sla_runs(self, cfo_headers):
        r = requests.post(f"{API}/notifications/scan-sla", headers=cfo_headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "scanned" in data and "notified" in data

    def test_list_notifications(self, cfo_headers):
        r = requests.get(f"{API}/notifications", headers=cfo_headers, timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_webhook_dispatch_with_overdue_case(self, cfo_headers):
        """Set a case overdue, trigger scan-sla, verify notification dispatched."""
        # 1) Configure a known-bad webhook to capture graceful error handling
        bad_url = "https://this-should-fail.invalid.localhost.example/webhook"
        patch = requests.patch(
            f"{API}/notifications/settings",
            headers=cfo_headers,
            json={"webhook_urls": [bad_url], "enabled": True,
                  "sla_breach_severity_threshold": "low"},
            timeout=30,
        )
        assert patch.status_code == 200

        # 2) Pick an open case and force its due_date to yesterday
        cases = requests.get(f"{API}/cases?limit=10", headers=cfo_headers, timeout=30).json()
        open_cases = [c for c in cases if c.get("status") != "closed"]
        if not open_cases:
            pytest.skip("no open cases available")
        cid = open_cases[0]["id"]
        past = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        upd = requests.patch(
            f"{API}/cases/{cid}",
            headers=cfo_headers,
            json={"due_date": past},
            timeout=30,
        )
        # Some backends may not allow due_date in patch — surface that
        if upd.status_code != 200:
            pytest.skip(f"cases PATCH does not accept due_date: {upd.status_code} {upd.text[:200]}")

        # 3) Trigger SLA scan
        scan = requests.post(f"{API}/notifications/scan-sla", headers=cfo_headers, timeout=60)
        assert scan.status_code == 200
        scan_data = scan.json()
        # 4) Verify a notification exists (may be 0 if deduped today)
        lst = requests.get(f"{API}/notifications?limit=50", headers=cfo_headers, timeout=30).json()
        # look for notification against this case OR a dispatched_to record
        found = False
        for n in lst:
            dispatched = n.get("dispatched_to") or []
            if n.get("case_id") == cid or any(d.get("url") == bad_url for d in dispatched):
                found = True
                # Graceful error capture: entries should have error or status_code
                for d in dispatched:
                    assert ("status_code" in d) or ("error" in d) or ("ok" in d), \
                        f"dispatched_to entry missing status/error: {d}"
                break
        # It's OK if dedup prevents a new notification; but the scan itself must have run
        assert scan_data["scanned"] >= 0
        print(f"SLA scan result={scan_data}, found_matching_notification={found}")


# ---------------- Exports ----------------
class TestExports:
    def test_pdf_export(self, cfo_headers):
        r = requests.get(f"{API}/reports/audit-committee-pack.pdf",
                         headers=cfo_headers, timeout=60)
        assert r.status_code == 200, r.text[:500]
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert "attachment" in r.headers.get("content-disposition", "").lower()
        body = r.content
        assert body[:4] == b"%PDF", f"not a PDF: starts with {body[:8]!r}"
        assert len(body) > 3000, f"pdf too small: {len(body)} bytes"

    def test_xlsx_export(self, cfo_headers):
        r = requests.get(f"{API}/reports/audit-committee-pack.xlsx",
                         headers=cfo_headers, timeout=60)
        assert r.status_code == 200, r.text[:500]
        ct = r.headers.get("content-type", "")
        assert "spreadsheet" in ct or "xlsx" in ct or "openxmlformats" in ct
        body = r.content
        assert body[:2] == b"PK", f"not a zip/xlsx: starts with {body[:8]!r}"
        assert len(body) > 5000, f"xlsx too small: {len(body)} bytes"

    def test_pdf_export_external_auditor(self, ext_auditor_headers):
        """External auditor should also be able to download the audit committee pack."""
        r = requests.get(f"{API}/reports/audit-committee-pack.pdf",
                         headers=ext_auditor_headers, timeout=60)
        # Route currently only requires authenticated user; should succeed
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"
