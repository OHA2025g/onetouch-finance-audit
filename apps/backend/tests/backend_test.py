"""End-to-end backend tests for One Touch Audit AI.

Covers: auth, dashboards, controls, exceptions, cases, evidence, copilot,
admin, ingestion, readiness. Uses live backend via REACT_APP_BACKEND_URL.
"""
import gzip
import hashlib
import io
import json
import os
import time
import pytest
import requests

from l4_http_common import resolve_react_app_backend_url, wait_until_api_ready


BASE_URL = resolve_react_app_backend_url()
assert BASE_URL, (
    "Backend base URL not configured. Set REACT_APP_BACKEND_URL (or BACKEND_URL) to the API root "
    "(e.g. http://127.0.0.1:8000), or add it to apps/frontend/.env for local pytest."
)
API = f"{BASE_URL}/api"


def _wait_api(timeout_s: float = 60.0) -> None:
    wait_until_api_ready(API, timeout_s=timeout_s)

CFO = {"email": "cfo@onetouch.ai", "password": "demo1234"}
OWNER = {"email": "owner@onetouch.ai", "password": "demo1234"}
EXTERNAL_AUDITOR = {"email": "external.auditor@bigfour.example", "password": "demo1234"}
SUPERADMIN = {"email": "superadmin@onetouch.ai", "password": "demo1234"}


# --------------- Fixtures ---------------
@pytest.fixture(scope="session", autouse=True)
def _api_ready():
    _wait_api()


