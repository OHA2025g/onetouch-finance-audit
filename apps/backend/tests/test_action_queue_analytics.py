"""Unit tests for CFO action queue analytics."""

from __future__ import annotations

from app.services.action_queue_analytics_service import _compute_summary
from app.services.action_queue_service import (
    _materiality_score,
    decode_cursor,
    encode_cursor,
    is_sla_breached,
    scope_filters,
)


def test_scope_filters_entity():
    q = scope_filters(entity_code="US-HQ", status="open")
    assert q["entity"] == "US-HQ"
    assert q["status"] == "open"


def test_materiality_score_ordering():
    assert _materiality_score("P0", 1_000_000) > _materiality_score("P2", 1_000_000)


def test_compute_summary_open_counts():
    items = [
        {
            "status": "open",
            "priority": "P0",
            "type": "exception_highrisk",
            "created_at": "2026-01-01T00:00:00+00:00",
            "age_days": 5,
            "detail": {"exposure": 100_000},
            "events": [],
        },
        {
            "status": "approved",
            "priority": "P1",
            "type": "case_overdue",
            "created_at": "2026-01-02T00:00:00+00:00",
            "detail": {},
            "events": [{"type": "approved", "note": "ok", "at": "2026-01-03T00:00:00+00:00"}],
        },
    ]
    s = _compute_summary(items, items)
    assert s["open_total"] == 1
    assert s["p0_open"] == 1
    assert s["queue_exposure_usd"] == 100_000.0
    assert "aging_buckets" in s


def test_is_sla_breached_p0_one_day():
    assert is_sla_breached({"priority": "P0"}, 1.5) is True
    assert is_sla_breached({"priority": "P0"}, 0.5) is False


def test_export_xlsx_bytes_header():
    from app.services.action_queue_service import export_xlsx_bytes

    data = export_xlsx_bytes(
        [
            {
                "id": "aq-1",
                "type": "case_overdue",
                "status": "open",
                "priority": "P1",
                "title": "Test",
                "entity": "US-HQ",
                "process": "P2P",
                "age_days": 2,
                "materiality_score": 80,
                "sla_breached": False,
                "detail": {"exposure": 1000},
            }
        ]
    )
    assert data[:2] == b"PK"


def test_cursor_roundtrip():
    payload = {"id": "aq-test-1", "score": 99.5, "materiality_score": 80}
    token = encode_cursor(payload)
    assert decode_cursor(token) == payload
    assert decode_cursor("not-valid!!!") is None


def test_compute_summary_exposure_by_process():
    items = [
        {
            "status": "open",
            "priority": "P1",
            "process": "Procure-to-Pay",
            "detail": {"exposure": 50_000},
            "events": [],
        },
        {
            "status": "open",
            "priority": "P2",
            "process": "Treasury",
            "detail": {"exposure": 30_000},
            "events": [],
        },
    ]
    s = _compute_summary(items, items)
    rows = s.get("exposure_by_process") or []
    assert len(rows) >= 2
    assert rows[0]["exposure"] >= rows[-1]["exposure"]
