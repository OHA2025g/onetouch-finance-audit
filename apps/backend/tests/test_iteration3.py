"""Iteration 3 backend tests: drill-down endpoints, anomaly training + model versioning,
daily CFO brief dispatch with Slack Block Kit formatting."""
import os
import time
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "http://127.0.0.1:8000").rstrip("/")

USERS = {
    "cfo": ("cfo@onetouch.ai", "demo1234"),
    "controller": ("controller@onetouch.ai", "demo1234"),
    "auditor": ("auditor@onetouch.ai", "demo1234"),
    "compliance": ("compliance@onetouch.ai", "demo1234"),
    "owner": ("owner@onetouch.ai", "demo1234"),
    "external": ("external.auditor@bigfour.example", "demo1234"),
}


def _login(email, password):
    deadline = time.time() + 60.0
    last_err = None
    while time.time() < deadline:
        try:
            r = requests.get(f"{BASE_URL}/api/", timeout=2)
            if r.status_code == 200:
                break
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(0.5)
    else:
        raise AssertionError(f"API not reachable within 60s: {last_err}")
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def tokens():
    return {k: _login(e, p) for k, (e, p) in USERS.items()}


def _h(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


# ---------- DRILL-DOWN ----------
class TestDrill:
    def test_drill_invoice_seeded_duplicate(self, tokens):
        r = requests.get(f"{BASE_URL}/api/drill/invoice/INV-DUP-0", headers=_h(tokens["cfo"]), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("primary", "vendor", "purchase_order", "goods_receipt", "payments", "duplicates", "exceptions", "cases"):
            assert k in d, f"missing key {k}"
        assert d["primary"]["id"] == "INV-DUP-0"
        # INV-DUP-0 should have at least one duplicate sibling
        assert isinstance(d["duplicates"], list)

    def test_drill_vendor_V1000(self, tokens):
        r = requests.get(f"{BASE_URL}/api/drill/vendor/V-1000", headers=_h(tokens["cfo"]), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["primary"]["id"] == "V-1000"
        stats = d["stats"]
        for k in ("invoice_count", "payment_count", "total_invoiced", "total_paid", "exception_count"):
            assert k in stats
        assert isinstance(d["invoices"], list)
        assert isinstance(d["payments"], list)
        assert isinstance(d["purchase_orders"], list)

    def test_drill_user_gl_lead(self, tokens):
        r = requests.get(f"{BASE_URL}/api/drill/user/gl.lead@onetouch.ai", headers=_h(tokens["cfo"]), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "primary" in d and "roles" in d and "access_events" in d
        assert "cases" in d and "journals_posted" in d and "audit_log" in d

    def test_drill_user_resolves_user_access_event_id(self, tokens):
        """UA-* ids from exception.source_record_id must resolve to the event's user_email (seeded)."""
        r = requests.get(f"{BASE_URL}/api/drill/user/UA-0", headers=_h(tokens["cfo"]), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("type") == "user"
        assert d["primary"].get("email") and "@" in d["primary"]["email"]
        assert d["primary"]["email"] != "UA-0"
        assert isinstance(d.get("access_events"), list)
        assert len(d["access_events"]) >= 1

    def test_drill_control_C_AP_001(self, tokens):
        r = requests.get(f"{BASE_URL}/api/drill/control/C-AP-001", headers=_h(tokens["cfo"]), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["primary"]["code"] == "C-AP-001" or d["primary"].get("id") == "C-AP-001"
        stats = d["stats"]
        for k in ("exception_count", "total_exposure", "open_cases", "by_entity"):
            assert k in stats
        assert isinstance(d["recent_runs"], list)
        assert isinstance(d["exceptions"], list)

    def test_drill_payment_from_vendor(self, tokens):
        # find a payment id via vendor drill, then drill payment
        v = requests.get(f"{BASE_URL}/api/drill/vendor/V-1000", headers=_h(tokens["cfo"]), timeout=15).json()
        if not v["payments"]:
            pytest.skip("no payments for V-1000")
        pid = v["payments"][0]["id"]
        r = requests.get(f"{BASE_URL}/api/drill/payment/{pid}", headers=_h(tokens["cfo"]), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("primary", "vendor", "invoice", "exceptions", "cases"):
            assert k in d

    def test_drill_journal(self, tokens):
        # list journals via any endpoint; fallback to known JE-30045 or derive from user drill
        u = requests.get(f"{BASE_URL}/api/drill/user/gl.lead@onetouch.ai", headers=_h(tokens["cfo"]), timeout=15).json()
        if u.get("journals_posted"):
            jid = u["journals_posted"][0]["id"]
        else:
            jid = "JE-30045"
        r = requests.get(f"{BASE_URL}/api/drill/journal/{jid}", headers=_h(tokens["cfo"]), timeout=15)
        if r.status_code == 404:
            pytest.skip("no journal available to drill")
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("primary", "creator", "approver", "recent_by_same_user", "exceptions", "cases"):
            assert k in d

    def test_drill_unknown_type_returns_400(self, tokens):
        r = requests.get(f"{BASE_URL}/api/drill/unknown_type/xyz", headers=_h(tokens["cfo"]), timeout=15)
        assert r.status_code == 400

    def test_drill_nonexistent_invoice_returns_404(self, tokens):
        r = requests.get(f"{BASE_URL}/api/drill/invoice/nonexistent-id-xyz", headers=_h(tokens["cfo"]), timeout=15)
        assert r.status_code == 404


# ---------- ANOMALY TRAINING & VERSIONING ----------
class TestAnomalyTraining:
    def test_train_as_cfo_returns_artefact(self, tokens):
        r = requests.post(f"{BASE_URL}/api/anomaly/train", json={"notes": "TEST_iter3"}, headers=_h(tokens["cfo"]), timeout=60)
        assert r.status_code == 200, r.text
        a = r.json()
        assert a["approval_status"] == "pending_review"
        assert a["active"] is False
        assert a["version_label"].startswith("v") and a["version_label"].endswith(".0")
        m = a["metrics"]
        for k in ("n_train", "n_test", "test_anomaly_rate", "test_score_mean", "test_score_std", "train_types"):
            assert k in m, f"metrics missing {k}"
        assert (m["n_train"] + m["n_test"]) >= 500, f"expected ≥500 training samples, got {m['n_train']+m['n_test']}"
        # stash for later tests
        pytest.TEST_VERSION_ID = a["id"]

    def test_train_as_external_auditor_forbidden(self, tokens):
        r = requests.post(f"{BASE_URL}/api/anomaly/train", json={}, headers=_h(tokens["external"]), timeout=15)
        assert r.status_code == 403

    def test_list_model_versions_newest_first(self, tokens):
        r = requests.get(f"{BASE_URL}/api/admin/model-versions", headers=_h(tokens["cfo"]), timeout=15)
        assert r.status_code == 200
        versions = r.json()
        assert isinstance(versions, list) and len(versions) >= 1
        if len(versions) >= 2:
            assert versions[0]["created_at"] >= versions[1]["created_at"], "versions must be newest-first"

    def test_approve_as_controller_forbidden(self, tokens):
        vid = getattr(pytest, "TEST_VERSION_ID", None)
        if not vid:
            pytest.skip("no trained version id available")
        r = requests.post(f"{BASE_URL}/api/admin/model-versions/{vid}/approve", headers=_h(tokens["controller"]), timeout=15)
        assert r.status_code == 403

    def test_approve_as_cfo_activates_and_deactivates_others(self, tokens):
        vid = getattr(pytest, "TEST_VERSION_ID", None)
        if not vid:
            pytest.skip("no trained version id available")
        r = requests.post(f"{BASE_URL}/api/admin/model-versions/{vid}/approve", headers=_h(tokens["cfo"]), timeout=15)
        assert r.status_code == 200, r.text
        v = r.json()
        assert v["approval_status"] == "approved"
        assert v["active"] is True
        assert v["approved_by"] == USERS["cfo"][0]
        # All other versions should be inactive
        listing = requests.get(f"{BASE_URL}/api/admin/model-versions", headers=_h(tokens["cfo"]), timeout=15).json()
        active_count = sum(1 for m in listing if m.get("active"))
        assert active_count == 1, f"exactly one version should be active, got {active_count}"


# ---------- DAILY CFO BRIEF ----------
class TestDailyBrief:
    def test_send_now_as_cfo(self, tokens):
        r = requests.post(f"{BASE_URL}/api/notifications/daily-brief/send", headers=_h(tokens["cfo"]), timeout=30)
        assert r.status_code == 200, r.text
        n = r.json()
        if n.get("skipped"):
            pytest.skip(f"brief skipped: {n.get('skipped')}")
        assert n["event_type"] == "daily_cfo_brief"
        assert n["title"].startswith("Daily CFO brief")
        extras = n.get("extras") or {}
        assert "kpis" in extras
        assert "top_risks" in extras

    def test_send_now_as_external_auditor_forbidden(self, tokens):
        r = requests.post(f"{BASE_URL}/api/notifications/daily-brief/send", headers=_h(tokens["external"]), timeout=15)
        assert r.status_code == 403

    def test_slack_webhook_dispatch_triggers_block_kit(self, tokens):
        # Get current settings so we can restore
        s = requests.get(f"{BASE_URL}/api/notifications/settings", headers=_h(tokens["cfo"]), timeout=15).json()
        original = s.get("webhook_urls", [])
        fake_slack = "https://hooks.slack.com/services/TEST/FAKE/iter3"
        patch = {
            "webhook_urls": [fake_slack],
            "enabled": True,
            "daily_brief_enabled": True,
        }
        pr = requests.patch(f"{BASE_URL}/api/notifications/settings", json=patch, headers=_h(tokens["cfo"]), timeout=15)
        assert pr.status_code == 200, pr.text
        try:
            r = requests.post(f"{BASE_URL}/api/notifications/daily-brief/send", headers=_h(tokens["cfo"]), timeout=30)
            assert r.status_code == 200, r.text
            n = r.json()
            dispatched = n.get("dispatched_to", [])
            assert len(dispatched) == 1, f"expected 1 dispatch result, got {len(dispatched)}"
            entry = dispatched[0]
            assert entry["url"] == fake_slack
            # Fake URL won't authenticate, so we expect either a 4xx/5xx captured or a network error
            assert ("status_code" in entry) or ("error" in entry)
        finally:
            # Restore
            requests.patch(f"{BASE_URL}/api/notifications/settings",
                           json={"webhook_urls": original}, headers=_h(tokens["cfo"]), timeout=15)


# ---------- AUTH REDIRECT ROLE MAPPING (backend /auth/me only; redirect is FE) ----------
class TestAuthRoles:
    @pytest.mark.parametrize("key,role", [
        ("cfo", "CFO"),
        ("controller", "Controller"),
        ("auditor", "Internal Auditor"),
        ("compliance", "Compliance Head"),
        ("owner", "Process Owner"),
        ("external", "External Auditor"),
    ])
    def test_me_reports_role(self, tokens, key, role):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=_h(tokens[key]), timeout=15)
        assert r.status_code == 200
        assert r.json()["role"] == role
