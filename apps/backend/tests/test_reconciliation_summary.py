"""Unit tests for reconciliation enrichment and summary KPIs."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:27017")
os.environ.setdefault("DB_NAME", "onetouch_test")

from app.services.reconciliation_metrics import (
    build_reconciliation_summary,
    days_to_approve,
    enrich_reconciliation,
    outside_tolerance,
)


def test_outside_tolerance():
    assert outside_tolerance({"variance_amount": 6000, "tolerance": 5000}) is True
    assert outside_tolerance({"variance_amount": 100, "tolerance": 5000}) is False


def test_enrich_flags_overdue_and_workflow():
    past = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    rec = {
        "id": "r1",
        "status": "open",
        "due_date": past,
        "variance_amount": 9000,
        "tolerance": 5000,
        "evidence": [],
    }
    out = enrich_reconciliation(rec)
    assert out["workflow_status"] == "open"
    assert out["is_overdue"] is True
    assert out["outside_tolerance"] is True
    assert out["has_evidence"] is False


def test_days_to_approve():
    assert days_to_approve({"submitted_at": "2026-01-01T00:00:00+00:00", "approved_at": "2026-01-04T00:00:00+00:00"}) == 3.0


def test_build_summary_kpis_and_breakdowns():
    items = [
        {
            "id": "r1",
            "entity": "US-HQ",
            "status": "open",
            "variance_amount": 100,
            "tolerance": 5000,
            "reconciliation_type": "Bank",
            "evidence": [],
        },
        {
            "id": "r2",
            "entity": "EU-01",
            "status": "approved",
            "variance_amount": 8000,
            "tolerance": 5000,
            "reconciliation_type": "GL",
            "evidence": [{"id": "e1"}],
            "submitted_at": "2026-01-01T00:00:00+00:00",
            "approved_at": "2026-01-03T00:00:00+00:00",
        },
        {
            "id": "r3",
            "entity": "US-HQ",
            "status": "approved",
            "variance_amount": 50,
            "tolerance": 5000,
            "reconciliation_type": "Bank",
            "evidence": [{"id": "e2"}],
            "case_id": "case-rec-abc",
        },
    ]
    enriched = [enrich_reconciliation(r) for r in items]
    summary = build_reconciliation_summary(
        enriched,
        total=10,
        case_stats={"escalated_total": 2, "open_linked_cases": 1, "recons_with_open_case": 1},
    )
    k = summary["kpis"]
    assert k["total_reconciliations"] == 10
    assert k["outside_tolerance_count"] == 1
    assert k["avg_days_to_approve"] == 2.0
    assert k["escalated_to_case_count"] == 2
    assert k["open_linked_cases_count"] == 1
    assert len(summary["by_type"]) == 2
    assert summary["by_type"][0]["abs_variance"] > 0
    assert len(summary["by_entity"]) >= 2
    assert len(summary["top_entities_by_variance"]) >= 1
