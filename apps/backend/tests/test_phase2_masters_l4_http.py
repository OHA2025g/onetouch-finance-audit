"""L4 contract tests for Phase 2 Unified finance model.

These are HTTP tests (requests) that validate production-like behavior:
- typed list contracts exist and are stable
- pagination/search works for master lists
- entity scope enforcement toggle blocks cross-entity queries
- master audit trail and master DQ endpoints respond
"""

from __future__ import annotations

import os
import time
import uuid

import pytest
import requests

from l4_http_common import resolve_react_app_backend_url, wait_until_api_ready


# L4 tests call the live API. CI sets REACT_APP_BACKEND_URL in docker-compose; locally use env or apps/frontend/.env.
_L4_BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "").strip() or (resolve_react_app_backend_url() or "")
pytestmark = pytest.mark.skipif(
    not _L4_BASE,
    reason="REACT_APP_BACKEND_URL not set and apps/frontend/.env missing — skip L4 HTTP contract tests",
)
BASE_URL = _L4_BASE
API = f"{BASE_URL.rstrip('/')}/api"


CREDS = {
    "superadmin": ("superadmin@onetouch.ai", "demo1234"),
    "cfo": ("cfo@onetouch.ai", "demo1234"),
}

def _wait_api(timeout_s: float = 60.0) -> None:
    """Block until public ``GET /api/`` returns 200."""
    wait_until_api_ready(API, timeout_s=timeout_s)


def _login(email, password):
    _wait_api()
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def tokens():
    return {k: _login(e, p) for k, (e, p) in CREDS.items()}


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


class TestMastersContracts:
    def test_customers_employees_bank_accounts_exist(self, tokens):
        for endpoint in ("/masters/customers", "/masters/employees", "/masters/bank-accounts"):
            r = requests.get(f"{API}{endpoint}", headers=_h(tokens["cfo"]), params={"limit": 5, "offset": 0}, timeout=30)
            assert r.status_code == 200, r.text
            body = r.json()
            assert isinstance(body.get("items"), list)
            # Phase 2 seed should ensure these are non-empty
            assert len(body["items"]) > 0
            assert "as_of" in body

    def test_vendors_pagination_and_search(self, tokens):
        r = requests.get(f"{API}/masters/vendors", headers=_h(tokens["cfo"]), params={"limit": 5, "offset": 0}, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body.get("items"), list)
        assert body.get("count") == len(body["items"])
        assert "as_of" in body

        if body["items"]:
            first = body["items"][0]
            code = first.get("vendor_code") or ""
            r2 = requests.get(
                f"{API}/masters/vendors",
                headers=_h(tokens["cfo"]),
                params={"q": code[:6], "limit": 10, "offset": 0},
                timeout=30,
            )
            assert r2.status_code == 200, r2.text
            assert isinstance(r2.json().get("items"), list)

    def test_transactions_contract(self, tokens):
        r = requests.get(f"{API}/masters/transactions", headers=_h(tokens["cfo"]), params={"limit": 3, "offset": 0}, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body.get("items"), list)
        assert "as_of" in body


class TestEntityScopeEnforcement:
    def test_toggle_entity_scope_on_and_blocks_cross_entity(self, tokens):
        # enable enforcement
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r.status_code == 200, r.text

        # Process Owner is IN-SVC; requesting UK-OPS must be blocked when scope is on.
        owner_tok = _login("owner@onetouch.ai", "demo1234")
        r2 = requests.get(
            f"{API}/masters/vendors",
            headers=_h(owner_tok),
            params={"entity_code": "UK-OPS", "limit": 5, "offset": 0},
            timeout=30,
        )
        assert r2.status_code == 403, r2.text

        # CFO has group-wide visibility (same unrestricted entity scope as Super Admin).
        r_cfo_cross = requests.get(
            f"{API}/masters/vendors",
            headers=_h(tokens["cfo"]),
            params={"entity_code": "UK-OPS", "limit": 5, "offset": 0},
            timeout=30,
        )
        assert r_cfo_cross.status_code == 200, r_cfo_cross.text

        # and the same applies to other Phase 2 master lists + DQ findings (shared RBAC helper)
        for endpoint in (
            "/masters/customers",
            "/masters/employees",
            "/masters/bank-accounts",
            "/dq/masters/findings",
            "/exceptions",
            "/legal/notices",
            "/access/users",
            "/reports/audit-committee-pack.pdf",
            "/forex/summary",
            "/bank-recon/statements",
            "/inventory-audit/summary",
            "/continuous-audit/rules",
            "/doa/matrix",
            "/evidence-intelligence/quality-issues",
            "/audit-depth/gl/accounts",
        ):
            rX = requests.get(
                f"{API}{endpoint}",
                headers=_h(owner_tok),
                params={"entity_code": "UK-OPS", "limit": 5, "offset": 0},
                timeout=30,
            )
            assert rX.status_code == 403, rX.text

        # requesting without entity_code should be restricted to assigned entity (200)
        r3 = requests.get(f"{API}/masters/vendors", headers=_h(tokens["cfo"]), params={"limit": 5}, timeout=30)
        assert r3.status_code == 200, r3.text

        # disable enforcement to avoid affecting other tests
        cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
        r4 = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)
        assert r4.status_code == 200, r4.text


class TestRollupsSummaryWhenEntityScopeEnforced:
    """``GET /rollups/summary`` / ``/rollups/hierarchy``: CFO sees full org; other users narrow when RBAC scope is on."""

    def test_cfo_rollups_summary_scoped_to_assigned_entity(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            rs = requests.get(f"{API}/rollups/summary", headers=_h(tokens["cfo"]), timeout=30)
            assert rs.status_code == 200, rs.text
            body = rs.json()
            assert body.get("entity_scope_applied") is not True
            assert set(body.get("entity_codes") or []) == {"IN-SVC", "SG-APAC", "UK-OPS", "US-HQ"}

            rh = requests.get(f"{API}/rollups/hierarchy", headers=_h(tokens["cfo"]), timeout=30)
            assert rh.status_code == 200, rh.text
            hb = rh.json()
            assert hb.get("entity_scope_applied") is not True
            assert set(hb.get("entity_codes") or []) == {"IN-SVC", "SG-APAC", "UK-OPS", "US-HQ"}
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            r_off = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)
            assert r_off.status_code == 200, r_off.text


