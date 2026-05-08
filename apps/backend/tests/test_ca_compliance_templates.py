"""India compliance template rows (no DB)."""
from __future__ import annotations

from app.services.ca_compliance_templates import compliance_rows_for_laws


def test_compliance_rows_default_laws_when_empty() -> None:
    rows = compliance_rows_for_laws([])
    codes = {r["law_code"] for r in rows}
    assert "CA2013" in codes
    assert "GST" in codes
    assert all(r.get("id") for r in rows)
    assert all(r.get("status") == "pending evidence" for r in rows)


def test_compliance_rows_filtered() -> None:
    rows = compliance_rows_for_laws(["GST", "TDS"])
    assert all(r["law_code"] in ("GST", "TDS") for r in rows)
    assert len(rows) >= 1
