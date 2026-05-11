"""Reconciliation detail + drill/evidence access for non-CFO roles (cross-role drill-down)."""
import pytest
import requests

from l4_http_common import resolve_react_app_backend_url

BASE_URL = (resolve_react_app_backend_url() or "").rstrip("/")
assert BASE_URL, "Set REACT_APP_BACKEND_URL or apps/frontend/.env for HTTP tests."
API = f"{BASE_URL}/api"

CREDS = {
    "controller": ("controller@onetouch.ai", "demo1234"),
    "compliance": ("compliance@onetouch.ai", "demo1234"),
    "auditor": ("auditor@onetouch.ai", "demo1234"),
}


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def role_tokens():
    out = {}
    for role, (email, pwd) in CREDS.items():
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=30)
        assert r.status_code == 200, f"login {email}: {r.text}"
        out[role] = r.json()["token"]
    return out


@pytest.fixture(scope="module")
def cfo_token():
    r = requests.post(f"{API}/auth/login", json={"email": "cfo@onetouch.ai", "password": "demo1234"}, timeout=30)
    assert r.status_code == 200
    return r.json()["token"]


def test_reconciliation_detail_returns_shape(cfo_token):
    dash = requests.get(f"{API}/dashboard/controller", headers=_hdr(cfo_token), timeout=30).json()
    assert dash.get("reconciliations"), "seed should include reconciliations"
    rid = dash["reconciliations"][0]["id"]
    r = requests.get(f"{API}/reconciliations/{rid}", headers=_hdr(cfo_token), timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["reconciliation"]["id"] == rid
    assert "related_journal" in body


def test_reconciliation_detail_404(cfo_token):
    r = requests.get(f"{API}/reconciliations/REC-DOES-NOT-EXIST-99999", headers=_hdr(cfo_token), timeout=30)
    assert r.status_code == 404


@pytest.mark.parametrize("role", ("controller", "compliance", "auditor"))
def test_drill_control_accessible(role_tokens, role):
    tok = role_tokens[role]
    r = requests.get(f"{API}/drill/control/C-AP-001", headers=_hdr(tok), timeout=30)
    assert r.status_code == 200, f"{role}: {r.status_code} {r.text[:240]}"


@pytest.mark.parametrize("role", ("controller", "compliance", "auditor"))
def test_evidence_graph_accessible(role_tokens, role):
    tok = role_tokens[role]
    ex = requests.get(f"{API}/exceptions?limit=1", headers=_hdr(tok), timeout=30).json()
    assert isinstance(ex, list) and ex, "need at least one exception"
    eid = ex[0]["id"]
    r = requests.get(f"{API}/evidence/{eid}", headers=_hdr(tok), timeout=30)
    assert r.status_code == 200, f"{role}: evidence/{eid} → {r.status_code}"