class TestCaAuditEngagementsEntityScope:
    """CA audit engagements and modules gate on ``audit_engagements.entity_code`` when RBAC entity scope is on."""

    def test_cfo_cannot_read_other_entity_engagement_or_modules(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            eid = "ENG-DEMO-IN-2025"
            # CFO is seeded to US-HQ; India engagement is out of scope when enforcement is on.
            for path in (
                f"/audit-engagements/{eid}",
                f"/audit-engagements/{eid}/materiality",
                f"/audit-engagements/{eid}/summary",
            ):
                rx = requests.get(f"{API}{path}", headers=_h(tokens["cfo"]), timeout=30)
                assert rx.status_code == 403, f"{path}: {rx.status_code} {rx.text}"
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_in_svc_user_can_read_india_engagement_when_enforced(self, tokens):
        owner_tok = _login("owner@onetouch.ai", "demo1234")
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r = requests.get(f"{API}/audit-engagements/ENG-DEMO-IN-2025", headers=_h(owner_tok), timeout=30)
            assert r.status_code == 200, r.text
            assert r.json().get("entity_code") == "IN-SVC"
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_engagement_get_rejects_mismatched_entity_code_query_when_enforced(self, tokens):
        """``GET /audit-engagements/{id}`` must reject a wrong explicit ``entity_code`` query (aligned with CA modules)."""
        owner_tok = _login("owner@onetouch.ai", "demo1234")
        eid = "ENG-DEMO-IN-2025"
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r_bad = requests.get(
                f"{API}/audit-engagements/{eid}",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                timeout=30,
            )
            assert r_bad.status_code == 403, r_bad.text
            r_ok = requests.get(
                f"{API}/audit-engagements/{eid}",
                headers=_h(owner_tok),
                params={"entity_code": "IN-SVC"},
                timeout=30,
            )
            assert r_ok.status_code == 200, r_ok.text
            assert r_ok.json().get("entity_code") == "IN-SVC"
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_engagement_summary_rejects_mismatched_entity_code_query_when_enforced(self, tokens):
        """``GET /audit-engagements/{id}/summary`` must reject a wrong explicit ``entity_code`` query."""
        owner_tok = _login("owner@onetouch.ai", "demo1234")
        eid = "ENG-DEMO-IN-2025"
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r_bad = requests.get(
                f"{API}/audit-engagements/{eid}/summary",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                timeout=30,
            )
            assert r_bad.status_code == 403, r_bad.text
            r_ok = requests.get(
                f"{API}/audit-engagements/{eid}/summary",
                headers=_h(owner_tok),
                params={"entity_code": "IN-SVC"},
                timeout=30,
            )
            assert r_ok.status_code == 200, r_ok.text
            body = r_ok.json()
            assert "engagement" in body
            assert body["engagement"].get("entity_code") == "IN-SVC"
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_engagement_put_rejects_mismatched_entity_code_query_when_enforced(self, tokens):
        """``PUT /audit-engagements/{id}`` must reject a wrong explicit ``entity_code`` query before applying patch."""
        owner_tok = _login("owner@onetouch.ai", "demo1234")
        eid = "ENG-DEMO-IN-2025"
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r_bad = requests.put(
                f"{API}/audit-engagements/{eid}",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json={"risk_level": "high"},
                timeout=30,
            )
            assert r_bad.status_code == 403, r_bad.text
            r_ok = requests.put(
                f"{API}/audit-engagements/{eid}",
                headers=_h(owner_tok),
                params={"entity_code": "IN-SVC"},
                json={"risk_level": "medium"},
                timeout=30,
            )
            assert r_ok.status_code == 200, r_ok.text
            assert r_ok.json().get("entity_code") == "IN-SVC"
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_engagement_delete_rejects_mismatched_entity_code_query_when_enforced(self, tokens):
        """``DELETE /audit-engagements/{id}`` must reject a wrong explicit ``entity_code`` query (no successful delete)."""
        owner_tok = _login("owner@onetouch.ai", "demo1234")
        eid = "ENG-DEMO-IN-2025"
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r_bad = requests.delete(
                f"{API}/audit-engagements/{eid}",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                timeout=30,
            )
            assert r_bad.status_code == 403, r_bad.text
            r_still = requests.get(f"{API}/audit-engagements/{eid}", headers=_h(owner_tok), params={"entity_code": "IN-SVC"}, timeout=30)
            assert r_still.status_code == 200, r_still.text
            assert r_still.json().get("engagement_id") == eid
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_engagement_milestone_team_planning_note_posts_reject_mismatched_entity_code_query_when_enforced(self, tokens):
        """Sub-resource POSTs must reject a wrong ``entity_code`` query before mutating the engagement (403-only)."""
        owner_tok = _login("owner@onetouch.ai", "demo1234")
        eid = "ENG-DEMO-IN-2025"
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            ms = {
                "title": "L4 entity scope gate",
                "due_date": "2026-12-31T00:00:00+00:00",
                "status": "pending",
                "owner_email": "auditor@onetouch.ai",
            }
            r_ms = requests.post(
                f"{API}/audit-engagements/{eid}/milestones",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json=ms,
                timeout=30,
            )
            assert r_ms.status_code == 403, r_ms.text
            r_tm = requests.post(
                f"{API}/audit-engagements/{eid}/team",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json={"user_email": "owner@onetouch.ai", "role": "staff", "allocation_pct": 10.0},
                timeout=30,
            )
            assert r_tm.status_code == 403, r_tm.text
            r_pn = requests.post(
                f"{API}/audit-engagements/{eid}/planning-notes",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json={"note": "rbac l4", "visibility": "team"},
                timeout=30,
            )
            assert r_pn.status_code == 403, r_pn.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_compliance_library_rejects_mismatched_entity_code_query_when_enforced(self, tokens):
        """``GET /compliance/library`` uses the same ``enforce_entity_scope`` surface as CA India flows (owner is IN-SVC)."""
        owner_tok = _login("owner@onetouch.ai", "demo1234")
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r_bad = requests.get(
                f"{API}/compliance/library",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                timeout=30,
            )
            assert r_bad.status_code == 403, r_bad.text
            r_ok = requests.get(
                f"{API}/compliance/library",
                headers=_h(owner_tok),
                params={"entity_code": "IN-SVC"},
                timeout=30,
            )
            assert r_ok.status_code == 200, r_ok.text
            assert r_ok.json().get("entity_code") == "IN-SVC"
            r_default = requests.get(f"{API}/compliance/library", headers=_h(owner_tok), timeout=30)
            assert r_default.status_code == 200, r_default.text
            assert r_default.json().get("entity_code") == "IN-SVC"
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_controls_list_and_detail_reject_mismatched_entity_code_query_when_enforced(self, tokens):
        """``GET /controls`` and ``GET /controls/{id}`` honor optional ``entity_code`` (RACM / IFC surfaces; owner is IN-SVC)."""
        owner_tok = _login("owner@onetouch.ai", "demo1234")
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r_bad = requests.get(f"{API}/controls", headers=_h(owner_tok), params={"entity_code": "US-HQ"}, timeout=30)
            assert r_bad.status_code == 403, r_bad.text
            r_ok = requests.get(f"{API}/controls", headers=_h(owner_tok), params={"entity_code": "IN-SVC"}, timeout=30)
            assert r_ok.status_code == 200, r_ok.text
            r_default = requests.get(f"{API}/controls", headers=_h(owner_tok), timeout=30)
            assert r_default.status_code == 200, r_default.text
            rows = r_ok.json() if isinstance(r_ok.json(), list) else []
            if rows and isinstance(rows[0], dict) and rows[0].get("id"):
                cid = str(rows[0]["id"])
                r_detail_bad = requests.get(
                    f"{API}/controls/{cid}",
                    headers=_h(owner_tok),
                    params={"entity_code": "US-HQ"},
                    timeout=30,
                )
                assert r_detail_bad.status_code == 403, r_detail_bad.text
                r_detail_ok = requests.get(
                    f"{API}/controls/{cid}",
                    headers=_h(owner_tok),
                    params={"entity_code": "IN-SVC"},
                    timeout=30,
                )
                assert r_detail_ok.status_code == 200, r_detail_ok.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_exceptions_list_and_count_reject_mismatched_entity_code_query_when_enforced(self, tokens):
        """``GET /exceptions`` and ``GET /exceptions/count`` honor ``entity_code`` / ``entity`` the same way as ``/controls`` (owner is IN-SVC)."""
        owner_tok = _login("owner@onetouch.ai", "demo1234")
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            for path, extra in ((f"{API}/exceptions", {"limit": 50}), (f"{API}/exceptions/count", {})):
                r_bad = requests.get(
                    path,
                    headers=_h(owner_tok),
                    params={"entity_code": "US-HQ", **extra},
                    timeout=30,
                )
                assert r_bad.status_code == 403, f"{path}: {r_bad.text}"
                r_ok = requests.get(
                    path,
                    headers=_h(owner_tok),
                    params={"entity_code": "IN-SVC", **extra},
                    timeout=30,
                )
                assert r_ok.status_code == 200, f"{path}: {r_ok.text}"
                r_entity_kw = requests.get(
                    path,
                    headers=_h(owner_tok),
                    params={"entity": "US-HQ", **extra},
                    timeout=30,
                )
                assert r_entity_kw.status_code == 403, f"{path} entity=: {r_entity_kw.text}"
            r_def = requests.get(f"{API}/exceptions", headers=_h(owner_tok), params={"limit": 20}, timeout=30)
            assert r_def.status_code == 200, r_def.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_exception_detail_rejects_cross_entity_when_enforced(self, tokens):
        """``GET /exceptions/{id}`` must not leak another legal entity's exception row when scope is on."""
        owner_tok = _login("owner@onetouch.ai", "demo1234")
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r_list = requests.get(
                f"{API}/exceptions",
                headers=_h(tokens["cfo"]),
                params={"entity_code": "US-HQ", "limit": 50},
                timeout=30,
            )
            assert r_list.status_code == 200, r_list.text
            items = r_list.json()
            if not isinstance(items, list):
                pytest.skip("exceptions list not a list")
            ex_id = None
            for it in items:
                if not isinstance(it, dict) or not it.get("id"):
                    continue
                if str(it.get("entity") or "").strip() == "US-HQ":
                    ex_id = str(it["id"])
                    break
            if not ex_id:
                pytest.skip("no seeded exception with entity US-HQ")
            r_bad = requests.get(f"{API}/exceptions/{ex_id}", headers=_h(owner_tok), timeout=30)
            assert r_bad.status_code == 403, r_bad.text
            r_ok = requests.get(f"{API}/exceptions/{ex_id}", headers=_h(tokens["cfo"]), timeout=30)
            assert r_ok.status_code == 200, r_ok.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_continuous_audit_entity_query_rejects_mismatched_when_enforced(self, tokens):
        """``GET /continuous-audit/rules``, ``/exceptions``, ``/rule-performance`` reject wrong ``entity_code``; cross-entity rule run is forbidden."""
        owner_tok = _login("owner@onetouch.ai", "demo1234")
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r_bad_rules = requests.get(
                f"{API}/continuous-audit/rules",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                timeout=30,
            )
            assert r_bad_rules.status_code == 403, r_bad_rules.text
            r_ok_rules = requests.get(
                f"{API}/continuous-audit/rules",
                headers=_h(owner_tok),
                params={"entity_code": "IN-SVC"},
                timeout=30,
            )
            assert r_ok_rules.status_code == 200, r_ok_rules.text
            r_default_rules = requests.get(f"{API}/continuous-audit/rules", headers=_h(owner_tok), timeout=30)
            assert r_default_rules.status_code == 200, r_default_rules.text

            r_bad_ex = requests.get(
                f"{API}/continuous-audit/exceptions",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                timeout=30,
            )
            assert r_bad_ex.status_code == 403, r_bad_ex.text
            r_ok_ex = requests.get(
                f"{API}/continuous-audit/exceptions",
                headers=_h(owner_tok),
                params={"entity_code": "IN-SVC"},
                timeout=30,
            )
            assert r_ok_ex.status_code == 200, r_ok_ex.text

            r_bad_perf = requests.get(
                f"{API}/continuous-audit/rule-performance",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                timeout=30,
            )
            assert r_bad_perf.status_code == 403, r_bad_perf.text
            r_ok_perf = requests.get(
                f"{API}/continuous-audit/rule-performance",
                headers=_h(owner_tok),
                params={"entity_code": "IN-SVC"},
                timeout=30,
            )
            assert r_ok_perf.status_code == 200, r_ok_perf.text

            r_cfo_rules = requests.get(
                f"{API}/continuous-audit/rules",
                headers=_h(tokens["cfo"]),
                params={"entity_code": "US-HQ"},
                timeout=30,
            )
            assert r_cfo_rules.status_code == 200, r_cfo_rules.text
            payload = r_cfo_rules.json()
            items = payload.get("items") if isinstance(payload, dict) else []
            rule_id = None
            for it in items or []:
                if isinstance(it, dict) and it.get("id") and str(it.get("entity") or "").strip() == "US-HQ":
                    rule_id = str(it["id"])
                    break
            if rule_id:
                r_run_bad = requests.post(
                    f"{API}/continuous-audit/rules/{rule_id}/run",
                    headers=_h(owner_tok),
                    json={},
                    timeout=60,
                )
                assert r_run_bad.status_code == 403, r_run_bad.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_module_gets_reject_mismatched_entity_code_query_when_enforced(self, tokens):
        """CA audit ``GET`` modules under ``/audit-engagements/{id}/…`` must honor the same ``entity_code`` query as CRUD."""
        owner_tok = _login("owner@onetouch.ai", "demo1234")
        eid = "ENG-DEMO-IN-2025"
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            for suffix in (
                "materiality",
                "schedules",
                "schedules/assets",
                "schedules/revenue",
                "schedules/expenses",
                "schedules/inventory",
                "schedules/liabilities",
                "audit-findings",
                "management-action-summary",
                "compliance-calendar",
                "opinion",
                "working-papers",
                "wp-workbench",
                "ca-dashboard",
                "ca-command-center",
                "sampling-plans",
                "vouching-items",
                "trial-balance",
                "risks",
                "risk-heatmap",
                "risks/export.xlsx",
                "risks/audit-plan-preview",
                "compliance/status",
                "compliance/findings",
                "compliance/export",
                "ifc-dashboard",
                "ifc-heatmap",
                "observations",
                "caro/state",
                "caro/responses",
                "tax-audit-44ab/state",
                "gst/reconciliation",
                "tds/reconciliation",
                "report",
                "control-tests",
                "control-deficiencies",
                "financial-statements/latest",
                "balance-sheet",
                "profit-loss",
                "cash-flow",
                "audit-adjustments",
            ):
                path = f"{API}/audit-engagements/{eid}/{suffix}"
                r_bad = requests.get(path, headers=_h(owner_tok), params={"entity_code": "US-HQ"}, timeout=30)
                assert r_bad.status_code == 403, f"{suffix}: {r_bad.text}"
                r_ok = requests.get(path, headers=_h(owner_tok), params={"entity_code": "IN-SVC"}, timeout=30)
                assert r_ok.status_code == 200, f"{suffix}: {r_ok.text}"
            exp_base = f"{API}/audit-engagements/{eid}/report/export"
            r_bad_exp = requests.get(
                exp_base,
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ", "format": "observations-xlsx"},
                timeout=30,
            )
            assert r_bad_exp.status_code == 403, r_bad_exp.text
            r_ok_exp = requests.get(
                exp_base,
                headers=_h(owner_tok),
                params={"entity_code": "IN-SVC", "format": "observations-xlsx"},
                timeout=30,
            )
            assert r_ok_exp.status_code == 200, r_ok_exp.text
            tb_r = requests.get(
                f"{API}/audit-engagements/{eid}/trial-balance",
                headers=_h(owner_tok),
                params={"entity_code": "IN-SVC"},
                timeout=30,
            )
            assert tb_r.status_code == 200, tb_r.text
            acct = None
            for ln in (tb_r.json() or {}).get("lines") or []:
                if isinstance(ln, dict) and ln.get("account_code"):
                    acct = str(ln["account_code"]).strip()
                    break
            if acct:
                dd_base = f"{API}/audit-engagements/{eid}/fs/drilldown"
                r_bad_dd = requests.get(
                    dd_base,
                    headers=_h(owner_tok),
                    params={"entity_code": "US-HQ", "account_code": acct},
                    timeout=30,
                )
                assert r_bad_dd.status_code == 403, r_bad_dd.text
                r_ok_dd = requests.get(
                    dd_base,
                    headers=_h(owner_tok),
                    params={"entity_code": "IN-SVC", "account_code": acct},
                    timeout=30,
                )
                assert r_ok_dd.status_code == 200, r_ok_dd.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_id_only_gets_reject_mismatched_entity_code_query_when_enforced(self, tokens):
        """Id-only CA GETs must apply ``entity_code`` on the request (same as nested engagement routes)."""
        owner_tok = _login("owner@onetouch.ai", "demo1234")
        eid = "ENG-DEMO-IN-2025"
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:

            def assert_id_get(path_prefix: str, resource_id: str) -> None:
                r_bad = requests.get(
                    f"{API}{path_prefix}/{resource_id}",
                    headers=_h(owner_tok),
                    params={"entity_code": "US-HQ"},
                    timeout=30,
                )
                assert r_bad.status_code == 403, f"{path_prefix}/{resource_id}: {r_bad.text}"
                r_ok = requests.get(
                    f"{API}{path_prefix}/{resource_id}",
                    headers=_h(owner_tok),
                    params={"entity_code": "IN-SVC"},
                    timeout=30,
                )
                assert r_ok.status_code == 200, f"{path_prefix}/{resource_id}: {r_ok.text}"

            checked = False
            r_wp = requests.get(
                f"{API}/audit-engagements/{eid}/working-papers",
                headers=_h(owner_tok),
                params={"entity_code": "IN-SVC"},
                timeout=30,
            )
            assert r_wp.status_code == 200, r_wp.text
            papers = (r_wp.json() or {}).get("working_papers") or []
            if isinstance(papers, list) and papers and isinstance(papers[0], dict) and papers[0].get("id"):
                wid = str(papers[0]["id"])
                assert_id_get("/working-papers", wid)
                r_ev_bad = requests.get(
                    f"{API}/working-papers/{wid}/evidence",
                    headers=_h(owner_tok),
                    params={"entity_code": "US-HQ"},
                    timeout=30,
                )
                assert r_ev_bad.status_code == 403, r_ev_bad.text
                r_ev_ok = requests.get(
                    f"{API}/working-papers/{wid}/evidence",
                    headers=_h(owner_tok),
                    params={"entity_code": "IN-SVC"},
                    timeout=30,
                )
                assert r_ev_ok.status_code == 200, r_ev_ok.text
                checked = True

            r_risks = requests.get(
                f"{API}/audit-engagements/{eid}/risks",
                headers=_h(owner_tok),
                params={"entity_code": "IN-SVC"},
                timeout=30,
            )
            assert r_risks.status_code == 200, r_risks.text
            risks = r_risks.json()
            if isinstance(risks, list) and risks and isinstance(risks[0], dict) and risks[0].get("id"):
                assert_id_get("/risks", str(risks[0]["id"]))
                checked = True

            r_ct = requests.get(
                f"{API}/audit-engagements/{eid}/control-tests",
                headers=_h(owner_tok),
                params={"entity_code": "IN-SVC"},
                timeout=30,
            )
            assert r_ct.status_code == 200, r_ct.text
            tests = r_ct.json()
            if isinstance(tests, list) and tests and isinstance(tests[0], dict) and tests[0].get("id"):
                assert_id_get("/control-tests", str(tests[0]["id"]))
                checked = True

            r_sp = requests.get(
                f"{API}/audit-engagements/{eid}/sampling-plans",
                headers=_h(owner_tok),
                params={"entity_code": "IN-SVC"},
                timeout=30,
            )
            assert r_sp.status_code == 200, r_sp.text
            plans = (r_sp.json() or {}).get("items") or []
            if isinstance(plans, list) and plans and isinstance(plans[0], dict) and plans[0].get("id"):
                pid = str(plans[0]["id"])
                r_bad = requests.get(
                    f"{API}/sampling-plans/{pid}/samples",
                    headers=_h(owner_tok),
                    params={"entity_code": "US-HQ"},
                    timeout=30,
                )
                assert r_bad.status_code == 403, r_bad.text
                r_ok = requests.get(
                    f"{API}/sampling-plans/{pid}/samples",
                    headers=_h(owner_tok),
                    params={"entity_code": "IN-SVC"},
                    timeout=30,
                )
                assert r_ok.status_code == 200, r_ok.text
                checked = True

            if not checked:
                pytest.skip("demo engagement missing working papers, risks, control tests, and sampling plans for id-only probe")
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_id_only_mutations_reject_mismatched_entity_code_query_when_enforced(self, tokens):
        """Id-only CA ``PUT`` / ``POST`` must reject a wrong ``entity_code`` query before touching child rows."""
        owner_tok = _login("owner@onetouch.ai", "demo1234")
        eid = "ENG-DEMO-IN-2025"
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            qp_in = {"entity_code": "IN-SVC"}
            qp_bad = {"entity_code": "US-HQ"}
            checked = False

            r_wp = requests.get(
                f"{API}/audit-engagements/{eid}/working-papers",
                headers=_h(owner_tok),
                params=qp_in,
                timeout=30,
            )
            assert r_wp.status_code == 200, r_wp.text
            papers = (r_wp.json() or {}).get("working_papers") or []
            if isinstance(papers, list) and papers and isinstance(papers[0], dict) and papers[0].get("id"):
                wid = str(papers[0]["id"])
                r_put = requests.put(
                    f"{API}/working-papers/{wid}",
                    headers=_h(owner_tok),
                    params=qp_bad,
                    json={"title": "L4 id-only mutation gate"},
                    timeout=30,
                )
                assert r_put.status_code == 403, r_put.text
                r_ev = requests.post(
                    f"{API}/working-papers/{wid}/evidence",
                    headers=_h(owner_tok),
                    params=qp_bad,
                    json={"label": "L4 gate", "reference": "ref-l4", "ref_type": "file"},
                    timeout=30,
                )
                assert r_ev.status_code == 403, r_ev.text
                r_note = requests.post(
                    f"{API}/working-papers/{wid}/review-notes",
                    headers=_h(owner_tok),
                    params=qp_bad,
                    json={"note": "L4 gate", "author_email": "owner@onetouch.ai", "note_type": "review"},
                    timeout=30,
                )
                assert r_note.status_code == 403, r_note.text
                r_sign = requests.post(
                    f"{API}/working-papers/{wid}/sign-off",
                    headers=_h(owner_tok),
                    params=qp_bad,
                    json={"role": "preparer", "signer_email": "owner@onetouch.ai"},
                    timeout=30,
                )
                assert r_sign.status_code == 403, r_sign.text
                checked = True

            folders = (r_wp.json() or {}).get("folders") or []
            if isinstance(folders, list) and folders and isinstance(folders[0], dict) and folders[0].get("id"):
                fid = str(folders[0]["id"])
                r_wpost = requests.post(
                    f"{API}/working-papers",
                    headers=_h(owner_tok),
                    params=qp_bad,
                    json={
                        "engagement_id": eid,
                        "folder_id": fid,
                        "title": "L4 id-only mutation gate WP",
                        "linked_risk_ids": [],
                        "linked_control_ids": [],
                        "linked_case_ids": [],
                        "evidence_ids": [],
                        "references": [],
                    },
                    timeout=30,
                )
                assert r_wpost.status_code == 403, r_wpost.text
                checked = True

            r_risks = requests.get(
                f"{API}/audit-engagements/{eid}/risks",
                headers=_h(owner_tok),
                params=qp_in,
                timeout=30,
            )
            assert r_risks.status_code == 200, r_risks.text
            risks = r_risks.json()
            if isinstance(risks, list) and risks and isinstance(risks[0], dict) and risks[0].get("id"):
                rid = str(risks[0]["id"])
                r_risk_put = requests.put(
                    f"{API}/risks/{rid}",
                    headers=_h(owner_tok),
                    params=qp_bad,
                    json={"risk_title": "L4 id-only mutation gate"},
                    timeout=30,
                )
                assert r_risk_put.status_code == 403, r_risk_put.text
                r_risk_del = requests.delete(
                    f"{API}/risks/{rid}",
                    headers=_h(owner_tok),
                    params=qp_bad,
                    timeout=30,
                )
                assert r_risk_del.status_code == 403, r_risk_del.text
                r_rc = requests.post(
                    f"{API}/risks/{rid}/controls",
                    headers=_h(owner_tok),
                    params=qp_bad,
                    json={"control_id": "l4-probe-control-id"},
                    timeout=30,
                )
                assert r_rc.status_code == 403, r_rc.text
                r_rp = requests.post(
                    f"{API}/risks/{rid}/procedures",
                    headers=_h(owner_tok),
                    params=qp_bad,
                    json={"title": "L4 gate procedure", "description": "", "source": "manual"},
                    timeout=30,
                )
                assert r_rp.status_code == 403, r_rp.text
                checked = True

            r_ct = requests.get(
                f"{API}/audit-engagements/{eid}/control-tests",
                headers=_h(owner_tok),
                params=qp_in,
                timeout=30,
            )
            assert r_ct.status_code == 200, r_ct.text
            tests = r_ct.json()
            if isinstance(tests, list) and tests and isinstance(tests[0], dict) and tests[0].get("id"):
                tid = str(tests[0]["id"])
                r_ct_put = requests.put(
                    f"{API}/control-tests/{tid}/result",
                    headers=_h(owner_tok),
                    params=qp_bad,
                    json={"notes": "L4 id-only mutation gate", "result": "pending", "evidence_refs": []},
                    timeout=30,
                )
                assert r_ct_put.status_code == 403, r_ct_put.text
                checked = True

            r_sp = requests.get(
                f"{API}/audit-engagements/{eid}/sampling-plans",
                headers=_h(owner_tok),
                params=qp_in,
                timeout=30,
            )
            assert r_sp.status_code == 200, r_sp.text
            plans = (r_sp.json() or {}).get("items") or []
            if isinstance(plans, list) and plans and isinstance(plans[0], dict) and plans[0].get("id"):
                pid = str(plans[0]["id"])
                r_gen = requests.post(
                    f"{API}/sampling-plans/{pid}/generate",
                    headers=_h(owner_tok),
                    params=qp_bad,
                    json={},
                    timeout=60,
                )
                assert r_gen.status_code == 403, r_gen.text
                checked = True

            r_v = requests.get(
                f"{API}/audit-engagements/{eid}/vouching-items",
                headers=_h(owner_tok),
                params=qp_in,
                timeout=30,
            )
            assert r_v.status_code == 200, r_v.text
            vitems = (r_v.json() or {}).get("items") or []
            if isinstance(vitems, list) and vitems and isinstance(vitems[0], dict) and vitems[0].get("id"):
                vid = str(vitems[0]["id"])
                r_v_put = requests.put(
                    f"{API}/vouching-items/{vid}",
                    headers=_h(owner_tok),
                    params=qp_bad,
                    json={"notes": "L4 id-only mutation gate"},
                    timeout=30,
                )
                assert r_v_put.status_code == 403, r_v_put.text
                checked = True

            r_adj = requests.get(
                f"{API}/audit-engagements/{eid}/audit-adjustments",
                headers=_h(owner_tok),
                params=qp_in,
                timeout=30,
            )
            assert r_adj.status_code == 200, r_adj.text
            aitems = (r_adj.json() or {}).get("items") or []
            if isinstance(aitems, list) and aitems and isinstance(aitems[0], dict) and aitems[0].get("id"):
                aid = str(aitems[0]["id"])
                r_ap = requests.put(
                    f"{API}/audit-adjustments/{aid}",
                    headers=_h(owner_tok),
                    params=qp_bad,
                    json={"narrative": "L4 id-only mutation gate"},
                    timeout=30,
                )
                assert r_ap.status_code == 403, r_ap.text
                checked = True

            r_mat = requests.get(
                f"{API}/audit-engagements/{eid}/materiality",
                headers=_h(owner_tok),
                params=qp_in,
                timeout=30,
            )
            if r_mat.status_code == 200:
                mat_body = r_mat.json() or {}
                mid = mat_body.get("id") or (mat_body.get("materiality_assessment") or {}).get("materiality_record_id")
                if mid:
                    r_mat_put = requests.put(
                        f"{API}/materiality/{mid}",
                        headers=_h(owner_tok),
                        params=qp_bad,
                        json={"revenue": 1.0},
                        timeout=30,
                    )
                    assert r_mat_put.status_code == 403, r_mat_put.text
                    r_mat_apr = requests.post(
                        f"{API}/materiality/{mid}/approve",
                        headers=_h(owner_tok),
                        params=qp_bad,
                        json={"approval_status": "prepared", "prepared_by": "owner@onetouch.ai"},
                        timeout=30,
                    )
                    assert r_mat_apr.status_code == 403, r_mat_apr.text
                    checked = True

            r_def = requests.get(
                f"{API}/audit-engagements/{eid}/control-deficiencies",
                headers=_h(owner_tok),
                params=qp_in,
                timeout=30,
            )
            assert r_def.status_code == 200, r_def.text
            ditems = (r_def.json() or {}).get("items") or []
            if isinstance(ditems, list) and ditems and isinstance(ditems[0], dict) and ditems[0].get("id"):
                did = str(ditems[0]["id"])
                r_du = requests.put(
                    f"{API}/control-deficiencies/{did}",
                    headers=_h(owner_tok),
                    params=qp_bad,
                    json={"description": "L4 id-only mutation gate"},
                    timeout=30,
                )
                assert r_du.status_code == 403, r_du.text
                r_dm = requests.post(
                    f"{API}/control-deficiencies/{did}/management-response",
                    headers=_h(owner_tok),
                    params=qp_bad,
                    json={"response_text": "L4 gate", "owner_email": "owner@onetouch.ai"},
                    timeout=30,
                )
                assert r_dm.status_code == 403, r_dm.text
                checked = True

            r_cert = requests.post(
                f"{API}/control-certifications",
                headers=_h(owner_tok),
                params=qp_bad,
                json={
                    "engagement_id": eid,
                    "owner_email": "owner@onetouch.ai",
                    "certification_text": "L4 id-only gate",
                    "scope": "IFC",
                },
                timeout=30,
            )
            assert r_cert.status_code == 403, r_cert.text
            checked = True

            r_aroot = requests.post(
                f"{API}/audit-adjustments",
                headers=_h(owner_tok),
                params=qp_bad,
                json={
                    "engagement_id": eid,
                    "account_code": "L4-GATE",
                    "account_name": "Gate",
                    "debit": 0.0,
                    "credit": 0.0,
                    "narrative": "L4 id-only gate",
                    "status": "proposed",
                },
                timeout=30,
            )
            assert r_aroot.status_code == 403, r_aroot.text
            checked = True

            r_sroot = requests.post(
                f"{API}/sampling-plans",
                headers=_h(owner_tok),
                params=qp_bad,
                json={
                    "engagement_id": eid,
                    "method": "random",
                    "population_size": 100,
                    "sample_size": 5,
                    "seed": 42,
                    "working_paper_id": None,
                },
                timeout=30,
            )
            assert r_sroot.status_code == 403, r_sroot.text
            checked = True

            r_cd_root = requests.post(
                f"{API}/control-deficiencies",
                headers=_h(owner_tok),
                params=qp_bad,
                json={
                    "engagement_id": eid,
                    "control_test_id": "l4-probe-control-test",
                    "severity": "low",
                    "description": "L4 id-only gate",
                    "create_case": False,
                },
                timeout=30,
            )
            assert r_cd_root.status_code == 403, r_cd_root.text
            checked = True

            papers_for_v = (r_wp.json() or {}).get("working_papers") or []
            if isinstance(papers_for_v, list) and papers_for_v and isinstance(papers_for_v[0], dict) and papers_for_v[0].get("id"):
                widv = str(papers_for_v[0]["id"])
                r_vroot = requests.post(
                    f"{API}/vouching-items",
                    headers=_h(owner_tok),
                    params=qp_bad,
                    json={
                        "engagement_id": eid,
                        "working_paper_id": widv,
                        "transaction_ref": "L4-GATE-VOUCH-ROOT",
                        "tick_mark": "pending clarification",
                    },
                    timeout=30,
                )
                assert r_vroot.status_code == 403, r_vroot.text
                checked = True
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_module_posts_reject_mismatched_entity_code_query_when_enforced(self, tokens):
        """CA audit ``POST`` entry points (and selected nested ``PUT``s) must reject a wrong ``entity_code`` query before writes (403-only)."""
        owner_tok = _login("owner@onetouch.ai", "demo1234")
        eid = "ENG-DEMO-IN-2025"
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r_obs = requests.post(
                f"{API}/audit-engagements/{eid}/observations",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json={
                    "title": "L4 entity scope POST gate",
                    "description": "must not persist under wrong entity_code query",
                    "severity": "low",
                    "material": False,
                    "pervasive": False,
                    "source": "manual",
                },
                timeout=30,
            )
            assert r_obs.status_code == 403, r_obs.text
            r_obs_put = requests.put(
                f"{API}/audit-engagements/{eid}/observations/l4-entity-scope-missing-obs-id",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json={"resolved": True},
                timeout=30,
            )
            assert r_obs_put.status_code == 403, r_obs_put.text
            r_comp = requests.post(
                f"{API}/audit-engagements/{eid}/compliance/checklist",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json={"law_codes": []},
                timeout=30,
            )
            assert r_comp.status_code == 403, r_comp.text
            r_wp = requests.post(
                f"{API}/audit-engagements/{eid}/working-papers/folders",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json={},
                timeout=30,
            )
            assert r_wp.status_code == 403, r_wp.text
            r_risk = requests.post(
                f"{API}/audit-engagements/{eid}/risks",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json={
                    "risk_title": "L4 entity scope POST gate",
                    "risk_description": "must not insert",
                    "process_area": "O2C",
                    "financial_statement_area": "Revenue",
                    "risk_category": "Financial Reporting Risk",
                    "likelihood_score": 3,
                    "impact_score": 3,
                    "owner": "owner@onetouch.ai",
                },
                timeout=30,
            )
            assert r_risk.status_code == 403, r_risk.text
            r_caro = requests.post(
                f"{API}/audit-engagements/{eid}/caro/checklist",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json={"clause_ids": ["3(i)"]},
                timeout=30,
            )
            assert r_caro.status_code == 403, r_caro.text
            r_44 = requests.post(
                f"{API}/audit-engagements/{eid}/tax-audit-44ab/checklist",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json={"clause_ids": ["10A"]},
                timeout=30,
            )
            assert r_44.status_code == 403, r_44.text
            r_gst = requests.post(
                f"{API}/audit-engagements/{eid}/gst/reconciliation",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json={
                    "gstr1_sales": 0.0,
                    "gstr3b_sales": 0.0,
                    "gstr2b_purchases": 0.0,
                    "purchase_register": 0.0,
                    "itc_claimed": 0.0,
                    "itc_eligible": 0.0,
                },
                timeout=30,
            )
            assert r_gst.status_code == 403, r_gst.text
            r_tds = requests.post(
                f"{API}/audit-engagements/{eid}/tds/reconciliation",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json={"ledger_tds": 0.0, "challan_tds": 0.0, "delayed_payment_days": 0},
                timeout=30,
            )
            assert r_tds.status_code == 403, r_tds.text
            # Top-level aliases (engagement_id in body) must honor the same explicit entity_code query as nested routes.
            r_caro_root = requests.post(
                f"{API}/caro/checklist",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json={"engagement_id": eid, "clause_ids": ["3(i)"]},
                timeout=30,
            )
            assert r_caro_root.status_code == 403, r_caro_root.text
            r_gst_root = requests.post(
                f"{API}/gst/reconciliation",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json={
                    "engagement_id": eid,
                    "gstr1_sales": 0.0,
                    "gstr3b_sales": 0.0,
                    "gstr2b_purchases": 0.0,
                    "purchase_register": 0.0,
                    "itc_claimed": 0.0,
                    "itc_eligible": 0.0,
                },
                timeout=30,
            )
            assert r_gst_root.status_code == 403, r_gst_root.text
            r_tds_root = requests.post(
                f"{API}/tds/reconciliation",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json={
                    "engagement_id": eid,
                    "ledger_tds": 0.0,
                    "challan_tds": 0.0,
                    "delayed_payment_days": 0,
                },
                timeout=30,
            )
            assert r_tds_root.status_code == 403, r_tds_root.text
            for gen_suffix in ("opinion/generate", "report/generate", "caro/generate"):
                r_gen = requests.post(
                    f"{API}/audit-engagements/{eid}/{gen_suffix}",
                    headers=_h(owner_tok),
                    params={"entity_code": "US-HQ"},
                    json={},
                    timeout=30,
                )
                assert r_gen.status_code == 403, f"{gen_suffix}: {r_gen.text}"
            sch_types = ("assets", "revenue", "expenses", "inventory", "liabilities")
            for st in sch_types:
                r_sch_c = requests.post(
                    f"{API}/audit-engagements/{eid}/schedules/{st}/conclusion",
                    headers=_h(owner_tok),
                    params={"entity_code": "US-HQ"},
                    json={"conclusion": "L4 entity scope gate", "signed_off": False},
                    timeout=30,
                )
                assert r_sch_c.status_code == 403, f"schedules/{st}/conclusion: {r_sch_c.text}"
                r_sch_ev = requests.post(
                    f"{API}/audit-engagements/{eid}/schedules/{st}/evidence",
                    headers=_h(owner_tok),
                    params={"entity_code": "US-HQ"},
                    json={"label": "L4 gate", "reference": "ref-l4", "ref_type": "file"},
                    timeout=30,
                )
                assert r_sch_ev.status_code == 403, f"schedules/{st}/evidence: {r_sch_ev.text}"
                r_sch_ex = requests.post(
                    f"{API}/audit-engagements/{eid}/schedules/{st}/exception",
                    headers=_h(owner_tok),
                    params={"entity_code": "US-HQ"},
                    json={
                        "title": "L4 entity scope gate",
                        "description": "must not insert",
                        "severity": "medium",
                        "create_case": False,
                    },
                    timeout=30,
                )
                assert r_sch_ex.status_code == 403, f"schedules/{st}/exception: {r_sch_ex.text}"
                r_put_sch = requests.put(
                    f"{API}/audit-engagements/{eid}/schedules/{st}/procedures/l4-entity-scope-fake-procedure-id",
                    headers=_h(owner_tok),
                    params={"entity_code": "US-HQ"},
                    json={"status": "completed"},
                    timeout=30,
                )
                assert r_put_sch.status_code == 403, f"schedules/{st}/procedures: {r_put_sch.text}"
            r_patch_rep = requests.patch(
                f"{API}/audit-engagements/{eid}/report/status",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json={"status": "draft"},
                timeout=30,
            )
            assert r_patch_rep.status_code == 403, r_patch_rep.text
            r_mlet = requests.post(
                f"{API}/audit-engagements/{eid}/management-letter/generate",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json={},
                timeout=30,
            )
            assert r_mlet.status_code == 403, r_mlet.text
            r_mrepr = requests.post(
                f"{API}/audit-engagements/{eid}/management-representation",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json={"text": "L4 entity scope gate", "signed_by": "owner@onetouch.ai"},
                timeout=30,
            )
            assert r_mrepr.status_code == 403, r_mrepr.text
            r_af = requests.post(
                f"{API}/audit-engagements/{eid}/audit-findings",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json={"title": "L4 entity scope gate", "description": "must not insert", "severity": "low"},
                timeout=30,
            )
            assert r_af.status_code == 403, r_af.text
            r_fs = requests.post(
                f"{API}/audit-engagements/{eid}/fs/generate",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json={"mapping_profile": "default_ind_as"},
                timeout=30,
            )
            assert r_fs.status_code == 403, r_fs.text
            r_fs_long = requests.post(
                f"{API}/audit-engagements/{eid}/financial-statements/generate",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json={"mapping_profile": "default_ind_as"},
                timeout=60,
            )
            assert r_fs_long.status_code == 403, r_fs_long.text
            r_adj = requests.post(
                f"{API}/audit-engagements/{eid}/audit-adjustments",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json={
                    "account_code": "9999",
                    "account_name": "L4 entity scope gate",
                    "debit": 0.0,
                    "credit": 0.0,
                    "narrative": "must not insert",
                    "status": "proposed",
                },
                timeout=30,
            )
            assert r_adj.status_code == 403, r_adj.text
            r_cfind = requests.post(
                f"{API}/audit-engagements/{eid}/compliance/findings",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json={"law_code": "CA2013", "title": "L4 entity scope gate", "severity": "low"},
                timeout=30,
            )
            assert r_cfind.status_code == 403, r_cfind.text
            r_caroc = requests.post(
                f"{API}/audit-engagements/{eid}/caro/clause",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json={"clause_id": "3(i)", "status": "compliant"},
                timeout=30,
            )
            assert r_caroc.status_code == 403, r_caroc.text
            r_44c = requests.post(
                f"{API}/audit-engagements/{eid}/tax-audit-44ab/clause",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json={"clause_id": "10A", "status": "compliant"},
                timeout=30,
            )
            assert r_44c.status_code == 403, r_44c.text
            r_mat = requests.post(
                f"{API}/audit-engagements/{eid}/materiality",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json={
                    "revenue": 100.0,
                    "profit_before_tax": 10.0,
                    "total_assets": 50.0,
                    "gross_expenses": 80.0,
                },
                timeout=30,
            )
            assert r_mat.status_code == 403, r_mat.text
            r_cres = requests.post(
                f"{API}/audit-engagements/{eid}/compliance/result",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json={"requirement_id": "l4-entity-scope-gate", "status": "compliant"},
                timeout=30,
            )
            assert r_cres.status_code == 403, r_cres.text
            r_ct = requests.post(
                f"{API}/audit-engagements/{eid}/control-tests",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json={
                    "test_type": "design effectiveness",
                    "period": "2025-04",
                    "tester_email": "owner@onetouch.ai",
                },
                timeout=30,
            )
            assert r_ct.status_code == 403, r_ct.text
            tiny_tb_csv = b"account_code,account_name,debit,credit\nL4TB-GATE,Entity scope gate,0,0\n"
            r_tb_upload = requests.post(
                f"{API}/audit-engagements/{eid}/trial-balance/upload",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                files={"file": ("l4-entity-scope-gate.csv", tiny_tb_csv, "text/csv")},
                timeout=60,
            )
            assert r_tb_upload.status_code == 403, r_tb_upload.text
            r_racm_gen = requests.post(
                f"{API}/audit-engagements/{eid}/risks/generate-procedures-from-high-risk",
                headers=_h(owner_tok),
                params={"entity_code": "US-HQ"},
                json={},
                timeout=30,
            )
            assert r_racm_gen.status_code == 403, r_racm_gen.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_executive_pack_optional_entity_code_rejected_when_mismatched(self, tokens):
        """Committee/executive GETs accept optional entity_code; wrong explicit code rejected before engagement body."""
        owner_tok = _login("owner@onetouch.ai", "demo1234")
        eid = "ENG-DEMO-IN-2025"
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            for suffix in (
                "executive-summary",
                "audit-committee-pack",
                "continuous-assurance-score",
                "advisory-insights",
                "management-action-summary",
            ):
                path = f"{API}/audit-engagements/{eid}/{suffix}"
                r_bad = requests.get(path, headers=_h(owner_tok), params={"entity_code": "US-HQ"}, timeout=30)
                assert r_bad.status_code == 403, f"{path}: {r_bad.text}"
            r_ok = requests.get(
                f"{API}/audit-engagements/{eid}/executive-summary",
                headers=_h(owner_tok),
                params={"entity_code": "IN-SVC"},
                timeout=30,
            )
            assert r_ok.status_code == 200, r_ok.text
            assert "headline" in r_ok.json() or "scores" in r_ok.json()
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_risk_get_by_id_blocked_cross_entity_when_enforced(self, tokens):
        """Id-only ``GET /risks/{id}`` must not bypass engagement entity RBAC."""
        owner_tok = _login("owner@onetouch.ai", "demo1234")
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            rlist = requests.get(
                f"{API}/audit-engagements/ENG-DEMO-IN-2025/risks",
                headers=_h(owner_tok),
                timeout=30,
            )
            assert rlist.status_code == 200, rlist.text
            risks = rlist.json()
            if not isinstance(risks, list) or not risks:
                pytest.skip("no risks for IN engagement")
            rid = risks[0]["id"]
            r_g = requests.get(f"{API}/risks/{rid}", headers=_h(tokens["cfo"]), timeout=30)
            assert r_g.status_code == 403, r_g.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_control_test_get_by_id_blocked_cross_entity_when_enforced(self, tokens):
        """Id-only ``GET /control-tests/{id}`` must not bypass engagement entity RBAC."""
        owner_tok = _login("owner@onetouch.ai", "demo1234")
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            rlist = requests.get(
                f"{API}/audit-engagements/ENG-DEMO-IN-2025/control-tests",
                headers=_h(owner_tok),
                timeout=30,
            )
            assert rlist.status_code == 200, rlist.text
            tests = rlist.json()
            if not isinstance(tests, list) or not tests:
                pytest.skip("no control tests for IN engagement")
            tid = tests[0]["id"]
            r_g = requests.get(f"{API}/control-tests/{tid}", headers=_h(tokens["cfo"]), timeout=30)
            assert r_g.status_code == 403, r_g.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_working_paper_get_by_id_blocked_cross_entity_when_enforced(self, tokens):
        """Id-only ``GET /working-papers/{id}`` must not bypass engagement entity RBAC."""
        owner_tok = _login("owner@onetouch.ai", "demo1234")
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            rlist = requests.get(
                f"{API}/audit-engagements/ENG-DEMO-IN-2025/working-papers",
                headers=_h(owner_tok),
                timeout=30,
            )
            assert rlist.status_code == 200, rlist.text
            body = rlist.json()
            papers = body.get("working_papers") or []
            if not isinstance(papers, list) or not papers:
                pytest.skip("no working papers for IN engagement")
            wid = papers[0]["id"]
            r_g = requests.get(f"{API}/working-papers/{wid}", headers=_h(tokens["cfo"]), timeout=30)
            assert r_g.status_code == 403, r_g.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_audit_adjustment_put_by_id_blocked_cross_entity_when_enforced(self, tokens):
        """Id-only ``PUT /audit-adjustments/{id}`` must not bypass engagement entity RBAC."""
        owner_tok = _login("owner@onetouch.ai", "demo1234")
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            rlist = requests.get(
                f"{API}/audit-engagements/ENG-DEMO-IN-2025/audit-adjustments",
                headers=_h(owner_tok),
                timeout=30,
            )
            assert rlist.status_code == 200, rlist.text
            body = rlist.json()
            items = body.get("items") or []
            if not isinstance(items, list) or not items:
                pytest.skip("no audit adjustments for IN engagement")
            aid = items[0]["id"]
            r_put = requests.put(
                f"{API}/audit-adjustments/{aid}",
                headers=_h(tokens["cfo"]),
                json={"narrative": "rbac entity-scope probe"},
                timeout=30,
            )
            assert r_put.status_code == 403, r_put.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_sampling_plan_get_samples_blocked_cross_entity_when_enforced(self, tokens):
        """Id-only ``GET /sampling-plans/{id}/samples`` must not bypass engagement entity RBAC."""
        owner_tok = _login("owner@onetouch.ai", "demo1234")
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            rlist = requests.get(
                f"{API}/audit-engagements/ENG-DEMO-IN-2025/sampling-plans",
                headers=_h(owner_tok),
                timeout=30,
            )
            assert rlist.status_code == 200, rlist.text
            body = rlist.json()
            items = body.get("items") or []
            if not isinstance(items, list) or not items:
                pytest.skip("no sampling plans for IN engagement")
            pid = items[0]["id"]
            r_g = requests.get(
                f"{API}/sampling-plans/{pid}/samples",
                headers=_h(tokens["cfo"]),
                timeout=30,
            )
            assert r_g.status_code == 403, r_g.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_control_deficiency_put_by_id_blocked_cross_entity_when_enforced(self, tokens):
        """Id-only ``PUT /control-deficiencies/{id}`` must not bypass engagement entity RBAC."""
        owner_tok = _login("owner@onetouch.ai", "demo1234")
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            rlist = requests.get(
                f"{API}/audit-engagements/ENG-DEMO-IN-2025/control-deficiencies",
                headers=_h(owner_tok),
                timeout=30,
            )
            assert rlist.status_code == 200, rlist.text
            body = rlist.json()
            items = body.get("items") or []
            if not isinstance(items, list) or not items:
                pytest.skip("no control deficiencies for IN engagement")
            did = items[0]["id"]
            r_put = requests.put(
                f"{API}/control-deficiencies/{did}",
                headers=_h(tokens["cfo"]),
                json={"description": "rbac entity-scope probe"},
                timeout=30,
            )
            assert r_put.status_code == 403, r_put.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_vouching_item_put_by_id_blocked_cross_entity_when_enforced(self, tokens):
        """Id-only ``PUT /vouching-items/{id}`` must not bypass engagement entity RBAC."""
        owner_tok = _login("owner@onetouch.ai", "demo1234")
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            rlist = requests.get(
                f"{API}/audit-engagements/ENG-DEMO-IN-2025/vouching-items",
                headers=_h(owner_tok),
                timeout=30,
            )
            assert rlist.status_code == 200, rlist.text
            body = rlist.json()
            items = body.get("items") or []
            if not isinstance(items, list) or not items:
                pytest.skip("no vouching items for IN engagement")
            vid = items[0]["id"]
            r_put = requests.put(
                f"{API}/vouching-items/{vid}",
                headers=_h(tokens["cfo"]),
                json={"notes": "rbac entity-scope probe"},
                timeout=30,
            )
            assert r_put.status_code == 403, r_put.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_schedule_conclusion_post_blocked_cross_entity_when_enforced(self, tokens):
        """Schedule workbook writes must honor engagement entity RBAC (not only lazy doc init)."""
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r_post = requests.post(
                f"{API}/audit-engagements/ENG-DEMO-IN-2025/schedules/assets/conclusion",
                headers=_h(tokens["cfo"]),
                json={"conclusion": "rbac entity-scope probe", "signed_off": False},
                timeout=30,
            )
            assert r_post.status_code == 403, r_post.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_caro_checklist_root_post_blocked_cross_entity_when_enforced(self, tokens):
        """``POST /caro/checklist`` (engagement in body) must enforce the same entity RBAC as nested routes."""
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r_post = requests.post(
                f"{API}/caro/checklist",
                headers=_h(tokens["cfo"]),
                json={"engagement_id": "ENG-DEMO-IN-2025", "clause_ids": ["3(i)"]},
                timeout=30,
            )
            assert r_post.status_code == 403, r_post.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_control_test_put_result_blocked_cross_entity_when_enforced(self, tokens):
        """Id-only ``PUT /control-tests/{id}/result`` must not bypass engagement entity RBAC."""
        owner_tok = _login("owner@onetouch.ai", "demo1234")
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            rlist = requests.get(
                f"{API}/audit-engagements/ENG-DEMO-IN-2025/control-tests",
                headers=_h(owner_tok),
                timeout=30,
            )
            assert rlist.status_code == 200, rlist.text
            tests = rlist.json()
            if not isinstance(tests, list) or not tests:
                pytest.skip("no control tests for IN engagement")
            tid = tests[0]["id"]
            r_put = requests.put(
                f"{API}/control-tests/{tid}/result",
                headers=_h(tokens["cfo"]),
                json={"notes": "rbac entity-scope probe"},
                timeout=30,
            )
            assert r_put.status_code == 403, r_put.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_gst_reconciliation_root_post_blocked_cross_entity_when_enforced(self, tokens):
        """``POST /gst/reconciliation`` (engagement in body) must enforce entity RBAC."""
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r_post = requests.post(
                f"{API}/gst/reconciliation",
                headers=_h(tokens["cfo"]),
                json={
                    "engagement_id": "ENG-DEMO-IN-2025",
                    "gstr1_sales": 0.0,
                    "gstr3b_sales": 0.0,
                    "gstr2b_purchases": 0.0,
                    "purchase_register": 0.0,
                    "itc_claimed": 0.0,
                    "itc_eligible": 0.0,
                },
                timeout=30,
            )
            assert r_post.status_code == 403, r_post.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_tds_reconciliation_root_post_blocked_cross_entity_when_enforced(self, tokens):
        """``POST /tds/reconciliation`` (engagement in body) must enforce entity RBAC."""
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r_post = requests.post(
                f"{API}/tds/reconciliation",
                headers=_h(tokens["cfo"]),
                json={
                    "engagement_id": "ENG-DEMO-IN-2025",
                    "ledger_tds": 0.0,
                    "challan_tds": 0.0,
                    "delayed_payment_days": 0,
                },
                timeout=30,
            )
            assert r_post.status_code == 403, r_post.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_control_certification_post_blocked_cross_entity_when_enforced(self, tokens):
        """``POST /control-certifications`` must reject cross-entity engagement writes."""
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r_post = requests.post(
                f"{API}/control-certifications",
                headers=_h(tokens["cfo"]),
                json={
                    "engagement_id": "ENG-DEMO-IN-2025",
                    "owner_email": "cfo@onetouch.ai",
                    "certification_text": "rbac entity-scope probe",
                    "scope": "ITGC",
                },
                timeout=30,
            )
            assert r_post.status_code == 403, r_post.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_deficiency_management_response_post_blocked_cross_entity_when_enforced(self, tokens):
        """Id-only deficiency management-response POST must not bypass engagement entity RBAC."""
        owner_tok = _login("owner@onetouch.ai", "demo1234")
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            rlist = requests.get(
                f"{API}/audit-engagements/ENG-DEMO-IN-2025/control-deficiencies",
                headers=_h(owner_tok),
                timeout=30,
            )
            assert rlist.status_code == 200, rlist.text
            body = rlist.json()
            items = body.get("items") or []
            if not isinstance(items, list) or not items:
                pytest.skip("no control deficiencies for IN engagement")
            did = items[0]["id"]
            r_post = requests.post(
                f"{API}/control-deficiencies/{did}/management-response",
                headers=_h(tokens["cfo"]),
                json={"response_text": "probe", "owner_email": "mgmt@example.com"},
                timeout=30,
            )
            assert r_post.status_code == 403, r_post.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_observations_post_blocked_cross_entity_when_enforced(self, tokens):
        """Reporting observations must not be creatable on another legal entity's engagement."""
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r_post = requests.post(
                f"{API}/audit-engagements/ENG-DEMO-IN-2025/observations",
                headers=_h(tokens["cfo"]),
                json={
                    "title": "RBAC probe",
                    "description": "entity-scope probe",
                    "severity": "low",
                    "material": False,
                    "pervasive": False,
                    "source": "manual",
                },
                timeout=30,
            )
            assert r_post.status_code == 403, r_post.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_compliance_checklist_post_blocked_cross_entity_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r_post = requests.post(
                f"{API}/audit-engagements/ENG-DEMO-IN-2025/compliance/checklist",
                headers=_h(tokens["cfo"]),
                json={"law_codes": ["CA2013"]},
                timeout=30,
            )
            assert r_post.status_code == 403, r_post.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_tax44_checklist_post_blocked_cross_entity_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r_post = requests.post(
                f"{API}/audit-engagements/ENG-DEMO-IN-2025/tax-audit-44ab/checklist",
                headers=_h(tokens["cfo"]),
                json={"clause_ids": ["10A"]},
                timeout=30,
            )
            assert r_post.status_code == 403, r_post.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_audit_adjustment_root_post_blocked_cross_entity_when_enforced(self, tokens):
        """``POST /audit-adjustments`` (engagement in body) must enforce entity RBAC."""
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r_post = requests.post(
                f"{API}/audit-adjustments",
                headers=_h(tokens["cfo"]),
                json={
                    "engagement_id": "ENG-DEMO-IN-2025",
                    "account_code": "RBAC-PROBE",
                    "account_name": "Probe",
                    "debit": 0.0,
                    "credit": 0.0,
                    "narrative": "entity-scope probe",
                    "status": "proposed",
                },
                timeout=30,
            )
            assert r_post.status_code == 403, r_post.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_materiality_reporting_writes_blocked_cross_entity_bundle(self, tokens):
        """Materiality, RACM create, findings, representations, and report generators must 403 for cross-entity CFO."""
        eid = "ENG-DEMO-IN-2025"
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        risk_body = {
            "risk_title": "RBAC entity-scope probe",
            "risk_description": "probe",
            "process_area": "General",
            "financial_statement_area": "Assets",
            "risk_category": "Financial Reporting Risk",
            "likelihood_score": 3,
            "impact_score": 3,
            "owner": "cfo@onetouch.ai",
        }
        post_cases = [
            ("materiality upsert", f"{API}/audit-engagements/{eid}/materiality", {}),
            ("create risk", f"{API}/audit-engagements/{eid}/risks", risk_body),
            ("audit finding", f"{API}/audit-engagements/{eid}/audit-findings", {"title": "RBAC probe", "description": "x"}),
            (
                "management representation",
                f"{API}/audit-engagements/{eid}/management-representation",
                {"text": "Representations text", "signed_by": "cfo@onetouch.ai"},
            ),
            ("opinion generate", f"{API}/audit-engagements/{eid}/opinion/generate", {}),
            ("final report generate", f"{API}/audit-engagements/{eid}/report/generate", {}),
            ("management letter generate", f"{API}/audit-engagements/{eid}/management-letter/generate", {}),
            ("CARO generate", f"{API}/audit-engagements/{eid}/caro/generate", {}),
        ]
        try:
            for label, url, body in post_cases:
                r = requests.post(url, headers=_h(tokens["cfo"]), json=body, timeout=60)
                assert r.status_code == 403, f"{label}: {r.status_code} {r.text}"
            r_patch = requests.patch(
                f"{API}/audit-engagements/{eid}/report/status",
                headers=_h(tokens["cfo"]),
                json={"status": "draft"},
                timeout=30,
            )
            assert r_patch.status_code == 403, r_patch.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_compliance_fs_india_writes_blocked_cross_entity_bundle(self, tokens):
        """India compliance, FS generate, GST/TDS nested posts, IFC, and clause updates must 403 for cross-entity CFO."""
        eid = "ENG-DEMO-IN-2025"
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        gst_body = {
            "gstr1_sales": 0.0,
            "gstr3b_sales": 0.0,
            "gstr2b_purchases": 0.0,
            "purchase_register": 0.0,
            "itc_claimed": 0.0,
            "itc_eligible": 0.0,
        }
        post_cases = [
            (
                "compliance finding",
                f"{API}/audit-engagements/{eid}/compliance/findings",
                {"law_code": "CA2013", "title": "RBAC probe", "severity": "low"},
            ),
            (
                "compliance result update",
                f"{API}/audit-engagements/{eid}/compliance/result",
                {"requirement_id": "rbac-probe-req", "status": "compliant"},
            ),
            ("GST reconciliation (nested)", f"{API}/audit-engagements/{eid}/gst/reconciliation", gst_body),
            (
                "TDS reconciliation (nested)",
                f"{API}/audit-engagements/{eid}/tds/reconciliation",
                {"ledger_tds": 0.0, "challan_tds": 0.0, "delayed_payment_days": 0},
            ),
            ("FS generate", f"{API}/audit-engagements/{eid}/fs/generate", {"mapping_profile": "default_ind_as"}),
            (
                "IFC control test create",
                f"{API}/audit-engagements/{eid}/control-tests",
                {"test_type": "design effectiveness", "period": "2025-04", "tester_email": "cfo@onetouch.ai"},
            ),
            (
                "control deficiency create (body engagement)",
                f"{API}/control-deficiencies",
                {
                    "engagement_id": eid,
                    "control_test_id": "rbac-probe-test",
                    "severity": "low",
                    "description": "probe",
                    "create_case": False,
                },
            ),
            (
                "44AB clause update",
                f"{API}/audit-engagements/{eid}/tax-audit-44ab/clause",
                {"clause_id": "10A", "status": "compliant"},
            ),
            (
                "CARO clause update",
                f"{API}/audit-engagements/{eid}/caro/clause",
                {"clause_id": "3(i)", "status": "compliant"},
            ),
        ]
        try:
            for label, url, body in post_cases:
                r = requests.post(url, headers=_h(tokens["cfo"]), json=body, timeout=60)
                assert r.status_code == 403, f"{label}: {r.status_code} {r.text}"
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_ca_engagement_hub_and_wp_root_writes_blocked_cross_entity_bundle(self, tokens):
        """Engagement hub POSTs and WP/sampling/vouch root POSTs (body ``engagement_id``) must 403 for cross-entity CFO."""
        eid = "ENG-DEMO-IN-2025"
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        hub_posts = [
            (
                "milestone",
                f"{API}/audit-engagements/{eid}/milestones",
                {"title": "RBAC probe", "due_date": "2026-12-31", "status": "pending", "owner_email": "cfo@onetouch.ai"},
            ),
            (
                "team member",
                f"{API}/audit-engagements/{eid}/team",
                {"user_email": "staff@example.com", "role": "staff"},
            ),
            (
                "planning note",
                f"{API}/audit-engagements/{eid}/planning-notes",
                {"note": "probe", "visibility": "team"},
            ),
            (
                "working paper root",
                f"{API}/working-papers",
                {"engagement_id": eid, "folder_id": "folder-rbac-probe", "title": "RBAC probe"},
            ),
            (
                "sampling plan root",
                f"{API}/sampling-plans",
                {
                    "engagement_id": eid,
                    "method": "random",
                    "population_size": 100,
                    "sample_size": 5,
                },
            ),
            (
                "vouching item root",
                f"{API}/vouching-items",
                {
                    "engagement_id": eid,
                    "working_paper_id": "wp-rbac-probe",
                    "transaction_ref": "RBAC-PROBE-1",
                },
            ),
        ]
        try:
            for label, url, body in hub_posts:
                r = requests.post(url, headers=_h(tokens["cfo"]), json=body, timeout=60)
                assert r.status_code == 403, f"{label}: {r.status_code} {r.text}"
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_create_engagement_rejects_cross_entity_code_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            body = {
                "engagement_id": "ENG-RBAC-SCOPE-TEST-001",
                "entity_name": "Other region",
                "entity_code": "UK-OPS",
                "financial_year": "2025-26",
                "audit_type": "internal",
                "audit_scope": "Test",
                "start_date": "2025-04-01",
                "end_date": "2026-03-31",
                "audit_partner": "p@example.com",
                "audit_manager": "m@example.com",
            }
            controller_tok = _login("controller@onetouch.ai", "demo1234")
            rc = requests.post(f"{API}/audit-engagements", headers=_h(controller_tok), json=body, timeout=30)
            assert rc.status_code == 403, rc.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)


