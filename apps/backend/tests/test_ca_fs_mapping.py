"""FS mapping from trial balance (no DB)."""
from __future__ import annotations

from app.services.ca_fs_mapping import (
    build_financial_statement_mappings,
    classify_account,
    net_amount,
)


def test_classify_assets_and_revenue() -> None:
    b, _rule = classify_account("1100", "Cash on hand")
    assert b == "assets"
    b2, _ = classify_account("4100", "Sales revenue")
    assert b2 == "revenue"


def test_mappings_net_amount() -> None:
    lines = [
        {"id": "a1", "account_code": "1000", "account_name": "Cash", "debit": 1000, "credit": 0},
        {"id": "a2", "account_code": "2000", "account_name": "Payables", "debit": 0, "credit": 1000},
    ]
    maps = build_financial_statement_mappings(lines)
    assert len(maps) == 2
    by_code = {m["account_code"]: m for m in maps}
    assert by_code["1000"]["mapped_bucket"] == "assets"
    assert by_code["2000"]["mapped_bucket"] == "liabilities"
    assert net_amount(lines[0]) == 1000.0
