"""Unit tests for KPI snapshot service."""

from __future__ import annotations

import os

os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:27017")
os.environ.setdefault("DB_NAME", "onetouch_test")

from app.services.kpi_snapshot_service import _compute_delta, scope_key


def test_scope_key_stable():
    assert scope_key(entity_code="US-HQ", period_ym="2026-04") == "entity=US-HQ|period=2026-04|dept=|cc=|process="


def test_compute_delta_pct():
    d = _compute_delta(82.0, 78.0, "pct")
    assert d["delta_direction"] == "up"
    assert d["delta_pct"] == 4.0


def test_compute_delta_usd_down():
    d = _compute_delta(1_000_000, 1_200_000, "usd")
    assert d["delta_direction"] == "down"
    assert d["delta_abs"] == -200_000