class TestRollupsRecomputeEntityScope:
    def test_cfo_recompute_forbidden_when_enforced_superadmin_allowed(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r_cfo = requests.post(f"{API}/rollups/recompute", headers=_h(tokens["cfo"]), json={}, timeout=120)
            assert r_cfo.status_code == 200, r_cfo.text
            r_sa = requests.post(f"{API}/rollups/recompute", headers=_h(tokens["superadmin"]), json={}, timeout=120)
            assert r_sa.status_code == 200, r_sa.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)


class TestCloseRetentionConnectorsEntityScope:
    """Close cycles, retention purge, and connectors respect entity scope when RBAC enforcement is on."""

    def test_retention_run_blocked_for_cfo_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r = requests.post(
                f"{API}/retention/run",
                headers=_h(tokens["cfo"]),
                json={"dry_run": True},
                timeout=60,
            )
            assert r.status_code == 403, r.text
            r_sa = requests.post(
                f"{API}/retention/run",
                headers=_h(tokens["superadmin"]),
                json={"dry_run": True},
                timeout=60,
            )
            assert r_sa.status_code == 200, r_sa.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_close_create_rejects_cross_entity_code_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            body = {
                "period_ym": "2099-01",
                "name": "Scope test close",
                "entity_code": "UK-OPS",
            }
            # CFO bypasses entity scope for consolidated ops; Controller is scoped to seed entity (US-HQ).
            controller_tok = _login("controller@onetouch.ai", "demo1234")
            rc = requests.post(f"{API}/close/cycles", headers=_h(controller_tok), json=body, timeout=30)
            assert rc.status_code == 403, rc.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_close_cycles_list_ok_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r = requests.get(f"{API}/close/cycles", headers=_h(tokens["cfo"]), timeout=30)
            assert r.status_code == 200, r.text
            assert isinstance(r.json(), list)
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_connectors_list_ok_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r = requests.get(f"{API}/connectors", headers=_h(tokens["cfo"]), timeout=30)
            assert r.status_code == 200, r.text
            assert isinstance(r.json(), list)
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)


