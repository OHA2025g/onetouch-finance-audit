"""Financial statement mapping from trial balance (bucket classification + FS line build)."""
from __future__ import annotations

import hashlib
import uuid
from typing import Any, Dict, List, Literal, Optional, Tuple

FSBucket = Literal["assets", "liabilities", "equity", "revenue", "expenses", "unmapped"]


def classify_line_record(line: Dict[str, Any]) -> Tuple[FSBucket, str]:
    """Classify using optional `classification_override` on the TB row."""
    ov = (line.get("classification_override") or "").strip().lower()
    if ov in ("assets", "liabilities", "equity", "revenue", "expenses"):
        return ov, "manual_override"  # type: ignore[return-value]
    return classify_account(str(line.get("account_code") or ""), str(line.get("account_name") or ""))


def classify_account(account_code: str, account_name: str) -> Tuple[FSBucket, str]:
    """
    Map a GL line to reporting bucket using code prefix heuristics (demo IND-style) and name keywords.
    Returns (bucket, rule_note).
    """
    code = (account_code or "").strip().upper()
    name = (account_name or "").strip().lower()

    if code.startswith("1") or "asset" in name or "receivable" in name or "inventory" in name or "cash" in name:
        return "assets", "prefix_or_asset_keyword"
    if code.startswith("2") or "liab" in name or "payable" in name or "loan" in name or "borrow" in name:
        return "liabilities", "prefix_or_liability_keyword"
    if code.startswith("3") or "equity" in name or "capital" in name or "retained" in name or "reserve" in name:
        return "equity", "prefix_or_equity_keyword"
    if code.startswith("4") or "revenue" in name or "income" in name or "sales" in name:
        return "revenue", "prefix_or_revenue_keyword"
    if code.startswith(("5", "6", "7", "8", "9")) or "expense" in name or "cost" in name or "depreciation" in name:
        return "expenses", "prefix_or_expense_keyword"
    # Fallback: name-only hints
    if "expense" in name or "cost" in name:
        return "expenses", "name_expense"
    if "revenue" in name or "income" in name:
        return "revenue", "name_revenue"
    return "unmapped", "no_rule"


def net_amount(line: Dict[str, Any]) -> float:
    return float(line.get("debit") or 0) - float(line.get("credit") or 0)


