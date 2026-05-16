"""Unit tests for bank reconciliation service."""

from __future__ import annotations

import os

os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:27017")
os.environ.setdefault("DB_NAME", "onetouch_test")

from app.services.bank_recon_service import (
    apply_classifications,
    count_line_buckets,
    match_line_item,
    parse_csv_statement,
)


def test_parse_csv_statement():
    csv_text = "date,amount,direction,reference\n2026-04-01,5000,outbound,WIRE-1\n"
    items = parse_csv_statement(csv_text)
    assert len(items) == 1
    assert items[0]["reference"] == "WIRE-1"
    assert items[0]["amount"] == 5000.0


def test_match_payment_reference():
    item = {"reference": "WIRE-90001", "amount": 100.0}
    pay = {"WIRE-90001": {"id": "PAY-1", "bank_reference": "WIRE-90001", "amount": 100.0}}
    out = match_line_item(item, pay_by_ref=pay, bt_by_ref={})
    assert out["match_status"] == "matched"
    assert out["book_match"]["type"] == "payment"


def test_classify_reduces_unmatched():
    import asyncio

    items = [{"reference": "CARD-1", "amount": 50, "match_status": "unmatched"}]
    updated = asyncio.run(apply_classifications(items, [{"reference": "CARD-1", "classification": "bank_fee"}]))
    counts = count_line_buckets(updated)
    assert counts["classified_count"] == 1
    assert counts["unmatched_count"] == 0