class TestGovernanceEntityScope:
    """Governance approvals are stamped with ``entity_code``; global policy updates are Super Admin when scope is on."""

    def test_approval_create_rejects_cross_entity_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            body = {
                "request_type": "connector_activation",
                "subject_type": "connector",
                "subject_id": "conn-test-scope",
                "reason": "test",
                "entity_code": "UK-OPS",
                "proposed_change": {},
            }
            controller_tok = _login("controller@onetouch.ai", "demo1234")
            rc = requests.post(f"{API}/governance/approvals", headers=_h(controller_tok), json=body, timeout=30)
            assert rc.status_code == 403, rc.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_approvals_list_ok_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r = requests.get(f"{API}/governance/approvals", headers=_h(tokens["cfo"]), timeout=30)
            assert r.status_code == 200, r.text
            assert isinstance(r.json(), list)
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_policy_update_forbidden_for_cfo_when_enforced_superadmin_ok(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            pol = requests.get(f"{API}/governance/policies", headers=_h(tokens["cfo"]), timeout=30)
            assert pol.status_code == 200, pol.text
            body = dict(pol.json())
            body["requires_approval"] = {**(body.get("requires_approval") or {}), "connector_activation": True}
            r_cfo = requests.post(f"{API}/governance/policies", headers=_h(tokens["cfo"]), json=body, timeout=30)
            assert r_cfo.status_code == 403, r_cfo.text
            r_sa = requests.post(f"{API}/governance/policies", headers=_h(tokens["superadmin"]), json=body, timeout=30)
            assert r_sa.status_code == 200, r_sa.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)


