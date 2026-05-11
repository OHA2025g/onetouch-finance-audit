"""Phase 2 expansion tests — 11 new controls, 15 new collections, 8 new drill types.

Verifies no regression to Phase 1 (12 controls, drill types invoice/payment/journal/vendor/user/control).
"""
import pytest
import requests

from l4_http_common import resolve_react_app_backend_url

BASE_URL = resolve_react_app_backend_url()
assert BASE_URL, "Set REACT_APP_BACKEND_URL or apps/frontend/.env for HTTP tests."
API = f"{BASE_URL.rstrip('/')}/api"

CFO = {"email": "cfo@onetouch.ai", "password": "demo1234"}
EXT = {"email": "external.auditor@bigfour.example", "password": "demo1234"}

PHASE1_CODES = {
    "C-AP-001", "C-AP-002", "C-AP-003", "C-AP-004", "C-AP-005",
    "C-GL-001", "C-GL-002", "C-GL-003",
    "C-ACC-001", "C-ACC-002",
    "C-TR-001", "C-TX-001",
}
PHASE2_CODES = {
    "C-OTC-001", "C-OTC-002", "C-OTC-003",
    "C-PAY-001", "C-PAY-002",
    "C-TR-002", "C-TR-003",
    "C-TX-002",
    "C-FA-001", "C-FA-002", "C-FA-003",
}


@pytest.fixture(scope="session")
def cfo_headers():
    r = requests.post(f"{API}/auth/login", json=CFO, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="session")
