"""Schedule audit service (no DB)."""
from __future__ import annotations

from app.services.ca_schedule_audit import augment_schedule_for_api, build_demo_payload, compute_exception_flags


def test_build_demo_assets_keys() -> None:
    p = build_demo_payload("assets")
    assert "asset_register" in p
    assert "depreciation_recalculation" in p
    assert p["depreciation_recalculation"]["variance"] != 0


def test_exception_flags_legacy_revenue() -> None:
    legacy = {
        "recognition_checks": [{"id": "R-1", "status": "review", "note": "x"}],
        "cutoff": [{"near_period_end": True, "amount": 1}],
        "customer_wise": [{"customer": "A", "amount": 1, "pct": 0.25}],
        "credit_notes": [{"id": "CN", "amount": 200_000}],
    }
    flags = compute_exception_flags("revenue", legacy)
    assert flags.get("recognition_review") is True


def test_augment_adds_procedures() -> None:
    doc = {
        "id": "1",
        "engagement_id": "E1",
        "schedule_type": "inventory",
        "payload": build_demo_payload("inventory"),
        "exceptions": [],
    }
    out = augment_schedule_for_api(doc)
    assert len(out["audit_procedures"]) >= 4
    assert out["exception_flags"].get("gl_variance") is True