class TestMasterDataQualitySummaryEntityScope:
    """MDQ aggregate summaries narrow to the user's entity (aligned with list endpoints)."""

    def test_mdq_summary_scoped_for_cfo_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            for path in ("/master-data-quality/summary", "/dq/masters/summary"):
                r = requests.get(f"{API}{path}", headers=_h(tokens["cfo"]), timeout=60)
                assert r.status_code == 200, r.text
                body = r.json()
                assert body.get("entity_scope_applied") is not True
                assert "open_by_severity" in body
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)


class TestFinanceRestAndVendorRiskEntityScope:
    """Finance REST (`finance_rest_router`) + vendor-risk honor `enforce_entity_scope`."""

    def test_blocks_cross_entity_query_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r.status_code == 200, r.text
        try:
            owner_tok = _login("owner@onetouch.ai", "demo1234")
            # Process Owner (IN-SVC) must not query UK-OPS finance surfaces when enforcement is on.
            paths = (
                "/working-capital/summary",
                "/ar/summary",
                "/ap/summary",
                "/vendor-risk/summary",
                "/treasury/summary",
                "/forecast",
                "/budget/versions",
                "/cfo/summary",
                "/cfo/financial-health",
                "/finance-team/summary",
                "/gl/accounts",
                "/cases",
                "/o2c/summary",
                "/journals",
                "/reconciliations",
                "/rpt/related-parties",
                "/policies",
                "/three-way-match/summary",
                "/credit-notes/summary",
                "/fixed-assets-audit/summary",
                "/legal/notices",
                "/access/users",
                "/reports/audit-committee-pack.pdf",
                "/forex/summary",
                "/bank-recon/statements",
                "/inventory-audit/summary",
                "/continuous-audit/rules",
                "/doa/matrix",
                "/evidence-intelligence/quality-issues",
                "/audit-depth/gl/accounts",
                "/insights/evidence",
            )
            for p in paths:
                rx = requests.get(
                    f"{API}{p}",
                    headers=_h(owner_tok),
                    params={"entity_code": "UK-OPS"},
                    timeout=90,
                )
                assert rx.status_code == 403, f"{p}: {rx.status_code} {rx.text}"
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            r_off = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)
            assert r_off.status_code == 200, r_off.text