@pytest.fixture(scope="session")
def cfo_token():
    _wait_api()
    r = requests.post(f"{API}/auth/login", json=CFO, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def owner_token():
    _wait_api()
    r = requests.post(f"{API}/auth/login", json=OWNER, timeout=30)
    assert r.status_code == 200
    return r.json()["token"]


@pytest.fixture(scope="session")
def cfo_headers(cfo_token):
    return {"Authorization": f"Bearer {cfo_token}"}


@pytest.fixture(scope="session")
def owner_headers(owner_token):
    return {"Authorization": f"Bearer {owner_token}"}


@pytest.fixture(scope="session")
def external_auditor_token():
    _wait_api()
    r = requests.post(f"{API}/auth/login", json=EXTERNAL_AUDITOR, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def external_auditor_headers(external_auditor_token):
    return {"Authorization": f"Bearer {external_auditor_token}"}


@pytest.fixture(scope="session")
def superadmin_token():
    _wait_api()
    r = requests.post(f"{API}/auth/login", json=SUPERADMIN, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def superadmin_headers(superadmin_token):
    return {"Authorization": f"Bearer {superadmin_token}"}


# --------------- Auth ---------------
class TestAuth:
    def test_login_valid(self):
        r = requests.post(f"{API}/auth/login", json=CFO, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "token" in data and isinstance(data["token"], str) and len(data["token"]) > 20
        assert data["user"]["email"] == "cfo@onetouch.ai"
        assert data["user"]["role"] == "CFO"

    def test_login_invalid(self):
        r = requests.post(f"{API}/auth/login",
                          json={"email": "cfo@onetouch.ai", "password": "wrong"}, timeout=30)
        assert r.status_code == 401

    def test_me(self, cfo_headers):
        r = requests.get(f"{API}/auth/me", headers=cfo_headers, timeout=30)
        assert r.status_code == 200
        assert r.json()["email"] == "cfo@onetouch.ai"

    def test_me_unauth(self):
        r = requests.get(f"{API}/auth/me", timeout=30)
        assert r.status_code in (401, 403)


# --------------- Dashboards ---------------
class TestDashboards:
    def test_cfo_cockpit(self, cfo_headers):
        r = requests.get(f"{API}/dashboard/cfo", headers=cfo_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        for k in ("kpis", "heatmap", "top_risks", "trends", "top_failing_controls"):
            assert k in data, f"missing {k}"
        # Heatmap is entity × process; Phase 2 may add processes, so avoid hardcoding.
        assert len(data["heatmap"]) >= 20, f"expected at least baseline heatmap cells, got {len(data['heatmap'])}"
        assert len(data["top_risks"]) <= 10
        assert len(data["trends"]) == 8

    def test_controller(self, cfo_headers):
        r = requests.get(f"{API}/dashboard/controller", headers=cfo_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "kpis" in data
        assert "reconciliations" in data
        assert "ap_exceptions" in data

    def test_audit(self, cfo_headers):
        r = requests.get(f"{API}/dashboard/audit", headers=cfo_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "controls" in data and len(data["controls"]) >= 12
        assert "recent_runs" in data
        assert "summary" in data and "trends" in data
        assert "audit_readiness_pct" in data["summary"]

    def test_audit_scoped_entity(self, cfo_headers):
        """Phase 6–7 — dashboard/audit echoes master filters; recent_runs respect entity via ``entities``."""
        r = requests.get(
            f"{API}/dashboard/audit",
            params={"entity_code": "US-HQ"},
            headers=cfo_headers,
            timeout=30,
        )
        assert r.status_code == 200
        data = r.json()
        assert data.get("filters_applied", {}).get("entity_code") == "US-HQ"
        assert "controls" in data and "recent_runs" in data
        assert isinstance(data["recent_runs"], list)
        ec = data["filters_applied"].get("entity_code")
        for row in data["recent_runs"]:
            assert ec in (row.get("entities") or []), row

    def test_compliance(self, cfo_headers):
        r = requests.get(f"{API}/dashboard/compliance", headers=cfo_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        for k in ("kpis", "sod_conflicts", "access_violations", "exception_aging"):
            assert k in data

    def test_my_cases(self, owner_headers):
        r = requests.get(f"{API}/dashboard/my-cases", headers=owner_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "kpis" in data and "cases" in data
        for c in data["cases"]:
            assert c["owner_email"] == "owner@onetouch.ai"

    def test_readiness(self, cfo_headers):
        r = requests.get(f"{API}/readiness", headers=cfo_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        assert isinstance(data.get("filters_applied"), dict)
        assert isinstance(data.get("rows"), list)
        assert len(data["rows"]) > 0


# --------------- Controls ---------------
EXPECTED_CONTROLS = {
    "C-AP-001", "C-AP-002", "C-AP-003", "C-AP-004", "C-AP-005",
    "C-GL-001", "C-GL-002", "C-GL-003",
    "C-ACC-001", "C-ACC-002",
    "C-TR-001", "C-TX-001",
}


class TestControls:
    def test_list_controls(self, cfo_headers):
        r = requests.get(f"{API}/controls", headers=cfo_headers, timeout=30)
        assert r.status_code == 200
        controls = r.json()
        codes = {c["code"] for c in controls}
        assert EXPECTED_CONTROLS.issubset(codes), f"missing: {EXPECTED_CONTROLS - codes}"

    def test_run_single_control(self, cfo_headers):
        controls = requests.get(f"{API}/controls", headers=cfo_headers, timeout=30).json()
        cid = controls[0]["id"]
        r = requests.post(f"{API}/controls/{cid}/run", headers=cfo_headers, timeout=60)
        assert r.status_code == 200
        data = r.json()
        assert "run_id" in data
        assert "exceptions" in data
        assert data.get("status") == "success"

    def test_run_tags_test_run_with_entities(self, cfo_headers):
        """Phase 7 — test_runs.entities lists distinct exception entities for dashboard scoping."""
        controls = requests.get(f"{API}/controls", headers=cfo_headers, timeout=30).json()
        cid = controls[0]["id"]
        requests.post(f"{API}/controls/{cid}/run", headers=cfo_headers, timeout=60)
        dash = requests.get(f"{API}/dashboard/audit", headers=cfo_headers, timeout=30).json()
        assert dash.get("recent_runs"), "expected at least one test run"
        top = dash["recent_runs"][0]
        assert "entities" in top
        assert isinstance(top["entities"], list)

    def test_run_all(self, cfo_headers):
        r = requests.post(f"{API}/controls/run-all", headers=cfo_headers, timeout=120)
        assert r.status_code == 200
        data = r.json()
        assert data.get("total_exceptions", 0) > 0

    def test_control_detail_scoped_entity(self, cfo_headers):
        """Phase 6 — open_exceptions respect entity_code; response includes filters_applied."""
        controls = requests.get(f"{API}/controls", headers=cfo_headers, timeout=30).json()
        cid = controls[0]["id"]
        r = requests.get(
            f"{API}/controls/{cid}",
            params={"entity_code": "IN-SVC"},
            headers=cfo_headers,
            timeout=30,
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("filters_applied", {}).get("entity_code") == "IN-SVC"
        for ex in body.get("open_exceptions", []):
            assert ex.get("entity") == "IN-SVC"


# --------------- Exceptions + Cases ---------------
class TestExceptionsAndCases:
    def test_list_exceptions(self, cfo_headers):
        r = requests.get(f"{API}/exceptions?limit=500", headers=cfo_headers, timeout=30)
        assert r.status_code == 200
        lst = r.json()
        assert len(lst) > 100, f"expected many exceptions, got {len(lst)}"

    def test_filter_exceptions(self, cfo_headers):
        r = requests.get(f"{API}/exceptions?severity=high&limit=50",
                         headers=cfo_headers, timeout=30)
        assert r.status_code == 200
        for e in r.json():
            assert e["severity"] == "high"

    def test_exceptions_pagination(self, cfo_headers):
        r1 = requests.get(
            f"{API}/exceptions",
            params={"limit": 3, "offset": 0},
            headers=cfo_headers,
            timeout=30,
        )
        r2 = requests.get(
            f"{API}/exceptions",
            params={"limit": 3, "offset": 3},
            headers=cfo_headers,
            timeout=30,
        )
        assert r1.status_code == 200 and r2.status_code == 200
        a, b = r1.json(), r2.json()
        assert isinstance(a, list) and isinstance(b, list)
        assert len(a) <= 3 and len(b) <= 3
        ids1 = {x["id"] for x in a}
        ids2 = {x["id"] for x in b}
        assert ids1.isdisjoint(ids2)

    def test_exceptions_count(self, cfo_headers):
        rc = requests.get(f"{API}/exceptions/count", headers=cfo_headers, timeout=30)
        assert rc.status_code == 200
        n = rc.json().get("count")
        assert isinstance(n, int) and n > 100
        rl = requests.get(f"{API}/exceptions", params={"limit": 500}, headers=cfo_headers, timeout=30)
        assert rl.status_code == 200
        assert len(rl.json()) <= n

    def test_exception_detail(self, cfo_headers):
        lst = requests.get(f"{API}/exceptions?limit=5", headers=cfo_headers, timeout=30).json()
        eid = lst[0]["id"]
        r = requests.get(f"{API}/exceptions/{eid}", headers=cfo_headers, timeout=30)
        assert r.status_code == 200
        assert r.json()["exception"]["id"] == eid

    def test_promote_exception_to_case(self, cfo_headers):
        # find an exception without a case
        lst = requests.get(f"{API}/exceptions?status=open&limit=100",
                           headers=cfo_headers, timeout=30).json()
        assert lst, "no open exceptions"
        eid = None
        for e in lst:
            det = requests.get(f"{API}/exceptions/{e['id']}", headers=cfo_headers, timeout=30).json()
            if not det.get("case"):
                eid = e["id"]
                break
        assert eid, "could not find open exception without a case"
        r = requests.post(f"{API}/cases/from-exception?exception_id={eid}",
                          headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text
        case = r.json()
        assert case["exception_id"] == eid
        assert case["status"] == "open"
        # idempotent
        r2 = requests.post(f"{API}/cases/from-exception?exception_id={eid}",
                           headers=cfo_headers, timeout=30)
        assert r2.status_code == 200
        assert r2.json()["id"] == case["id"]

    def test_case_update_and_comment(self, cfo_headers):
        # pick first open case (seed may include closed/WORM-locked cases first)
        cases = requests.get(f"{API}/cases?limit=50&status=open", headers=cfo_headers, timeout=30).json()
        assert cases, "need at least one open case"
        cid = cases[0]["id"]
        # comment
        r = requests.post(f"{API}/cases/{cid}/comments",
                         headers=cfo_headers, json={"comment": "TEST_comment_auto"}, timeout=30)
        assert r.status_code == 200
        assert r.json()["comment"] == "TEST_comment_auto"
        # update status to closed
        r = requests.patch(f"{API}/cases/{cid}", headers=cfo_headers,
                          json={"status": "closed"}, timeout=30)
        assert r.status_code == 200
        assert r.json()["status"] == "closed"
        assert r.json().get("closed_at") is not None
        # verify detail returns comments + history
        det = requests.get(f"{API}/cases/{cid}", headers=cfo_headers, timeout=30).json()
        assert any(c["comment"] == "TEST_comment_auto" for c in det["comments"])
        assert det["case"]["status"] == "closed"
        # exception was also closed
        assert det["exception"]["status"] == "closed"


# --------------- Evidence ---------------
class TestEvidence:
    def test_evidence_graph(self, cfo_headers):
        lst = requests.get(f"{API}/exceptions?limit=3", headers=cfo_headers, timeout=30).json()
        eid = lst[0]["id"]
        r = requests.get(f"{API}/evidence/{eid}", headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text
        g = r.json()
        assert "nodes" in g and "edges" in g
        assert len(g["nodes"]) >= 1
        types = {n.get("type") for n in g["nodes"]}
        # at least control + exception nodes
        assert {"control", "exception"}.issubset(types)


# --------------- Copilot ---------------
class TestCopilot:
    def test_copilot_ask(self, cfo_headers):
        r = requests.post(f"{API}/copilot/ask", headers=cfo_headers,
                          json={"question": "What are the top duplicate payment exposures?"},
                          timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("answer", "citations", "confidence", "model", "needs_human_review"):
            assert k in data, f"missing {k}: got {list(data.keys())}"
        assert isinstance(data["answer"], str) and len(data["answer"]) > 10
        assert isinstance(data["citations"], list)

    def test_copilot_sessions(self, cfo_headers):
        r = requests.get(f"{API}/copilot/sessions", headers=cfo_headers, timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# --------------- Admin ---------------
class TestAdmin:
    def test_models(self, cfo_headers):
        r = requests.get(f"{API}/admin/models", headers=cfo_headers, timeout=30)
        assert r.status_code == 200 and isinstance(r.json(), list)

    def test_prompts(self, cfo_headers):
        r = requests.get(f"{API}/admin/prompts", headers=cfo_headers, timeout=30)
        assert r.status_code == 200 and isinstance(r.json(), list)

    def test_audit_logs(self, cfo_headers):
        r = requests.get(f"{API}/admin/audit-logs", headers=cfo_headers, timeout=30)
        assert r.status_code == 200 and isinstance(r.json(), list)

    def test_audit_logs_query(self, cfo_headers):
        r = requests.get(f"{API}/admin/audit-logs/query", params={"limit": 5}, headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, dict)
        assert "items" in data and "total" in data
        assert isinstance(data["items"], list)

    def test_audit_logs_query_prefix(self, cfo_headers):
        # Phase 29: prefix filters should be accepted (may return 0 items depending on dataset)
        r = requests.get(
            f"{API}/admin/audit-logs/query",
            params={"limit": 5, "action_type": "export_"},
            headers=cfo_headers,
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, dict)
        assert "items" in data

    def test_audit_logs_export_csv(self, cfo_headers):
        r = requests.get(f"{API}/admin/audit-logs/export.csv", params={"limit": 5}, headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text[:500]
        assert "text/csv" in (r.headers.get("content-type", "") or "")
        body = r.text
        assert "event_ts,actor_user_email,action_type,object_type,object_id,detail_json" in body.splitlines()[0]

    def test_audit_logs_export_json(self, cfo_headers):
        r = requests.get(f"{API}/admin/audit-logs/export.json", params={"limit": 5}, headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text[:500]
        ct = r.headers.get("content-type", "") or ""
        assert "application/json" in ct
        data = r.json()
        assert isinstance(data, dict)
        for k in (
            "exported_at",
            "filters_applied",
            "total_matched",
            "paging",
            "offset",
            "limit",
            "returned",
            "truncated",
            "next_cursor",
            "items",
        ):
            assert k in data
        assert data["offset"] == 0
        assert data["paging"] == "offset"
        assert data["next_cursor"] is None or isinstance(data["next_cursor"], dict)
        assert isinstance(data["items"], list)

    def test_audit_logs_export_ndjson(self, cfo_headers):
        r = requests.get(f"{API}/admin/audit-logs/export.ndjson", params={"limit": 5}, headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text[:500]
        ct = r.headers.get("content-type", "") or ""
        assert "ndjson" in ct
        assert r.headers.get("X-Audit-Export-Total-Matched") is not None
        raw = (r.text or "").strip()
        if raw:
            for line in raw.splitlines():
                obj = json.loads(line)
                assert isinstance(obj, dict)

    def test_audit_logs_export_json_gzip(self, cfo_headers):
        r = requests.get(
            f"{API}/admin/audit-logs/export.json",
            params={"limit": 5, "gzip": True},
            headers=cfo_headers,
            timeout=30,
        )
        assert r.status_code == 200, r.text[:200]
        assert "gzip" in (r.headers.get("content-type") or "").lower()
        dec = gzip.decompress(r.content)
        data = json.loads(dec.decode("utf-8"))
        assert "items" in data and isinstance(data["items"], list)

    def test_audit_logs_export_csv_gzip(self, cfo_headers):
        r = requests.get(
            f"{API}/admin/audit-logs/export.csv",
            params={"limit": 5, "gzip": True},
            headers=cfo_headers,
            timeout=30,
        )
        assert r.status_code == 200
        txt = gzip.decompress(r.content).decode("utf-8")
        assert txt.splitlines()[0].startswith("event_ts,")

    def test_audit_logs_export_ndjson_gzip(self, cfo_headers):
        r = requests.get(
            f"{API}/admin/audit-logs/export.ndjson",
            params={"limit": 5, "gzip": True},
            headers=cfo_headers,
            timeout=30,
        )
        assert r.status_code == 200
        raw = gzip.decompress(r.content).decode("utf-8").strip()
        if raw:
            for line in raw.splitlines():
                assert isinstance(json.loads(line), dict)

    def test_audit_logs_export_after_id_requires_after_ts(self, cfo_headers):
        r = requests.get(
            f"{API}/admin/audit-logs/export.json",
            params={"limit": 3, "after_id": "not-without-ts"},
            headers=cfo_headers,
            timeout=30,
        )
        assert r.status_code == 400

    def test_audit_logs_export_json_keyset(self, cfo_headers):
        r = requests.get(
            f"{API}/admin/audit-logs/export.json",
            params={"limit": 2, "after_ts": "2999-12-31T23:59:59Z"},
            headers=cfo_headers,
            timeout=30,
        )
        assert r.status_code == 200
        d = r.json()
        assert d["paging"] == "keyset"
        assert isinstance(d["items"], list)

    def test_audit_logs_export_json_paging(self, cfo_headers):
        r0 = requests.get(
            f"{API}/admin/audit-logs/export.json",
            params={"limit": 2, "offset": 0},
            headers=cfo_headers,
            timeout=30,
        )
        assert r0.status_code == 200
        d0 = r0.json()
        assert d0["offset"] == 0 and isinstance(d0["items"], list)

        r1 = requests.get(
            f"{API}/admin/audit-logs/export.json",
            params={"limit": 2, "offset": 2},
            headers=cfo_headers,
            timeout=30,
        )
        assert r1.status_code == 200
        d1 = r1.json()
        assert d1["offset"] == 2

    def test_audit_logs_export_digest_sha256(self, cfo_headers):
        r = requests.get(
            f"{API}/admin/audit-logs/export.json",
            params={"limit": 3, "digest": True},
            headers=cfo_headers,
            timeout=30,
        )
        assert r.status_code == 200
        hdr = r.headers.get("X-Audit-Export-Sha256")
        assert hdr and len(hdr) == 64
        assert hashlib.sha256(r.content).hexdigest() == hdr

        r2 = requests.get(
            f"{API}/admin/audit-logs/export.ndjson",
            params={"limit": 4, "digest": True},
            headers=cfo_headers,
            timeout=30,
        )
        assert r2.status_code == 200
        h2 = r2.headers.get("X-Audit-Export-Sha256")
        assert h2 and hashlib.sha256(r2.content).hexdigest() == h2

    def test_audit_log_detail(self, cfo_headers):
        lst = requests.get(f"{API}/admin/audit-logs", params={"limit": 1}, headers=cfo_headers, timeout=30).json()
        if not lst:
            pytest.skip("no audit logs in dataset")
        log_id = lst[0]["id"]
        r = requests.get(f"{API}/admin/audit-logs/{log_id}", headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("id") == log_id

    def test_summary(self, cfo_headers):
        r = requests.get(f"{API}/admin/summary", headers=cfo_headers, timeout=30)
        assert r.status_code == 200
        assert "collections" in r.json()

    def test_ingestion_runs(self, cfo_headers):
        r = requests.get(f"{API}/admin/ingestion-runs", headers=cfo_headers, timeout=30)
        assert r.status_code == 200

    def test_seed_reset_forbidden_for_owner(self, owner_headers):
        r = requests.post(f"{API}/admin/seed-reset", headers=owner_headers, timeout=60)
        assert r.status_code == 403

    def test_audit_logs_forbidden_for_owner(self, owner_headers):
        r = requests.get(f"{API}/admin/audit-logs", headers=owner_headers, timeout=30)
        assert r.status_code == 403
        assert requests.get(f"{API}/admin/audit-logs/export.json", headers=owner_headers, timeout=30).status_code == 403
        assert requests.get(f"{API}/admin/audit-logs/export.ndjson", headers=owner_headers, timeout=30).status_code == 403


# --------------- Masters (Phase 2 unified finance model) ---------------
class TestMasters:
    @staticmethod
    def _assert_master_list(data):
        assert "items" in data and "count" in data and "as_of" in data
        assert isinstance(data["items"], list)
        assert data["count"] == len(data["items"])

    def test_entities(self, cfo_headers):
        r = requests.get(f"{API}/masters/entities", headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text
        self._assert_master_list(r.json())

    def test_companies(self, cfo_headers):
        r = requests.get(f"{API}/masters/companies", headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text
        self._assert_master_list(r.json())

    def test_departments_scoped(self, cfo_headers):
        r = requests.get(
            f"{API}/masters/departments",
            headers=cfo_headers,
            params={"entity_code": "US-HQ"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        self._assert_master_list(r.json())

    def test_cost_centers_scoped(self, cfo_headers):
        r = requests.get(
            f"{API}/masters/cost-centers",
            headers=cfo_headers,
            params={"entity_code": "US-HQ"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        self._assert_master_list(r.json())

    def test_entity_hierarchy(self, cfo_headers):
        r = requests.get(f"{API}/masters/entity-hierarchy", headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "items" in data and isinstance(data["items"], list)

    def test_risk_scores(self, cfo_headers):
        r = requests.get(f"{API}/masters/risk-scores", params={"limit": 50}, headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "items" in data and isinstance(data["items"], list)
        assert "count" in data and "as_of" in data


# --------------- Dashboard scope (Phase 4) ---------------
class TestDashboardScope:
    def test_controller_scoped_entity(self, cfo_headers):
        r = requests.get(f"{API}/dashboard/controller", params={"entity_code": "US-HQ"}, headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("filters_applied", {}).get("entity_code") == "US-HQ"
        for row in data.get("reconciliations", []):
            assert row.get("entity") == "US-HQ"
        for ex in data.get("ap_exceptions", []):
            assert ex.get("entity") == "US-HQ"

    def test_cfo_scoped_entity(self, cfo_headers):
        r = requests.get(f"{API}/dashboard/cfo", params={"entity_code": "UK-OPS"}, headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("filters_applied", {}).get("entity_code") == "UK-OPS"
        for row in data.get("heatmap", []):
            assert row.get("entity") == "UK-OPS"


# --------------- Phase 10 — exception org enrichment at control run ---------------
class TestPhase10ExceptionOrgEnrichment:
    def test_exceptions_have_org_fields_after_control_run(self, cfo_headers):
        """When finance masters exist, control runs attach department_id / cost_center_id to new exceptions."""
        controls = requests.get(f"{API}/controls", headers=cfo_headers, timeout=30).json()
        c0 = controls[0]
        requests.post(f"{API}/controls/{c0['id']}/run", headers=cfo_headers, timeout=60)
        lst = requests.get(
            f"{API}/exceptions",
            params={"control_code": c0["code"], "limit": 80},
            headers=cfo_headers,
            timeout=30,
        ).json()
        if not lst:
            pytest.skip("control produced no exceptions in this dataset")
        with_dept = sum(1 for x in lst if x.get("department_id"))
        with_cc = sum(1 for x in lst if x.get("cost_center_id"))
        assert with_dept > 0 or with_cc > 0, "expected Phase 10 org enrichment when master_departments / cost_centers are seeded"


# --------------- Phase 38 — risk intelligence dashboard (CFO slice + risk scores) ---------------
class TestPhase38RiskIntelligenceDashboard:
    def test_risk_intelligence_ok(self, cfo_headers):
        r = requests.get(f"{API}/dashboard/risk-intelligence", headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "kpis" in d and "heatmap" in d and "filters_applied" in d
        assert "risk_scores" in d
        rs = d["risk_scores"]
        assert "items" in rs and "count" in rs and "as_of" in rs
        assert rs["count"] == len(rs["items"])

    def test_risk_intelligence_entity_scope_matches_cfo(self, cfo_headers):
        r = requests.get(f"{API}/dashboard/risk-intelligence", params={"entity_code": "UK-OPS"}, headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("filters_applied", {}).get("entity_code") == "UK-OPS"
        for row in d.get("heatmap", []):
            assert row.get("entity") == "UK-OPS"
        for item in d.get("risk_scores", {}).get("items", []):
            assert item.get("entity_code") == "UK-OPS"
        r_cfo = requests.get(f"{API}/dashboard/cfo", params={"entity_code": "UK-OPS"}, headers=cfo_headers, timeout=30)
        assert r_cfo.status_code == 200, r_cfo.text
        assert d["kpis"] == r_cfo.json()["kpis"]


# --------------- Phase 3 / Slice 2 — KPI endpoints ---------------
class TestPhase3KpiEndpoints:
    def test_kpi_definitions(self, cfo_headers):
        r = requests.get(f"{API}/kpi/definitions", headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "items" in d and "count" in d
        assert d["count"] == len(d["items"])
        assert any(x.get("id") == "audit_readiness_pct" for x in d["items"])

    def test_kpi_cfo_summary_scoped(self, cfo_headers):
        r = requests.get(f"{API}/kpi/cfo-summary", params={"entity_code": "UK-OPS"}, headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("filters_applied", {}).get("entity_code") == "UK-OPS"
        kpis = d.get("kpis") or []
        assert isinstance(kpis, list) and len(kpis) >= 3
        ids = {x.get("id") for x in kpis}
        assert "audit_readiness_pct" in ids

    def test_kpi_trend_readiness(self, cfo_headers):
        r = requests.get(f"{API}/kpi/trend/audit_readiness_pct", headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("kpi_id") == "audit_readiness_pct"
        assert isinstance(d.get("series"), list)

    def test_kpi_drilldown_has_refs(self, cfo_headers):
        r = requests.get(f"{API}/kpi/drilldown/unresolved_high_risk_exposure", headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("kpi_id") == "unresolved_high_risk_exposure"
        assert isinstance(d.get("refs"), list)

    def test_kpi_audit_readiness_drill_detail(self, cfo_headers):
        r = requests.get(f"{API}/kpi/drilldown/audit_readiness_pct", headers=cfo_headers, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("kpi_id") == "audit_readiness_pct"
        detail = d.get("detail") or {}
        summary = detail.get("summary") or {}
        assert summary.get("current") is not None
        assert isinstance(detail.get("heatmap"), list)
        assert isinstance(detail.get("distribution"), list)
        assert isinstance(detail.get("correlated_kpis"), list)

    def test_kpi_audit_readiness_trend_multi(self, cfo_headers):
        r = requests.get(f"{API}/kpi/trend/audit_readiness_pct", headers=cfo_headers, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("kpi_id") == "audit_readiness_pct"
        assert "trend_source" in d
        assert isinstance(d.get("series"), list)

    def test_kpi_audit_readiness_export_csv(self, cfo_headers):
        r = requests.get(
            f"{API}/kpi/drilldown/audit_readiness_pct/export",
            headers=cfo_headers,
            timeout=60,
        )
        assert r.status_code == 200, r.text
        assert "text/csv" in (r.headers.get("content-type") or "")
        assert b"Audit readiness export" in r.content


# --------------- Slice 3 — CFO action queue ---------------
class TestSlice3CfoActionQueue:
    def test_action_queue_list_refresh(self, cfo_headers):
        r = requests.get(f"{API}/cfo/action-queue", params={"refresh": True, "limit": 5}, headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "items" in d and "total" in d
        assert isinstance(d["items"], list)

    def test_action_queue_detail_and_comment(self, cfo_headers):
        r = requests.get(f"{API}/cfo/action-queue", params={"refresh": True, "limit": 1}, headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text
        items = (r.json() or {}).get("items") or []
        if not items:
            pytest.skip("no action queue items in dataset")
        aid = items[0]["id"]
        r2 = requests.get(f"{API}/cfo/action-queue/{aid}", headers=cfo_headers, timeout=30)
        assert r2.status_code == 200, r2.text
        r3 = requests.post(f"{API}/cfo/action/{aid}/comment", json={"comment": "QA note"}, headers=cfo_headers, timeout=30)
        assert r3.status_code == 200, r3.text
        assert any(c.get("text") == "QA note" for c in (r3.json().get("comments") or []))


# --------------- Slice 4 — month-end close ---------------
class TestSlice4MonthEndClose:
    def test_close_cycle_create_and_get(self, cfo_headers):
        r = requests.post(
            f"{API}/close/cycles",
            json={"period_ym": "2026-05", "name": "Month-end close 2026-05"},
            headers=cfo_headers,
            timeout=30,
        )
        assert r.status_code == 200, r.text
        cyc = r.json()
        assert cyc.get("period_ym") == "2026-05"
        cid = cyc.get("id")
        r2 = requests.get(f"{API}/close/cycles/{cid}", headers=cfo_headers, timeout=30)
        assert r2.status_code == 200, r2.text
        d = r2.json()
        assert d.get("id") == cid
        assert isinstance(d.get("tasks"), list)
        assert len(d["tasks"]) > 0

    def test_close_task_submit_approve_and_signoff_gate(self, cfo_headers):
        r = requests.post(
            f"{API}/close/cycles",
            json={"period_ym": "2026-06", "name": "Month-end close 2026-06"},
            headers=cfo_headers,
            timeout=30,
        )
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
        cyc = requests.get(f"{API}/close/cycles/{cid}", headers=cfo_headers, timeout=30).json()
        critical = next((t for t in cyc.get("tasks", []) if t.get("critical")), None)
        if not critical:
            pytest.skip("no critical close tasks in templates")
        tid = critical["id"]
        assert requests.post(f"{API}/close/tasks/{tid}/submit", headers=cfo_headers, timeout=30).status_code == 200
        assert requests.post(f"{API}/close/tasks/{tid}/approve", headers=cfo_headers, timeout=30).status_code == 200
        # Should still block if other critical tasks incomplete
        r3 = requests.post(f"{API}/close/signoff", json={"cycle_id": cid}, headers=cfo_headers, timeout=30)
        assert r3.status_code in (200, 409), r3.text


# --------------- Slice 5 — working capital ---------------
class TestSlice5WorkingCapital:
    def test_working_capital_dashboard(self, cfo_headers):
        r = requests.get(f"{API}/dashboard/working-capital", headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "kpis" in d
        assert "ar_aging" in d and isinstance(d["ar_aging"], list)
        assert "ap_aging" in d and isinstance(d["ap_aging"], list)


# --------------- Slice 6 — treasury ---------------
class TestSlice6Treasury:
    def test_treasury_dashboard(self, cfo_headers):
        r = requests.get(f"{API}/dashboard/treasury", headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "kpis" in d
        assert "bank_accounts" in d and isinstance(d["bank_accounts"], list)
        assert "recent_bank_transactions" in d and isinstance(d["recent_bank_transactions"], list)


# --------------- Slice 7 — FP&A snapshot ---------------
class TestSlice7Fpa:
    def test_fpa_dashboard(self, cfo_headers):
        r = requests.get(f"{API}/dashboard/fpa", headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "kpis" in d
        assert "capex_projects" in d and isinstance(d["capex_projects"], list)
        assert "recent_journals" in d and isinstance(d["recent_journals"], list)


# --------------- Slice 8 — cash conversion cycle ---------------
class TestSlice8CashConversion:
    def test_cash_conversion_dashboard(self, cfo_headers):
        r = requests.get(f"{API}/dashboard/cash-conversion", headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "kpis" in d
        assert "window_days" in d
        assert "note" in d


# --------------- Slice 9 — department/cost-center scoping ---------------
class TestSlice9OrgScoping:
    def test_working_capital_scoped_by_department(self, cfo_headers):
        depts = requests.get(f"{API}/masters/departments?entity_code=US-HQ", headers=cfo_headers, timeout=30).json().get("items") or []
        assert depts, "No departments seeded"
        did = depts[0]["id"]
        r = requests.get(f"{API}/dashboard/working-capital", headers=cfo_headers, params={"entity_code": "US-HQ", "department_id": did}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("filters_applied", {}).get("department_id") == did
        # Backfill assigns department_id to docs; ensure returned rows carry it when present
        top = d.get("top_overdue_ar") or []
        if top:
            assert all(x.get("department_id") == did for x in top if x.get("department_id") is not None)


# --------------- Slice 10 — org backfill control plane ---------------
class TestSlice10OrgBackfillControlPlane:
    def test_org_backfill_status_and_run(self, superadmin_headers):
        r0 = requests.get(f"{API}/system/org-backfill/status", headers=superadmin_headers, timeout=30)
        assert r0.status_code == 200, r0.text
        r = requests.post(
            f"{API}/system/org-backfill/run",
            json={"targets": ["transactions", "exceptions", "cases"], "limit": 500},
            headers=superadmin_headers,
            timeout=60,
        )
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc.get("id") == "latest"
        assert doc.get("last_run_by") == "superadmin@onetouch.ai"
        assert "last_result" in doc and isinstance(doc["last_result"], dict)


# --------------- Phase 40 — external auditor can load risk dashboard (nav parity with insights/risk) ---------------
class TestPhase40ExternalRiskDashboard:
    def test_external_auditor_risk_intelligence_dashboard(self, external_auditor_headers):
        r = requests.get(f"{API}/dashboard/risk-intelligence", headers=external_auditor_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "risk_scores" in d and "kpis" in d


# --------------- Phase 13 — audit committee pack exports respect reporting scope ---------------
class TestPhase13AuditCommitteeExports:
    def test_pdf_with_entity_scope(self, cfo_headers):
        r = requests.get(
            f"{API}/reports/audit-committee-pack.pdf",
            params={"entity_code": "IN-SVC"},
            headers=cfo_headers,
            timeout=120,
        )
        assert r.status_code == 200, r.text[:500]
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"

    def test_xlsx_with_entity_scope(self, cfo_headers):
        r = requests.get(
            f"{API}/reports/audit-committee-pack.xlsx",
            params={"entity_code": "IN-SVC"},
            headers=cfo_headers,
            timeout=120,
        )
        assert r.status_code == 200, r.text[:500]
        ct = r.headers.get("content-type", "")
        assert "spreadsheet" in ct or "xlsx" in ct or "openxmlformats" in ct
        assert r.content[:2] == b"PK"


# --------------- Phase 14 — auditor pack + open cases align with reporting context ---------------
class TestPhase14AuditorPackReportingContext:
    def test_pack_filters_applied_and_alignment_with_cfo(self, cfo_headers):
        """CFO may call /auditor/pack (same allowlist as Internal Auditor)."""
        r = requests.get(f"{API}/auditor/pack", params={"entity_code": "IN-SVC"}, headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text
        pack = r.json()
        assert isinstance(pack.get("filters_applied"), dict)
        assert pack["filters_applied"].get("entity_code") == "IN-SVC"
        r_cfo = requests.get(f"{API}/dashboard/cfo", params={"entity_code": "IN-SVC"}, headers=cfo_headers, timeout=30)
        assert r_cfo.status_code == 200, r_cfo.text
        cfo = r_cfo.json()
        assert pack["kpis"]["audit_readiness_pct"] == cfo["kpis"]["audit_readiness_pct"]
        assert len(pack["heatmap"]) == len(cfo["heatmap"])
        for row in pack["heatmap"]:
            assert row.get("entity") == "IN-SVC"
        for oc in pack["open_cases"]:
            assert oc.get("entity") == "IN-SVC"


# --------------- Phase 9 — cases denormalized org slice (dept / CC) ---------------
class TestPhase9CasesOrg:
    def test_cases_list_department_no_match_empty(self, cfo_headers):
        r = requests.get(
            f"{API}/cases",
            params={"department_id": "__phase9_no_match__", "limit": 20},
            headers=cfo_headers,
            timeout=30,
        )
        assert r.status_code == 200
        assert r.json() == []

    def test_my_cases_dashboard_department_filter_echo(self, owner_headers):
        r = requests.get(
            f"{API}/dashboard/my-cases",
            params={"department_id": "__phase9_no_match__"},
            headers=owner_headers,
            timeout=30,
        )
        assert r.status_code == 200
        d = r.json()
        assert d.get("filters_applied", {}).get("department_id") == "__phase9_no_match__"
        assert d["kpis"]["total_assigned"] == 0


# --------------- Phase 5 — compliance, readiness, cases scope ---------------
class TestPhase5Scope:
    def test_compliance_scoped_entity(self, cfo_headers):
        r = requests.get(f"{API}/dashboard/compliance", params={"entity_code": "US-HQ"}, headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("filters_applied", {}).get("entity_code") == "US-HQ"
        for e in data.get("sod_conflicts", []):
            assert e.get("entity") == "US-HQ"
        for e in data.get("access_violations", []):
            assert e.get("entity") == "US-HQ"

    def test_readiness_scoped_entity(self, cfo_headers):
        r = requests.get(f"{API}/readiness", params={"entity_code": "IN-SVC"}, headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("filters_applied", {}).get("entity_code") == "IN-SVC"
        rows = data.get("rows") or []
        assert isinstance(rows, list)
        for row in rows:
            assert row.get("entity") == "IN-SVC"

    def test_cases_entity_param(self, cfo_headers):
        r = requests.get(f"{API}/cases", params={"entity_code": "US-HQ", "limit": 50}, headers=cfo_headers, timeout=30)
        assert r.status_code == 200, r.text
        for c in r.json():
            assert c.get("entity") == "US-HQ"


# --------------- Ingestion ---------------
class TestIngestion:
    def test_csv_invoices(self, cfo_headers):
        csv_body = (
            "invoice_number,vendor_id,vendor_name,entity,invoice_date,amount,tax_amount,"
            "expected_tax_amount,status\n"
            "TEST_INV_001,V-1000,TEST Vendor,US-HQ,2026-01-05,1500.0,270.0,270.0,posted\n"
            "TEST_INV_002,V-1000,TEST Vendor,US-HQ,2026-01-05,3000.0,540.0,540.0,posted\n"
        )
        files = {"file": ("invoices.csv", io.BytesIO(csv_body.encode()), "text/csv")}
        data = {"dataset": "invoices"}
        r = requests.post(f"{API}/ingest/csv", headers=cfo_headers,
                          files=files, data=data, timeout=30)
        assert r.status_code == 200, r.text
        res = r.json()
        assert res["dataset"] == "invoices"
        assert res["rows_ingested"] == 2
        assert "lineage_id" in res

    def test_csv_bad_dataset(self, cfo_headers):
        files = {"file": ("x.csv", io.BytesIO(b"a,b\n1,2\n"), "text/csv")}
        r = requests.post(f"{API}/ingest/csv", headers=cfo_headers,
                          files=files, data={"dataset": "bogus"}, timeout=30)
        assert r.status_code == 400
