"""IFC heatmap helper (no DB)."""
from __future__ import annotations

from app.services.ca_ifc_service import build_ifc_heatmap, effectiveness_from_test_row, enrich_library_item


def test_effectiveness_mapping() -> None:
    assert effectiveness_from_test_row({"result": "deficient"}) == "ineffective"
    assert effectiveness_from_test_row({"effectiveness_score": "partially_effective"}) == "partially_effective"


def test_heatmap_counts_by_process() -> None:
    lib = [
        {"id": "L1", "code": "C1", "process": "O2C", "name": "n1", "control_type": "preventive", "description": "d"},
    ]
    tests = [
        {"id": "T1", "control_library_id": "L1", "test_type": "design effectiveness", "period": "FY25", "tester_email": "a@b.c", "effectiveness_score": "effective"},
        {"id": "T2", "control_library_id": "L1", "test_type": "operating effectiveness", "period": "FY25", "tester_email": "a@b.c", "result": "pending"},
    ]
    h = build_ifc_heatmap(tests, lib)
    assert "O2C" in h["matrix"]
    assert h["matrix"]["O2C"]["effective"] == 1
    assert h["matrix"]["O2C"]["pending"] == 1


def test_enrich_library() -> None:
    row = enrich_library_item({"id": "x", "code": "Z", "name": "n", "control_type": "manual", "process": "p", "description": "d"})
    assert row["objectives"]
    assert row["activities"]
    assert row["owners"]