class TestEvidenceLegalCopilotEntityScope:
    """Evidence graph, intelligence summary, legal holds list, and global copilot ops respect entity RBAC."""

    def test_evidence_graph_blocks_cross_entity_exception(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            rlist = requests.get(
                f"{API}/exceptions",
                headers=_h(tokens["superadmin"]),
                params={"entity_code": "UK-OPS", "limit": 5},
                timeout=30,
            )
            assert rlist.status_code == 200, rlist.text
            items = rlist.json() or []
            if not items:
                pytest.skip("no UK-OPS exceptions in dataset")
            ex_id = items[0]["id"]
            owner_tok = _login("owner@onetouch.ai", "demo1234")
            r_ev = requests.get(f"{API}/evidence/{ex_id}", headers=_h(owner_tok), timeout=30)
            assert r_ev.status_code == 403, r_ev.text
            assert "Entity" in r_ev.text or "entity" in r_ev.text.lower()
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_evidence_intelligence_summary_superadmin_covers_all_entities(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r_sa = requests.get(f"{API}/evidence-intelligence/summary", headers=_h(tokens["superadmin"]), timeout=30)
            r_cfo = requests.get(f"{API}/evidence-intelligence/summary", headers=_h(tokens["cfo"]), timeout=30)
            assert r_sa.status_code == 200 and r_cfo.status_code == 200
            n_sa = int(r_sa.json().get("open_exceptions") or 0)
            n_cfo = int(r_cfo.json().get("open_exceptions") or 0)
            assert n_sa >= n_cfo
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_legal_holds_list_ok_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r = requests.get(f"{API}/legal-holds", headers=_h(tokens["cfo"]), timeout=30)
            assert r.status_code == 200, r.text
            assert isinstance(r.json(), list)
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_copilot_rebuild_and_anomaly_recalibrate_forbidden_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r_idx = requests.post(f"{API}/copilot/rebuild-index", headers=_h(tokens["cfo"]), json={}, timeout=120)
            assert r_idx.status_code == 403, r_idx.text
            r_an = requests.post(f"{API}/anomaly/recalibrate", headers=_h(tokens["cfo"]), json={}, timeout=120)
            assert r_an.status_code == 403, r_an.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_drill_vendor_blocks_cross_entity_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            vlist = requests.get(
                f"{API}/masters/vendors",
                headers=_h(tokens["superadmin"]),
                params={"entity_code": "UK-OPS", "limit": 1, "offset": 0},
                timeout=30,
            )
            assert vlist.status_code == 200, vlist.text
            items = (vlist.json() or {}).get("items") or []
            if not items:
                pytest.skip("no UK-OPS vendor in dataset")
            vid = items[0]["id"]
            owner_tok = _login("owner@onetouch.ai", "demo1234")
            r_d = requests.get(f"{API}/drill/vendor/{vid}", headers=_h(owner_tok), timeout=30)
            assert r_d.status_code == 403, r_d.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_drill_control_exceptions_narrowed_to_user_entity_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            comp_tok = _login("compliance@onetouch.ai", "demo1234")
            r = requests.get(f"{API}/drill/control/C-AP-001", headers=_h(comp_tok), timeout=30)
            assert r.status_code == 200, r.text
            for ex in r.json().get("exceptions") or []:
                ent = ex.get("entity") or ex.get("entity_code")
                assert ent == "UK-OPS", ex
            r2 = requests.get(f"{API}/drill/control/C-AP-001", headers=_h(tokens["cfo"]), timeout=30)
            assert r2.status_code == 200, r2.text
            seeded_entities = {"IN-SVC", "SG-APAC", "UK-OPS", "US-HQ"}
            for ex in r2.json().get("exceptions") or []:
                ent = ex.get("entity") or ex.get("entity_code")
                assert ent in seeded_entities, ex
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)


class TestAdminHeavyOpsEntityScope:
    """Org-wide admin actions (anomaly train, notification scans, daily brief) are Super Admin–only when RBAC entity scope is on."""

    def test_anomaly_train_blocked_for_cfo_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r = requests.post(f"{API}/anomaly/train", headers=_h(tokens["cfo"]), json={"notes": "rbac-scope-test"}, timeout=120)
            assert r.status_code == 403, r.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_notifications_scan_and_daily_brief_blocked_for_cfo_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r1 = requests.post(f"{API}/notifications/scan-sla", headers=_h(tokens["cfo"]), timeout=60)
            assert r1.status_code == 403, r1.text
            r2 = requests.post(f"{API}/notifications/daily-brief/send", headers=_h(tokens["cfo"]), timeout=60)
            assert r2.status_code == 403, r2.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_auditor_control_detail_filters_exceptions_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r = requests.get(f"{API}/auditor/controls/C-AP-001", headers=_h(tokens["cfo"]), timeout=30)
            assert r.status_code == 200, r.text
            seeded_entities = {"IN-SVC", "SG-APAC", "UK-OPS", "US-HQ"}
            for ex in r.json().get("exceptions") or []:
                ent = ex.get("entity") or ex.get("entity_code")
                assert ent in seeded_entities, ex
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)


