"""Bank reconciliation automation — matching, enrichment, summary, CSV ingest."""

from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Optional, Tuple

from motor.motor_asyncio import AsyncIOMotorDatabase


AMOUNT_TOLERANCE = 0.01


def parse_csv_statement(text: str) -> List[Dict[str, Any]]:
    """Parse CSV with headers: date, amount, direction, reference (aliases supported)."""
    reader = csv.DictReader(io.StringIO(text.strip()))
    items: List[Dict[str, Any]] = []
    for row in reader:
        if not any((row.get(k) or "").strip() for k in row):
            continue
        date_val = (
            row.get("date")
            or row.get("txn_date")
            or row.get("transaction_date")
            or row.get("posting_date")
            or ""
        )
        ref = row.get("reference") or row.get("bank_reference") or row.get("ref") or ""
        direction = (row.get("direction") or row.get("type") or "outbound").strip().lower()
        try:
            amount = float(str(row.get("amount") or "0").replace(",", ""))
        except ValueError:
            amount = 0.0
        items.append(
            {
                "date": date_val,
                "amount": amount,
                "direction": direction if direction in ("inbound", "outbound") else "outbound",
                "reference": ref.strip(),
            }
        )
    return items


def _amounts_close(a: float, b: float) -> bool:
    return abs(float(a) - float(b)) <= AMOUNT_TOLERANCE


async def _book_indexes(
    db: AsyncIOMotorDatabase,
    *,
    entity: str,
    bank_account_id: Optional[str],
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    pay_by_ref: Dict[str, Dict[str, Any]] = {}
    async for p in db.payments.find({"entity": entity}, {"_id": 0, "id": 1, "bank_reference": 1, "amount": 1}):
        ref = str(p.get("bank_reference") or "").strip()
        if ref:
            pay_by_ref[ref] = p

    bt_q: Dict[str, Any] = {"entity": entity}
    if bank_account_id:
        bt_q["bank_account_id"] = bank_account_id
    bt_by_ref: Dict[str, Dict[str, Any]] = {}
    async for t in db.bank_transactions.find(bt_q, {"_id": 0, "id": 1, "reference": 1, "amount": 1}):
        ref = str(t.get("reference") or "").strip()
        if ref:
            bt_by_ref[ref] = t

    return pay_by_ref, bt_by_ref


def match_line_item(
    item: Dict[str, Any],
    *,
    pay_by_ref: Dict[str, Dict[str, Any]],
    bt_by_ref: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    ref = str(item.get("reference") or "").strip()
    amt = float(item.get("amount") or 0.0)
    out = dict(item)
    book_match = None
    match_reason = None

    if ref and ref in pay_by_ref:
        book = pay_by_ref[ref]
        if _amounts_close(book.get("amount", 0), amt):
            book_match = {"type": "payment", "id": book.get("id"), "reference": ref}
        else:
            match_reason = "payment_amount_mismatch"
    elif ref and ref in bt_by_ref:
        book = bt_by_ref[ref]
        if _amounts_close(book.get("amount", 0), amt):
            book_match = {"type": "bank_transaction", "id": book.get("id"), "reference": ref}
        else:
            match_reason = "bank_txn_amount_mismatch"
    elif ref.startswith("WIRE-"):
        book_match = {"type": "heuristic", "rule": "WIRE-prefix", "reference": ref}

    classified = bool(item.get("classification"))
    if book_match:
        out["match_status"] = "matched"
    elif classified:
        out["match_status"] = "classified"
    else:
        out["match_status"] = "unmatched"

    out["book_match"] = book_match
    out["match_reason"] = match_reason
    return out


async def enrich_statement_items(
    db: AsyncIOMotorDatabase,
    st: Dict[str, Any],
) -> List[Dict[str, Any]]:
    pay_by_ref, bt_by_ref = await _book_indexes(
        db,
        entity=str(st.get("entity") or ""),
        bank_account_id=st.get("bank_account_id"),
    )
    return [match_line_item(i, pay_by_ref=pay_by_ref, bt_by_ref=bt_by_ref) for i in (st.get("items") or [])]


def count_line_buckets(items: List[Dict[str, Any]]) -> Dict[str, int]:
    matched = sum(1 for i in items if i.get("match_status") == "matched")
    classified = sum(1 for i in items if i.get("match_status") == "classified")
    unmatched = sum(1 for i in items if i.get("match_status") == "unmatched")
    return {
        "matched_count": matched,
        "classified_count": classified,
        "unmatched_count": unmatched,
        "line_count": len(items),
    }


async def run_auto_match(db: AsyncIOMotorDatabase, st: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    items = await enrich_statement_items(db, st)
    counts = count_line_buckets(items)
    return items, counts


async def apply_classifications(
    items: List[Dict[str, Any]],
    classifications: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    by_ref = {str(c.get("reference") or "").strip(): c for c in classifications if c.get("reference")}
    out: List[Dict[str, Any]] = []
    for item in items:
        ref = str(item.get("reference") or "").strip()
        patch = by_ref.get(ref)
        if patch:
            merged = {
                **item,
                "classification": patch.get("classification"),
                "classification_notes": patch.get("notes"),
                "match_status": "classified" if item.get("match_status") != "matched" else "matched",
            }
            out.append(merged)
        else:
            out.append(item)
    return out


async def build_summary(
    db: AsyncIOMotorDatabase,
    *,
    entity_code: Optional[str],
    scan_limit: int = 500,
) -> Dict[str, Any]:
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    cur = db.bank_recon_statements.find(q, {"_id": 0}).sort("created_at", -1).limit(scan_limit)
    statements = [s async for s in cur]
    total = await db.bank_recon_statements.count_documents(q or {})

    signed_off = sum(1 for s in statements if str(s.get("status") or "").lower() == "signed_off")
    pending = len(statements) - signed_off
    total_lines = sum(int(s.get("line_count") or len(s.get("items") or [])) for s in statements)
    total_unmatched = sum(int(s.get("unmatched_count") or 0) for s in statements)
    total_matched = sum(int(s.get("matched_count") or 0) for s in statements)

    by_period: Dict[str, int] = {}
    for s in statements:
        p = str(s.get("statement_period") or "—")
        by_period[p] = by_period.get(p, 0) + 1
    by_period_rows = [{"period": k, "count": v} for k, v in sorted(by_period.items(), key=lambda kv: -kv[1])]

    return {
        "kpis": {
            "total_statements": total,
            "scanned": len(statements),
            "signed_off_count": signed_off,
            "pending_signoff_count": pending,
            "total_lines": total_lines,
            "total_matched_lines": total_matched,
            "total_unmatched_lines": total_unmatched,
            "pct_signed_off": round(100.0 * signed_off / len(statements), 1) if statements else 0.0,
        },
        "by_period": by_period_rows,
    }
