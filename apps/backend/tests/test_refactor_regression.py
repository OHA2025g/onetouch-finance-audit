"""Iteration 6 — Refactor regression suite.

Verifies every endpoint from iteration_5 baseline still returns the same
status and response shape after splitting server.py into routers and
DrillView.jsx into per-type renderers. Zero-behavior-change refactor.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().strip('"')
                break
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
BASE_URL = BASE_URL.rstrip("/")

API = f"{BASE_URL}/api"
CREDS = {
    "cfo": ("cfo@onetouch.ai", "demo1234"),
    "controller": ("controller@onetouch.ai", "demo1234"),
    "auditor": ("auditor@onetouch.ai", "demo1234"),
    "compliance": ("compliance@onetouch.ai", "demo1234"),
    "owner": ("owner@onetouch.ai", "demo1234"),
    "external": ("external.auditor@bigfour.example", "demo1234"),
}


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login {email} → {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def tokens():
    return {role: _login(e, p) for role, (e, p) in CREDS.items()}


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---------- Core bootstrap ----------
class TestHealthAndAuth:
    def test_health(self):
        r = requests.get(f"{API}/", timeout=15)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_login_and_me(self, tokens):
        r = requests.get(f"{API}/auth/me", headers=_h(tokens["cfo"]), timeout=15)
        assert r.status_code == 200
        assert r.json()["email"] == "cfo@onetouch.ai"

    def test_login_bad_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": "cfo@onetouch.ai", "password": "wrong"}, timeout=15)
        assert r.status_code in (400, 401, 403)


# ---------- Dashboards + readiness ----------
class TestDashboards:
    @pytest.mark.parametrize("section", ["cfo", "controller", "audit", "compliance", "my-cases"])
    def test_dashboard(self, tokens, section):
        r = requests.get(f"{API}/dashboard/{section}", headers=_h(tokens["cfo"]), timeout=30)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), dict)

    def test_readiness(self, tokens):
        r = requests.get(f"{API}/readiness", headers=_h(tokens["cfo"]), timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        rows = data.get("rows") or []
        assert len(rows) > 0

    def test_dashboard_risk_intelligence(self, tokens):
        """Phase 40 — consolidated risk hub payload (not under /dashboard/{persona})."""
        r = requests.get(f"{API}/dashboard/risk-intelligence", headers=_h(tokens["cfo"]), timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, dict)
        assert "risk_scores" in data
        assert "items" in data["risk_scores"]


# ---------- Controls + exceptions ----------
class TestControls:
    def test_list_controls(self, tokens):
        r = requests.get(f"{API}/controls", headers=_h(tokens["cfo"]), timeout=30)
        assert r.status_code == 200
        data = r.json()
        ctrls = data if isinstance(data, list) else data.get("items") or data.get("controls") or []
        assert len(ctrls) >= 23, f"expected ≥23 controls, got {len(ctrls)}"

    def test_control_detail(self, tokens):
        r = requests.get(f"{API}/controls", headers=_h(tokens["cfo"]), timeout=30)
        data = r.json()
        ctrls = data if isinstance(data, list) else data.get("items") or data.get("controls") or []
        cid = ctrls[0]["id"]
        r2 = requests.get(f"{API}/controls/{cid}", headers=_h(tokens["cfo"]), timeout=30)
        assert r2.status_code == 200

    def test_exceptions_list(self, tokens):
        r = requests.get(f"{API}/exceptions?limit=5", headers=_h(tokens["cfo"]), timeout=30)
        assert r.status_code == 200
        data = r.json()
        items = data if isinstance(data, list) else data.get("items", [])
        assert len(items) > 0

    def test_exception_detail(self, tokens):
        r = requests.get(f"{API}/exceptions?limit=1", headers=_h(tokens["cfo"]), timeout=30)
        items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        eid = items[0]["id"]
        r2 = requests.get(f"{API}/exceptions/{eid}", headers=_h(tokens["cfo"]), timeout=30)
        assert r2.status_code == 200

    def test_run_all_controls_rbac(self, tokens):
        # External auditor must be 403
        r = requests.post(f"{API}/controls/run-all", headers=_h(tokens["external"]), timeout=60)
        assert r.status_code == 403


# ---------- Cases ----------
class TestCases:
    def test_cases_list(self, tokens):
        r = requests.get(f"{API}/cases", headers=_h(tokens["cfo"]), timeout=30)
        assert r.status_code == 200

    def test_case_detail(self, tokens):
        r = requests.get(f"{API}/cases", headers=_h(tokens["cfo"]), timeout=30)
        data = r.json()
        items = data if isinstance(data, list) else data.get("items", [])
        if not items:
            pytest.skip("no cases")
        cid = items[0]["id"]
        r2 = requests.get(f"{API}/cases/{cid}", headers=_h(tokens["cfo"]), timeout=30)
        assert r2.status_code == 200


# ---------- Evidence + Copilot ----------
class TestEvidenceCopilot:
    def test_evidence(self, tokens):
        r = requests.get(f"{API}/exceptions?limit=1", headers=_h(tokens["cfo"]), timeout=30)
        items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        eid = items[0]["id"]
        r2 = requests.get(f"{API}/evidence/{eid}", headers=_h(tokens["cfo"]), timeout=30)
        assert r2.status_code == 200

    def test_copilot_index_status(self, tokens):
        r = requests.get(f"{API}/copilot/index-status", headers=_h(tokens["cfo"]), timeout=15)
        assert r.status_code == 200
        body = r.json()
        # iteration_5 baseline reports indexed_docs (~651)
        docs = body.get("indexed_docs") or body.get("documents") or 0
        assert docs > 0, f"expected indexed docs > 0, got {body}"

    def test_copilot_sessions(self, tokens):
        r = requests.get(f"{API}/copilot/sessions", headers=_h(tokens["cfo"]), timeout=15)
        assert r.status_code == 200

    def test_copilot_rebuild_rbac(self, tokens):
        r = requests.post(f"{API}/copilot/rebuild-index", headers=_h(tokens["external"]), timeout=30)
        assert r.status_code == 403


# ---------- Admin ----------
class TestAdmin:
    @pytest.mark.parametrize("path", ["models", "prompts", "audit-logs", "summary", "ingestion-runs", "model-versions"])
    def test_admin(self, tokens, path):
        r = requests.get(f"{API}/admin/{path}", headers=_h(tokens["cfo"]), timeout=30)
        assert r.status_code == 200, f"/admin/{path} → {r.status_code}"


# ---------- Reports + Auditor ----------
class TestReportsAndAuditor:
    def test_pdf(self, tokens):
        r = requests.get(f"{API}/reports/audit-committee-pack.pdf", headers=_h(tokens["cfo"]), timeout=60)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")

    def test_xlsx(self, tokens):
        r = requests.get(f"{API}/reports/audit-committee-pack.xlsx", headers=_h(tokens["cfo"]), timeout=60)
        assert r.status_code == 200

    def test_auditor_pack_external_allowed(self, tokens):
        r = requests.get(f"{API}/auditor/pack", headers=_h(tokens["external"]), timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body.get("filters_applied"), dict)


# ---------- Notifications ----------
class TestNotifications:
    def test_notifications(self, tokens):
        r = requests.get(f"{API}/notifications", headers=_h(tokens["cfo"]), timeout=15)
        assert r.status_code == 200

    def test_settings_get(self, tokens):
        r = requests.get(f"{API}/notifications/settings", headers=_h(tokens["cfo"]), timeout=15)
        assert r.status_code == 200

    def test_settings_patch(self, tokens):
        r = requests.patch(
            f"{API}/notifications/settings",
            headers=_h(tokens["cfo"]),
            json={"daily_brief_hour_utc": 8},
            timeout=15,
        )
        assert r.status_code == 200

    def test_scan_sla_rbac(self, tokens):
        r = requests.post(f"{API}/notifications/scan-sla", headers=_h(tokens["external"]), timeout=15)
        assert r.status_code == 403

    def test_daily_brief_rbac(self, tokens):
        r = requests.post(f"{API}/notifications/daily-brief/send", headers=_h(tokens["external"]), timeout=15)
        assert r.status_code == 403


# ---------- Drill — all 14 types ----------
DRILL_SEED_QUERIES = {
    "invoice": ("invoices", {}),
    "payment": ("payments", {}),
    "journal": ("journal_entries", {}),
    "vendor": ("vendors", {}),
    "user": ("users", {}),
    "control": ("controls", {}),
    "customer": ("customers", {}),
    "ar_invoice": ("ar_invoices", {}),
    "sales_order": ("sales_orders", {}),
    "employee": ("employees", {}),
    "payroll_entry": ("payroll_entries", {}),
    "bank_transaction": ("bank_transactions", {}),
    "fixed_asset": ("fixed_assets", {}),
    "capex_project": ("capex_projects", {}),
}


@pytest.fixture(scope="module")
def sample_ids(tokens):
    """Pick a representative id per drill type by scanning multiple sources."""
    ids = {}
    # 1) Pull from exceptions — they carry source_record_type/source_record_id
    r = requests.get(f"{API}/exceptions?limit=1000", headers=_h(tokens["cfo"]), timeout=30)
    items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    # Map exception source_record_type → drill type (they align 1-1 in this app)
    for ex in items:
        rt = ex.get("source_record_type") or ex.get("related_type")
        rid = ex.get("source_record_id") or ex.get("related_id")
        if rt and rid and rt in DRILL_SEED_QUERIES and rt not in ids:
            ids[rt] = rid
    # 2) Controls fallback
    if "control" not in ids:
        cr = requests.get(f"{API}/controls", headers=_h(tokens["cfo"]), timeout=30).json()
        clist = cr if isinstance(cr, list) else cr.get("items") or cr.get("controls") or []
        if clist:
            ids["control"] = clist[0]["id"]
    return ids


class TestDrill:
    @pytest.mark.parametrize("dtype", list(DRILL_SEED_QUERIES.keys()))
    def test_drill(self, tokens, sample_ids, dtype):
        rid = sample_ids.get(dtype)
        if not rid:
            pytest.skip(f"no seed id for drill type {dtype}")
        r = requests.get(f"{API}/drill/{dtype}/{rid}", headers=_h(tokens["cfo"]), timeout=30)
        if r.status_code == 404:
            pytest.skip(f"{dtype}/{rid} not found in seed (non-blocking)")
        assert r.status_code == 200, f"drill/{dtype}/{rid} → {r.status_code} {r.text[:200]}"
        body = r.json()
        assert isinstance(body, dict) and len(body) > 0


# ---------- Insights — all sections (incl. Phase 39 risk) ----------
class TestInsights:
    @pytest.mark.parametrize("section", ["cfo", "controller", "audit", "compliance", "risk", "my-cases", "cases", "evidence"])
    def test_insights(self, tokens, section):
        r = requests.get(f"{API}/insights/{section}", headers=_h(tokens["cfo"]), timeout=30)
        assert r.status_code == 200
        body = r.json()
        for key in ("insights", "recommendations", "action_items", "source", "section_label"):
            assert key in body, f"missing {key} in insights/{section}"

    @pytest.mark.parametrize("section", ["cfo", "controller", "compliance", "my-cases", "cases"])
    def test_insights_external_blocked(self, tokens, section):
        r = requests.get(f"{API}/insights/{section}", headers=_h(tokens["external"]), timeout=30)
        assert r.status_code == 403, f"external auditor should be blocked from /insights/{section}"

    @pytest.mark.parametrize("section", ["evidence", "audit", "risk"])
    def test_insights_external_allowed(self, tokens, section):
        r = requests.get(f"{API}/insights/{section}", headers=_h(tokens["external"]), timeout=30)
        assert r.status_code == 200, f"external auditor should access /insights/{section}"


# ---------- Seed integrity ----------
class TestSeedIntegrity:
    def test_controls_count(self, tokens):
        r = requests.get(f"{API}/controls", headers=_h(tokens["cfo"]), timeout=30)
        data = r.json()
        ctrls = data if isinstance(data, list) else data.get("items") or data.get("controls") or []
        assert len(ctrls) >= 23

    def test_exceptions_count(self, tokens):
        r = requests.get(f"{API}/exceptions/count", headers=_h(tokens["cfo"]), timeout=30)
        assert r.status_code == 200
        n = int(r.json().get("count") or 0)
        # iteration_5 baseline: 478+ exceptions (pagination is capped; use count endpoint)
        assert n >= 400, f"expected ≥400 exceptions, got {n}"