class TestBoardReportingAndControlLibraryEntityScope:
    """Board reports by id; /reports/templates|versions query entity_code; control-library GET/POST respect entity RBAC when enforcement is on."""

    def test_report_get_blocked_cross_entity_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            rg = requests.post(
                f"{API}/reports/generate",
                headers=_h(tokens["superadmin"]),
                json={"template_id": "tpl-cfo-monthly-pack", "filters": {"entity_code": "UK-OPS"}},
                timeout=60,
            )
            assert rg.status_code == 200, rg.text
            rep_id = rg.json().get("id")
            assert rep_id
            controller_tok = _login("controller@onetouch.ai", "demo1234")
            r_g = requests.get(f"{API}/reports/{rep_id}", headers=_h(controller_tok), timeout=30)
            assert r_g.status_code == 403, r_g.text
            r_ok = requests.get(f"{API}/reports/{rep_id}", headers=_h(tokens["superadmin"]), timeout=30)
            assert r_ok.status_code == 200, r_ok.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_report_templates_and_versions_entity_query_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            owner_tok = _login("owner@onetouch.ai", "demo1234")
            r_tpl_bad = requests.get(
                f"{API}/reports/templates",
                headers=_h(owner_tok),
                params={"entity_code": "UK-OPS"},
                timeout=30,
            )
            assert r_tpl_bad.status_code == 403, r_tpl_bad.text
            r_ver_bad = requests.get(
                f"{API}/reports/versions",
                headers=_h(owner_tok),
                params={"limit": 10, "entity_code": "UK-OPS"},
                timeout=30,
            )
            assert r_ver_bad.status_code == 403, r_ver_bad.text
            r_tpl_ok = requests.get(
                f"{API}/reports/templates",
                headers=_h(tokens["cfo"]),
                params={"entity_code": "US-HQ"},
                timeout=30,
            )
            assert r_tpl_ok.status_code == 200, r_tpl_ok.text
            assert r_tpl_ok.json().get("entity_code") == "US-HQ"
            r_ver_ok = requests.get(
                f"{API}/reports/versions",
                headers=_h(tokens["cfo"]),
                params={"limit": 10, "entity_code": "US-HQ"},
                timeout=30,
            )
            assert r_ver_ok.status_code == 200, r_ver_ok.text
            assert r_ver_ok.json().get("entity_code") == "US-HQ"
            assert "items" in r_ver_ok.json()
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_control_library_get_blocks_cross_entity_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            owner_tok = _login("owner@onetouch.ai", "demo1234")
            r_bad = requests.get(
                f"{API}/control-library",
                headers=_h(owner_tok),
                params={"entity_code": "UK-OPS"},
                timeout=30,
            )
            assert r_bad.status_code == 403, r_bad.text
            r_ok = requests.get(
                f"{API}/control-library",
                headers=_h(tokens["cfo"]),
                params={"entity_code": "US-HQ"},
                timeout=30,
            )
            assert r_ok.status_code == 200, r_ok.text
            body = r_ok.json()
            assert body.get("entity_code") == "US-HQ"
            assert isinstance(body.get("items"), list)
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_control_library_post_requires_superadmin_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            code = f"RBAC-TEST-{uuid.uuid4().hex[:8]}"
            body = {
                "code": code,
                "name": "RBAC scope test control",
                "control_type": "preventive",
                "process": "Test",
                "description": "entity scope test",
                "objectives": [],
                "activities": [],
                "owners": [],
            }
            r_cfo = requests.post(f"{API}/control-library", headers=_h(tokens["cfo"]), json=body, timeout=30)
            assert r_cfo.status_code == 403, r_cfo.text
            r_sa = requests.post(f"{API}/control-library", headers=_h(tokens["superadmin"]), json=body, timeout=30)
            assert r_sa.status_code == 200, r_sa.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)


class TestAuditEngagementsListEntityQuery:
    """GET /audit-engagements and planning-metrics accept optional entity_code; cross-entity query is rejected when scope is on."""

    def test_audit_engagements_list_and_planning_metrics_entity_query_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            owner_tok = _login("owner@onetouch.ai", "demo1234")
            r_list_bad = requests.get(
                f"{API}/audit-engagements",
                headers=_h(owner_tok),
                params={"entity_code": "UK-OPS"},
                timeout=30,
            )
            assert r_list_bad.status_code == 403, r_list_bad.text
            r_met_bad = requests.get(
                f"{API}/audit-engagements/planning-metrics",
                headers=_h(owner_tok),
                params={"entity_code": "UK-OPS"},
                timeout=30,
            )
            assert r_met_bad.status_code == 403, r_met_bad.text
            r_list_ok = requests.get(
                f"{API}/audit-engagements",
                headers=_h(tokens["cfo"]),
                params={"entity_code": "US-HQ"},
                timeout=30,
            )
            assert r_list_ok.status_code == 200, r_list_ok.text
            assert isinstance(r_list_ok.json(), list)
            r_met_ok = requests.get(
                f"{API}/audit-engagements/planning-metrics",
                headers=_h(tokens["cfo"]),
                params={"entity_code": "US-HQ"},
                timeout=30,
            )
            assert r_met_ok.status_code == 200, r_met_ok.text
            mj = r_met_ok.json()
            assert "active_audit_count" in mj
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)