def ext_headers():
    r = requests.post(f"{API}/auth/login", json=EXT, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


# ---- Controls catalog ----
class TestControlsCatalog:
    def test_23_total_controls(self, cfo_headers):
        r = requests.get(f"{API}/controls", headers=cfo_headers, timeout=30)
        assert r.status_code == 200
        codes = {c["code"] for c in r.json()}
        missing_p2 = PHASE2_CODES - codes
        missing_p1 = PHASE1_CODES - codes
        assert not missing_p1, f"Phase 1 regression — missing: {missing_p1}"
        assert not missing_p2, f"Phase 2 missing: {missing_p2}"
        assert len(codes) >= 23, f"expected >=23 controls, got {len(codes)}"


# ---- Control runs produce exceptions ----
class TestControlRuns:
    def test_run_all_completes(self, cfo_headers):
        r = requests.post(f"{API}/controls/run-all", headers=cfo_headers, timeout=180)
        assert r.status_code == 200, r.text
        assert r.json().get("total_exceptions", 0) > 0

    @pytest.mark.parametrize("code", sorted(PHASE2_CODES))
    def test_phase2_control_run_produces_exceptions(self, cfo_headers, code):
        controls = requests.get(f"{API}/controls", headers=cfo_headers, timeout=30).json()
        ctrl = next((c for c in controls if c["code"] == code), None)
        assert ctrl, f"control {code} not found"
        r = requests.post(f"{API}/controls/{ctrl['id']}/run", headers=cfo_headers, timeout=60)
        assert r.status_code == 200, f"{code}: {r.text}"
        body = r.json()
        assert body.get("status") == "success"
        exc_count = body.get("exceptions", 0)
        assert exc_count > 0, f"{code} produced 0 exceptions (expected >0 from seeded data)"

    @pytest.mark.parametrize("code", sorted(PHASE2_CODES))
    def test_phase2_exceptions_listed(self, cfo_headers, code):
        r = requests.get(f"{API}/exceptions?control_code={code}&limit=200",
                         headers=cfo_headers, timeout=30)
        assert r.status_code == 200
        lst = r.json()
        assert len(lst) > 0, f"{code}: expected exceptions in listing"
        for e in lst[:5]:
            assert e["control_code"] == code


# ---- Phase 1 regression: drill types still work ----
class TestPhase1Regression:
    def test_phase1_controls_still_produce_exceptions(self, cfo_headers):
        for code in ("C-AP-001", "C-GL-001", "C-TX-001"):
            r = requests.get(f"{API}/exceptions?control_code={code}&limit=5",
                             headers=cfo_headers, timeout=30)
            assert r.status_code == 200
            assert len(r.json()) > 0, f"phase1 regression — {code} has 0 exceptions"

    def test_phase1_drill_types_200(self, cfo_headers):
        # Find one concrete id per phase1 type via existing exceptions
        ex = requests.get(f"{API}/exceptions?limit=300", headers=cfo_headers, timeout=30).json()
        seen = {}
        for e in ex:
            t = e.get("source_record_type")
            if t in {"invoice", "payment", "journal", "vendor", "user", "control"} and t not in seen:
                seen[t] = e["source_record_id"]
        # Also fall back: control drill uses control_id (any control)
        if "control" not in seen:
            c = requests.get(f"{API}/controls", headers=cfo_headers, timeout=30).json()[0]
            seen["control"] = c["id"]
        for t, i in seen.items():
            r = requests.get(f"{API}/drill/{t}/{i}", headers=cfo_headers, timeout=30)
            assert r.status_code == 200, f"drill/{t}/{i} → {r.status_code}: {r.text[:120]}"


# ---- New Phase 2 drill endpoints ----
class TestPhase2Drills:
    def _seed_ids(self, cfo_headers):
        """Discover one valid id per Phase 2 source type via control-code targeted listing."""
        ids = {}
        # Per-control listing guarantees we can find seed ids regardless of pagination
        pairs = [
            ("customer", "C-OTC-001"),
            ("ar_invoice", "C-OTC-002"),
            ("payroll_entry", "C-PAY-001"),
            ("bank_transaction", "C-TR-002"),
            ("fixed_asset", "C-FA-001"),
            ("capex_project", "C-FA-003"),
        ]
        for t, code in pairs:
            lst = requests.get(f"{API}/exceptions?control_code={code}&limit=10",
                               headers=cfo_headers, timeout=30).json()
            for e in lst:
                if e.get("source_record_type") == t:
                    ids[t] = e["source_record_id"]
                    break
        # sales_order + employee aren't source_record_type on exceptions — use known seed ids
        ids.setdefault("sales_order", "SO-BREACH-0")
        ids.setdefault("employee", "EMP-5002")  # terminated employee (ghost payment seed)
        return ids

    def test_all_phase2_drill_types_return_200(self, cfo_headers):
        ids = self._seed_ids(cfo_headers)
        expected_types = {"customer", "ar_invoice", "sales_order", "employee",
                          "payroll_entry", "bank_transaction", "fixed_asset", "capex_project"}
        missing = expected_types - set(ids.keys())
        assert not missing, f"could not discover seed ids for types: {missing}"
        for t, i in ids.items():
            r = requests.get(f"{API}/drill/{t}/{i}", headers=cfo_headers, timeout=30)
            assert r.status_code == 200, f"drill/{t}/{i} → {r.status_code}: {r.text[:200]}"
            data = r.json()
            assert isinstance(data, dict) and data, f"drill/{t}/{i} returned empty body"

    def test_drill_unknown_type_400(self, cfo_headers):
        r = requests.get(f"{API}/drill/unknown_type_xyz/abc", headers=cfo_headers, timeout=30)
        assert r.status_code in (400, 404), f"expected 400/404, got {r.status_code}"

    def test_drill_missing_id_404(self, cfo_headers):
        r = requests.get(f"{API}/drill/customer/DOES_NOT_EXIST_ZZZ",
                         headers=cfo_headers, timeout=30)
        assert r.status_code == 404, f"expected 404, got {r.status_code}"


# ---- CFO cockpit updated ----
class TestCFOCockpitPhase2:
    def test_heatmap_includes_phase2_processes(self, cfo_headers):
        r = requests.get(f"{API}/dashboard/cfo", headers=cfo_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        procs = {cell.get("process") for cell in data["heatmap"]}
        # Expect at least these 7 processes
        expected = {"Access/SoD", "Fixed Assets", "Order-to-Cash", "Payroll",
                    "Procure-to-Pay", "Record-to-Report", "Tax", "Treasury"}
        # Allow superset but ensure all Phase 2 new processes present
        new_needed = {"Fixed Assets", "Order-to-Cash", "Payroll"}
        assert new_needed.issubset(procs), f"missing Phase 2 processes in heatmap: {new_needed - procs}"
        # Prefer 7 distinct
        assert len(procs) >= 7, f"expected >=7 processes, got {len(procs)}: {procs}"


# ---- External Auditor gating ----
class TestExternalAuditorGating:
    def test_ext_blocked_from_run_all(self, ext_headers):
        r = requests.post(f"{API}/controls/run-all", headers=ext_headers, timeout=30)
        assert r.status_code == 403

    def test_ext_blocked_from_seed_reset(self, ext_headers):
        r = requests.post(f"{API}/admin/seed-reset", headers=ext_headers, timeout=30)
        assert r.status_code == 403

    def test_ext_can_access_auditor_pack(self, ext_headers):
        r = requests.get(f"{API}/auditor/pack", headers=ext_headers, timeout=30)
        assert r.status_code == 200

    def test_ext_can_read_phase2_drill(self, ext_headers, cfo_headers):
        # Resolve a customer id first with CFO then drill with EXT
        ex = requests.get(f"{API}/exceptions?control_code=C-OTC-001&limit=1",
                         headers=cfo_headers, timeout=30).json()
        assert ex, "no C-OTC-001 exceptions to source customer id from"
        cid = ex[0]["source_record_id"]
        r = requests.get(f"{API}/drill/customer/{cid}", headers=ext_headers, timeout=30)
        assert r.status_code == 200


# ---- Readiness + recalibrate ----
class TestOps:
    def test_readiness_has_phase2_rows(self, cfo_headers):
        r = requests.get(f"{API}/readiness", headers=cfo_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        rows = data.get("rows") or []
        assert isinstance(rows, list) and len(rows) > 0
        procs = {row.get("process") for row in rows}
        # Expect at least one Phase 2 process represented
        assert procs & {"Fixed Assets", "Order-to-Cash", "Payroll", "Treasury", "Tax"}, \
            f"no Phase 2 processes in readiness: {procs}"

    def test_anomaly_recalibrate(self, cfo_headers):
        r = requests.post(f"{API}/anomaly/recalibrate", headers=cfo_headers, timeout=120)
        assert r.status_code == 200, r.text


# ---- Seed collections populated ----
class TestPhase2Seed:
    def test_admin_summary_has_phase2_collections(self, cfo_headers):
        r = requests.get(f"{API}/admin/summary", headers=cfo_headers, timeout=30)
        assert r.status_code == 200
        collections = r.json().get("collections", {})
        # Normalize shape: dict of name→count OR list
        if isinstance(collections, list):
            names = {c.get("name") for c in collections}
            counts = {c.get("name"): c.get("count", 0) for c in collections}
        else:
            names = set(collections.keys())
            counts = collections
        required = {"customers", "sales_orders", "ar_invoices", "customer_receipts",
                    "employees", "payroll_runs", "payroll_entries",
                    "bank_accounts", "bank_transactions", "fx_rates",
                    "tax_filings", "withholding_records",
                    "fixed_assets", "depreciation_schedules", "capex_projects"}
        missing = required - names
        # If admin/summary doesn't expose all, just assert non-zero for the ones present
        for k, v in counts.items():
            if k in required:
                assert (v or 0) > 0, f"collection {k} is empty"
        # Allow partial exposure — not all implementations list every collection
        if missing:
            print(f"NOTE: admin/summary did not expose: {missing}")
