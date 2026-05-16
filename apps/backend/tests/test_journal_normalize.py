"""Unit tests for journal normalization and risk scoring on ERP-shaped rows."""

from __future__ import annotations

import os

os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:27017")
os.environ.setdefault("DB_NAME", "onetouch_test")
os.environ.setdefault("JWT_SECRET", "test-secret")

from app.connectors.adapters._normalize import normalize_journal
from app.routers.journals_router import DEFAULT_RULES, _build_risk_summary, _scored_journal


def test_normalize_journal_maps_amount_and_flags():
    raw = {
        "id": "JRN-SAP-1",
        "journal_number": "SAP-JRN-1",
        "amount": 125_000.0,
        "created_by": "gl.lead@onetouch.ai",
        "source_system": "SAP-MOCK",
        "posting_date": "2026-05-01T00:00:00+00:00",
        "created_at": "2026-05-01T00:00:00+00:00",
    }
    norm = normalize_journal(raw)
    assert norm["total_amount"] == 125_000.0
    assert norm["is_manual"] is True
    assert norm["is_privileged_poster"] is True


def test_sap_shaped_journal_scores_non_zero():
    sap_row = {
        "id": "JRN-x",
        "journal_number": "SAP-JRN-2",
        "entity": "IN-HQ",
        "amount": 85_000.0,
        "created_by": "gl.lead@onetouch.ai",
        "approver_email": None,
        "posting_date": "2026-04-01T00:00:00+00:00",
        "created_at": "2026-05-14T00:00:00+00:00",
        "source_system": "SAP-MOCK",
    }
    scored = _scored_journal(sap_row, DEFAULT_RULES)
    assert scored["total_amount"] == 85_000.0
    assert scored["risk_score"] > 0
    assert scored["risk_band"] in ("low", "medium", "high")
    rule_ids = {h["rule_id"] for h in scored["hits"]}
    assert "JR-002" in rule_ids  # backdated
    assert "JR-003" in rule_ids  # privileged poster
    assert "JR-004" in rule_ids  # missing approver on manual


def test_build_risk_summary_aggregates_bands_and_rules():
    scored = [
        _scored_journal(
            {
                "id": "a",
                "total_amount": 200_000,
                "is_manual": True,
                "created_by": "gl.lead@onetouch.ai",
                "approver_email": None,
                "posting_date": "2026-04-01T00:00:00+00:00",
                "created_at": "2026-05-14T00:00:00+00:00",
                "source_system": "SAP-MOCK",
            },
            DEFAULT_RULES,
        ),
        _scored_journal(
            {
                "id": "b",
                "total_amount": 10_000,
                "is_manual": False,
                "created_by": "ap.clerk@onetouch.ai",
                "posting_date": "2026-05-10T00:00:00+00:00",
                "created_at": "2026-05-10T00:00:00+00:00",
            },
            DEFAULT_RULES,
        ),
    ]
    summary = _build_risk_summary(scored, total=100, rules=DEFAULT_RULES, reviewed_ids=set())
    assert summary["kpis"]["high_count"] >= 1
    assert summary["kpis"]["scanned"] == 2
    assert summary["kpis"]["total_journals"] == 100
    assert any(r["hit_count"] > 0 for r in summary["rule_hits"])
