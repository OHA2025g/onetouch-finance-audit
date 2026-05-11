"""L4 contract tests for Phase 34 — Evidence OCR & Document intelligence (HTTP)."""

from __future__ import annotations

import os
import time

import pytest
import requests


from l4_http_common import resolve_react_app_backend_url, wait_until_api_ready


BASE_URL = resolve_react_app_backend_url()
assert BASE_URL, (
    "Set REACT_APP_BACKEND_URL to the API root (e.g. http://127.0.0.1:8000), or define it in "
    "apps/frontend/.env for local pytest."
)
API = f"{BASE_URL.rstrip('/')}/api"


def _wait_api(timeout_s: float = 60.0) -> None:
    wait_until_api_ready(API, timeout_s=timeout_s)


def _login(email: str, password: str) -> str:
    _wait_api()
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def token() -> str:
    return _login("controller@onetouch.ai", "demo1234")


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


class TestEvidenceIntelligenceContracts:
    def test_phase34_extract_get_link_review(self, token):
        ex = requests.post(
            f"{API}/evidence-intelligence/extract",
            headers=_h(token),
            json={"document_name": "Invoice sample", "document_type": "invoice", "text": "Invoice# INV-778 Vendor Acme Amount 125000", "entity": "US-HQ"},
            timeout=60,
        )
        assert ex.status_code == 200, ex.text
        doc_id = ex.json().get("document_id")
        assert doc_id

        g = requests.get(f"{API}/evidence-intelligence/{doc_id}", headers=_h(token), timeout=60)
        assert g.status_code == 200, g.text
        assert g.json().get("found") is True

        # Link to an existing exception
        lst = requests.get(f"{API}/exceptions?limit=1", headers=_h(token), timeout=60)
        assert lst.status_code == 200, lst.text
        eid = (lst.json() or [])[0]["id"]
        lk = requests.post(
            f"{API}/evidence-intelligence/{doc_id}/link",
            headers=_h(token),
            json={"target_type": "exception", "target_id": eid, "note": "QA link"},
            timeout=60,
        )
        assert lk.status_code == 200, lk.text

        qi = requests.get(f"{API}/evidence-intelligence/quality-issues", headers=_h(token), timeout=60)
        assert qi.status_code == 200, qi.text
        assert "items" in qi.json()

        rv = requests.post(
            f"{API}/evidence-intelligence/{doc_id}/review",
            headers=_h(token),
            json={"decision": "accepted", "note": "QA accept"},
            timeout=60,
        )
        assert rv.status_code == 200, rv.text
        assert rv.json().get("status") == "ok"