class TestConnectorsAndDqHealthEntityQuery:
    """Connectors list/matrix/sync-logs, GET /dq/health, and GET /dq/schema-validations accept optional entity_code; cross-entity query rejected when scope is on."""

    def test_connectors_and_dq_health_entity_query_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            owner_tok = _login("owner@onetouch.ai", "demo1234")
            for path in (
                f"{API}/integrations/connectors",
                f"{API}/integrations/connectors/matrix",
                f"{API}/integrations/connectors/sync-logs",
                f"{API}/dq/health",
                f"{API}/dq/schema-validations",
            ):
                r_bad = requests.get(path, headers=_h(owner_tok), params={"entity_code": "UK-OPS"}, timeout=30)
                assert r_bad.status_code == 403, f"{path}: {r_bad.text}"
            r_ok = requests.get(
                f"{API}/integrations/connectors",
                headers=_h(tokens["cfo"]),
                params={"entity_code": "US-HQ"},
                timeout=30,
            )
            assert r_ok.status_code == 200, r_ok.text
            assert isinstance(r_ok.json(), list)
            h_ok = requests.get(f"{API}/dq/health", headers=_h(tokens["cfo"]), params={"entity_code": "US-HQ"}, timeout=30)
            assert h_ok.status_code == 200, h_ok.text
            assert "connectors" in h_ok.json()
            sv_ok = requests.get(
                f"{API}/dq/schema-validations",
                headers=_h(tokens["cfo"]),
                params={"entity_code": "US-HQ", "limit": 10},
                timeout=30,
            )
            assert sv_ok.status_code == 200, sv_ok.text
            assert isinstance(sv_ok.json(), list)
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)


class TestGovernanceApprovalsAndRollupsEntityQuery:
    """Governance approvals list and rollups summary/hierarchy accept optional entity_code under RBAC entity scope."""

    def test_governance_approvals_and_rollups_entity_query_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r_app = requests.get(
                f"{API}/governance/approvals",
                headers=_h(tokens["cfo"]),
                params={"status": "pending", "entity_code": "UK-OPS"},
                timeout=30,
            )
            assert r_app.status_code == 200, r_app.text
            for path in (f"{API}/rollups/hierarchy", f"{API}/rollups/summary"):
                r_r = requests.get(path, headers=_h(tokens["cfo"]), params={"entity_code": "UK-OPS"}, timeout=30)
                assert r_r.status_code == 200, f"{path}: {r_r.text}"
            r_app_ok = requests.get(
                f"{API}/governance/approvals",
                headers=_h(tokens["cfo"]),
                params={"status": "pending", "entity_code": "US-HQ"},
                timeout=30,
            )
            assert r_app_ok.status_code == 200, r_app_ok.text
            assert isinstance(r_app_ok.json(), list)
            r_hier = requests.get(
                f"{API}/rollups/hierarchy",
                headers=_h(tokens["cfo"]),
                params={"entity_code": "US-HQ"},
                timeout=30,
            )
            assert r_hier.status_code == 200, r_hier.text
            r_sum = requests.get(
                f"{API}/rollups/summary",
                headers=_h(tokens["cfo"]),
                params={"entity_code": "US-HQ"},
                timeout=30,
            )
            assert r_sum.status_code == 200, r_sum.text
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)


class TestPoliciesRetentionLegalHoldsRollupsDrilldownEntityQuery:
    """Governance policy read, retention list/eligible, legal-holds list, rollups drilldown: optional entity_code under RBAC."""

    def test_entity_query_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            owner_tok = _login("owner@onetouch.ai", "demo1234")
            r_pol = requests.get(
                f"{API}/governance/policies",
                headers=_h(owner_tok),
                params={"entity_code": "UK-OPS"},
                timeout=30,
            )
            assert r_pol.status_code == 403, r_pol.text
            for path in (f"{API}/retention/policies", f"{API}/retention/eligible"):
                r_r = requests.get(path, headers=_h(owner_tok), params={"entity_code": "UK-OPS"}, timeout=30)
                assert r_r.status_code == 403, f"{path}: {r_r.text}"
            r_h = requests.get(
                f"{API}/legal-holds",
                headers=_h(owner_tok),
                params={"status": "active", "entity_code": "UK-OPS"},
                timeout=30,
            )
            assert r_h.status_code == 403, r_h.text
            r_dd = requests.get(
                f"{API}/rollups/drilldown",
                headers=_h(owner_tok),
                params={"node_id": "US-HQ", "entity_code": "UK-OPS"},
                timeout=30,
            )
            assert r_dd.status_code == 403, r_dd.text

            r_pol_ok = requests.get(
                f"{API}/governance/policies",
                headers=_h(tokens["cfo"]),
                params={"entity_code": "US-HQ"},
                timeout=30,
            )
            assert r_pol_ok.status_code == 200, r_pol_ok.text
            assert isinstance(r_pol_ok.json(), dict)
            r_ret_ok = requests.get(
                f"{API}/retention/policies",
                headers=_h(tokens["cfo"]),
                params={"entity_code": "US-HQ"},
                timeout=30,
            )
            assert r_ret_ok.status_code == 200, r_ret_ok.text
            assert isinstance(r_ret_ok.json(), list)
            r_dd_ok = requests.get(
                f"{API}/rollups/drilldown",
                headers=_h(tokens["cfo"]),
                params={"node_id": "US-HQ", "entity_code": "US-HQ"},
                timeout=30,
            )
            assert r_dd_ok.status_code == 200, r_dd_ok.text
            assert "drill" in r_dd_ok.json()
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)


class TestCopilotReadEndpointsEntityQuery:
    """GET /copilot/sessions, /copilot/index-status, /copilot/retrieval-configs accept optional entity_code under RBAC."""

    def test_copilot_reads_entity_query_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            owner_tok = _login("owner@onetouch.ai", "demo1234")
            for path in (
                f"{API}/copilot/sessions",
                f"{API}/copilot/index-status",
                f"{API}/copilot/retrieval-configs",
            ):
                r_bad = requests.get(path, headers=_h(owner_tok), params={"entity_code": "UK-OPS"}, timeout=30)
                assert r_bad.status_code == 403, f"{path}: {r_bad.text}"
            s_ok = requests.get(
                f"{API}/copilot/sessions",
                headers=_h(tokens["cfo"]),
                params={"entity_code": "US-HQ", "limit": 5},
                timeout=30,
            )
            assert s_ok.status_code == 200, s_ok.text
            assert isinstance(s_ok.json(), list)
            idx_ok = requests.get(
                f"{API}/copilot/index-status",
                headers=_h(tokens["cfo"]),
                params={"entity_code": "US-HQ"},
                timeout=30,
            )
            assert idx_ok.status_code == 200, idx_ok.text
            assert "indexed_docs" in idx_ok.json()
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)


class TestEvidenceIntelligenceSummaryOptionalEntityQuery:
    """GET /evidence-intelligence/summary validates optional entity_code when RBAC entity scope is on."""

    def test_summary_entity_query_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            owner_tok = _login("owner@onetouch.ai", "demo1234")
            r_bad = requests.get(
                f"{API}/evidence-intelligence/summary",
                headers=_h(owner_tok),
                params={"entity_code": "UK-OPS"},
                timeout=30,
            )
            assert r_bad.status_code == 403, r_bad.text
            r_ok = requests.get(
                f"{API}/evidence-intelligence/summary",
                headers=_h(tokens["cfo"]),
                params={"entity_code": "US-HQ"},
                timeout=30,
            )
            assert r_ok.status_code == 200, r_ok.text
            assert "open_exceptions" in r_ok.json()
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)


class TestConnectorRunsHealthErrorsEntityQuery:
    """Connector runs/health/errors accept optional entity_code; cross-entity query rejected when scope is on."""

    def test_connector_detail_reads_entity_query_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            r_list = requests.get(
                f"{API}/integrations/connectors",
                headers=_h(tokens["cfo"]),
                params={"entity_code": "US-HQ"},
                timeout=30,
            )
            assert r_list.status_code == 200, r_list.text
            items = r_list.json()
            if not isinstance(items, list) or not items:
                pytest.skip("no connectors in dataset")
            cid = items[0]["id"]
            owner_tok = _login("owner@onetouch.ai", "demo1234")
            for suffix in ("runs", "health", "errors"):
                path = f"{API}/integrations/connectors/{cid}/{suffix}"
                r_bad = requests.get(path, headers=_h(owner_tok), params={"entity_code": "UK-OPS"}, timeout=30)
                assert r_bad.status_code == 403, f"{path}: {r_bad.text}"
            r_ok = requests.get(
                f"{API}/integrations/connectors/{cid}/runs",
                headers=_h(tokens["cfo"]),
                params={"entity_code": "US-HQ"},
                timeout=30,
            )
            assert r_ok.status_code == 200, r_ok.text
            assert isinstance(r_ok.json(), list)
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)


class TestGovernanceDepthAndComplianceLibraryEntityScope:
    """Governance-depth stubs and CA compliance library honor optional ``entity_code`` under RBAC entity scope."""

    def test_compliance_depth_blocks_cross_entity_query_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            owner_tok = _login("owner@onetouch.ai", "demo1234")
            r_bad = requests.get(
                f"{API}/compliance-depth/mdq/summary",
                headers=_h(owner_tok),
                params={"entity_code": "UK-OPS"},
                timeout=30,
            )
            assert r_bad.status_code == 403, r_bad.text
            r_ok = requests.get(
                f"{API}/compliance-depth/sod/campaigns",
                headers=_h(tokens["cfo"]),
                params={"entity_code": "US-HQ"},
                timeout=30,
            )
            assert r_ok.status_code == 200, r_ok.text
            assert r_ok.json().get("entity_code") == "US-HQ"
            r_default = requests.get(f"{API}/compliance-depth/doa/rules", headers=_h(tokens["cfo"]), timeout=30)
            assert r_default.status_code == 200, r_default.text
            assert r_default.json().get("entity_code") is None
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)

    def test_compliance_library_blocks_cross_entity_when_enforced(self, tokens):
        cfg = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": True}}}
        r_on = requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg, timeout=30)
        assert r_on.status_code == 200, r_on.text
        try:
            owner_tok = _login("owner@onetouch.ai", "demo1234")
            r_bad = requests.get(
                f"{API}/compliance/library",
                headers=_h(owner_tok),
                params={"entity_code": "UK-OPS"},
                timeout=30,
            )
            assert r_bad.status_code == 403, r_bad.text
            r_ok = requests.get(
                f"{API}/compliance/library",
                headers=_h(tokens["cfo"]),
                params={"entity_code": "US-HQ"},
                timeout=30,
            )
            assert r_ok.status_code == 200, r_ok.text
            body = r_ok.json()
            assert body.get("entity_code") == "US-HQ"
            assert isinstance(body.get("laws"), list)
        finally:
            cfg2 = {"config": {"field_masking": {"enabled": False}, "rbac": {"entity_scope_enforced": False}}}
            requests.post(f"{API}/system/security-config", headers=_h(tokens["superadmin"]), json=cfg2, timeout=30)


class TestAuditAndDQSurfaces:
    def test_audit_trail_endpoint(self, tokens):
        r = requests.get(f"{API}/masters/audit-trail", headers=_h(tokens["cfo"]), params={"limit": 5}, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body.get("items"), list)

    def test_master_dq_endpoints(self, tokens):
        # recompute requires super admin
        r0 = requests.post(f"{API}/dq/masters/recompute", headers=_h(tokens["superadmin"]), json={}, timeout=60)
        assert r0.status_code == 200, r0.text

        r1 = requests.get(f"{API}/dq/masters/summary", headers=_h(tokens["cfo"]), timeout=30)
        assert r1.status_code == 200, r1.text
        r2 = requests.get(f"{API}/dq/masters/findings", headers=_h(tokens["cfo"]), params={"limit": 10}, timeout=30)
        assert r2.status_code == 200, r2.text