def build_financial_statement_mappings(lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for ln in lines:
        code = str(ln.get("account_code") or "")
        name = str(ln.get("account_name") or "")
        bucket, rule = classify_line_record(ln)
        stmt: str = "balance_sheet" if bucket in ("assets", "liabilities", "equity") else "profit_loss"
        if bucket == "unmapped":
            stmt = "unmapped"
        out.append(
            {
                "id": str(uuid.uuid4()),
                "trial_balance_line_id": ln.get("id"),
                "account_code": code,
                "account_name": name,
                "net_amount": round(net_amount(ln), 2),
                "mapped_bucket": bucket,
                "statement": stmt,
                "mapping_rule": rule,
            }
        )
    return out


def _materiality_flag(abs_amt: float, final_m: float) -> str:
    if not final_m or final_m <= 0:
        return "none"
    if abs_amt >= 3 * final_m:
        return "material"
    if abs_amt >= final_m:
        return "performance"
    return "none"


def build_balance_sheet_lines(
    lines: List[Dict[str, Any]],
    mappings: List[Dict[str, Any]],
    prev_by_code: Dict[str, float],
    final_materiality: float,
) -> List[Dict[str, Any]]:
    by_bucket: Dict[str, List[Dict[str, Any]]] = {b: [] for b in ("assets", "liabilities", "equity")}
    m_by_code = {m["account_code"]: m for m in mappings}
    for ln in lines:
        code = str(ln.get("account_code") or "")
        m = m_by_code.get(code)
        if not m or m["mapped_bucket"] not in by_bucket:
            continue
        n = net_amount(ln)
        prev = float(prev_by_code.get(code, 0) or 0)
        disp = abs(n) if m["mapped_bucket"] == "liabilities" else n
        disp_prev = abs(prev) if m["mapped_bucket"] == "liabilities" else prev
        by_bucket[m["mapped_bucket"]].append(
            {
                "account_code": code,
                "account_name": ln.get("account_name"),
                "net_amount": round(n, 2),
                "display_amount": round(disp, 2),
                "trial_balance_line_id": ln.get("id"),
                "prior_net": round(prev, 2),
                "variance": round(disp - disp_prev, 2),
                "materiality_flag": _materiality_flag(abs(n - prev), final_materiality) if prev else _materiality_flag(abs(n), final_materiality),
            }
        )
    labels = {"assets": "Assets", "liabilities": "Liabilities", "equity": "Equity"}
    out: List[Dict[str, Any]] = []
    for bucket in ("assets", "liabilities", "equity"):
        rows = by_bucket[bucket]
        if bucket == "liabilities":
            total = sum(abs(r["net_amount"]) for r in rows)
            prior_total = sum(abs(r["prior_net"]) for r in rows)
        else:
            total = sum(r["net_amount"] for r in rows)
            prior_total = sum(r["prior_net"] for r in rows)
        out.append(
            {
                "id": f"bs-{bucket}",
                "line": labels[bucket],
                "bucket": bucket,
                "amount": round(total, 2),
                "prior_amount": round(prior_total, 2),
                "variance": round(total - prior_total, 2),
                "materiality_flag": _materiality_flag(abs(total - prior_total), final_materiality) if prev_by_code else _materiality_flag(abs(total), final_materiality),
                "child_accounts": rows,
            }
        )
    return out


def build_profit_loss_lines(
    lines: List[Dict[str, Any]],
    mappings: List[Dict[str, Any]],
    prev_by_code: Dict[str, float],
    final_materiality: float,
) -> List[Dict[str, Any]]:
    by_bucket: Dict[str, List[Dict[str, Any]]] = {"revenue": [], "expenses": [], "unmapped": []}
    m_by_code = {m["account_code"]: m for m in mappings}
    for ln in lines:
        code = str(ln.get("account_code") or "")
        m = m_by_code.get(code)
        if not m:
            continue
        b = m["mapped_bucket"]
        if b not in by_bucket:
            b = "unmapped"
        n = net_amount(ln)
        prev = float(prev_by_code.get(code, 0) or 0)
        disp = abs(n) if b in ("revenue", "expenses") else n
        disp_prev = abs(prev) if b in ("revenue", "expenses") else prev
        by_bucket[b].append(
            {
                "account_code": code,
                "account_name": ln.get("account_name"),
                "net_amount": round(n, 2),
                "display_amount": round(disp, 2),
                "trial_balance_line_id": ln.get("id"),
                "prior_net": round(prev, 2),
                "variance": round(disp - disp_prev, 2),
                "materiality_flag": _materiality_flag(abs(n - prev), final_materiality) if prev else _materiality_flag(abs(n), final_materiality),
            }
        )
    out: List[Dict[str, Any]] = []
    for bucket, title in (("revenue", "Revenue"), ("expenses", "Expenses"), ("unmapped", "Unmapped P&L")):
        rows = by_bucket[bucket]
        if bucket == "unmapped" and not rows:
            continue
        if bucket in ("revenue", "expenses"):
            total = sum(abs(r["net_amount"]) for r in rows)
            prior_total = sum(abs(r["prior_net"]) for r in rows)
        else:
            total = sum(r["net_amount"] for r in rows)
            prior_total = sum(r["prior_net"] for r in rows)
        out.append(
            {
                "id": f"pl-{bucket}",
                "line": title,
                "bucket": bucket,
                "amount": round(total, 2),
                "prior_amount": round(prior_total, 2),
                "variance": round(total - prior_total, 2),
                "materiality_flag": _materiality_flag(abs(total - prior_total), final_materiality) if prev_by_code else _materiality_flag(abs(total), final_materiality),
                "child_accounts": rows,
            }
        )
    return out


def build_cash_flow_lines(bs_totals: Dict[str, float], pl_net: float) -> List[Dict[str, Any]]:
    """Indirect-method style demo: operating ≈ P&L net; investing/financing placeholders."""
    operating = round(pl_net, 2)
    return [
        {"id": "cf-op", "line": "Operating activities (demo)", "amount": operating, "section": "operating"},
        {"id": "cf-inv", "line": "Investing activities (demo)", "amount": 0.0, "section": "investing"},
        {"id": "cf-fin", "line": "Financing activities (demo)", "amount": 0.0, "section": "financing"},
        {"id": "cf-nc", "line": "Net change in cash (demo)", "amount": operating, "section": "summary"},
    ]


def build_financial_schedules(lines: List[Dict[str, Any]], mappings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Lightweight schedule groupings for audit workbook cross-checks."""
    m_by_code = {m["account_code"]: m for m in mappings}
    assets = [ln for ln in lines if m_by_code.get(str(ln.get("account_code") or ""), {}).get("mapped_bucket") == "assets"]
    rev = [ln for ln in lines if m_by_code.get(str(ln.get("account_code") or ""), {}).get("mapped_bucket") == "revenue"]
    return [
        {
            "id": "sched-fixed-assets",
            "title": "Fixed assets / PPE tie-out",
            "schedule_type": "assets",
            "account_codes": [str(ln.get("account_code")) for ln in assets if "plant" in str(ln.get("account_name") or "").lower() or "ppe" in str(ln.get("account_name") or "").lower()][:40],
        },
        {
            "id": "sched-revenue",
            "title": "Revenue analytical",
            "schedule_type": "revenue",
            "account_codes": [str(ln.get("account_code")) for ln in rev][:80],
        },
    ]


def variance_chart_rows(bs_lines: List[Dict[str, Any]], pl_lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for block in bs_lines + pl_lines:
        rows.append(
            {
                "name": block.get("line") or block.get("bucket"),
                "current": float(block.get("amount") or 0),
                "prior": float(block.get("prior_amount") or 0),
                "variance": float(block.get("variance") or 0),
            }
        )
    return rows


def stable_ledger_seed(account_code: str) -> int:
    return int(hashlib.sha256(account_code.encode()).hexdigest()[:8], 16)


def demo_ledger_transactions_for_account(account_code: str, account_name: str, net_hint: float) -> List[Dict[str, Any]]:
    """Deterministic demo journal lines for drilldown (no external GL)."""
    seed = stable_ledger_seed(account_code)
    base = max(1.0, abs(net_hint) or 1000.0)
    parts = [
        (0.55, "JE"),
        (0.30, "JE"),
        (0.15, "JE"),
    ]
    out: List[Dict[str, Any]] = []
    for i, (pct, src) in enumerate(parts):
        amt = round(base * pct * (1 if net_hint >= 0 else -1), 2)
        jid = f"J-{account_code}-{seed % 10000 + i}"
        out.append(
            {
                "journal_id": jid,
                "posting_date": "2025-03-31",
                "description": f"{src} — {account_name or account_code}"[:120],
                "debit": amt if amt > 0 else 0.0,
                "credit": -amt if amt < 0 else 0.0,
                "source": "demo_ledger",
            }
        )
    return out
