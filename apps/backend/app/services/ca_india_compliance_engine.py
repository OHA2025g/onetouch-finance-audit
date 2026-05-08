"""India statutory compliance: structured library, GST/TDS check math, filing hints."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


def compliance_laws_catalog() -> List[Dict[str, Any]]:
    """Structured laws → sections for GET /compliance/library."""
    return [
        {
            "code": "CA2013",
            "name": "Companies Act 2013",
            "short_name": "Companies Act 2013",
            "sections": [
                {"code": "128", "title": "Books of account"},
                {"code": "129", "title": "Financial statements"},
                {"code": "134", "title": "Board report"},
                {"code": "143", "title": "Auditor powers & duties"},
            ],
        },
        {
            "code": "IT1961",
            "name": "Income Tax Act 1961",
            "short_name": "Income Tax Act 1961",
            "sections": [
                {"code": "44AB", "title": "Tax audit"},
                {"code": "201", "title": "TDS defaults"},
                {"code": "271", "title": "Penalties"},
            ],
        },
        {
            "code": "GST",
            "name": "Goods and Services Tax",
            "short_name": "GST",
            "sections": [
                {"code": "GSTR-1", "title": "Outward supplies return"},
                {"code": "GSTR-3B", "title": "Summary return & payment"},
                {"code": "GSTR-2B", "title": "Auto-drafted ITC statement"},
            ],
        },
        {
            "code": "TDS",
            "name": "TDS/TCS",
            "short_name": "TDS/TCS",
            "sections": [
                {"code": "194C", "title": "Contractors"},
                {"code": "194J", "title": "Professional fees"},
                {"code": "Challan", "title": "Deposit vs books"},
            ],
        },
        {
            "code": "CARO",
            "name": "CARO 2020",
            "short_name": "CARO",
            "sections": [
                {"code": "3(i)", "title": "Property, plant & equipment"},
                {"code": "3(ii)", "title": "Inventory"},
                {"code": "3(iii)", "title": "Loans to related parties"},
            ],
        },
        {
            "code": "44AB",
            "name": "Tax Audit (Form 3CD)",
            "short_name": "Tax Audit 44AB",
            "sections": [
                {"code": "10A", "title": "Books of account observations"},
                {"code": "10B", "title": "Other observations"},
                {"code": "10C", "title": "CARO / other reporting"},
            ],
        },
    ]


def compute_gst_checks(raw: Dict[str, Any]) -> Dict[str, Any]:
    """GST reconciliation signals (GSTR-1 vs 3B, 2B vs PR, ITC, tax liability)."""
    g1 = float(raw.get("gstr1_sales") or 0)
    g3b = float(raw.get("gstr3b_sales") or 0)
    g2b = float(raw.get("gstr2b_purchases") or 0)
    pr = float(raw.get("purchase_register") or 0)
    itc_c = float(raw.get("itc_claimed") or 0)
    itc_e = float(raw.get("itc_eligible") or 0)
    tax_3b = raw.get("gstr3b_output_tax_liability")
    tax_books = raw.get("books_output_tax_liability")
    checks: Dict[str, Any] = {
        "gstr1_vs_3b_sales_delta": round(g1 - g3b, 2),
        "gstr2b_vs_pr_delta": round(g2b - pr, 2),
        "itc_mismatch": round(itc_c - itc_e, 2),
        "tax_liability_mismatch": None,
        "flags": {
            "gstr1_vs_3b_material": abs(g1 - g3b) > 0.01,
            "gstr2b_vs_pr_material": abs(g2b - pr) > 0.01,
            "itc_material": abs(itc_c - itc_e) > 0.01,
            "tax_liability_material": False,
        },
    }
    if tax_3b is not None and tax_books is not None:
        t3 = float(tax_3b)
        tb = float(tax_books)
        checks["tax_liability_mismatch"] = round(t3 - tb, 2)
        checks["flags"]["tax_liability_material"] = abs(t3 - tb) > 0.01
    else:
        checks["tax_liability_mismatch"] = 0.0
    return checks


def compute_tds_checks(raw: Dict[str, Any]) -> Dict[str, Any]:
    """TDS reconciliation: ledger vs challan, rate mismatch, unpaid, delay."""
    led = float(raw.get("ledger_tds") or 0)
    ch = float(raw.get("challan_tds") or 0)
    days = int(raw.get("delayed_payment_days") or 0)
    exp = raw.get("expected_deduction_rate_pct")
    app = raw.get("applied_deduction_rate_pct")
    rate_delta = None
    rate_flag = False
    if exp is not None and app is not None:
        rate_delta = round(float(app) - float(exp), 4)
        rate_flag = abs(float(app) - float(exp)) > 0.05
    unpaid = max(0.0, led - ch)
    return {
        "ledger_vs_challan": round(led - ch, 2),
        "unpaid_tds": round(unpaid, 2),
        "delayed_payment_days": days,
        "deduction_rate_delta_pct": rate_delta,
        "flags": {
            "ledger_challan_mismatch": abs(led - ch) > 0.01,
            "unpaid_tds": unpaid > 0.01,
            "delayed_payment": days > 0,
            "rate_mismatch": rate_flag,
        },
    }


def default_filing_due_dates() -> List[Dict[str, Any]]:
    """Template filing cadence (relative demo dates from UTC today)."""
    base = datetime.now(timezone.utc)
    return [
        {
            "id": "fd-gstr1",
            "law_code": "GST",
            "form_code": "GSTR-1",
            "title": "GSTR-1 (monthly / QRMP)",
            "due_date": (base + timedelta(days=11)).date().isoformat(),
            "penalty_risk": "high",
        },
        {
            "id": "fd-gstr3b",
            "law_code": "GST",
            "form_code": "GSTR-3B",
            "title": "GSTR-3B payment & return",
            "due_date": (base + timedelta(days=18)).date().isoformat(),
            "penalty_risk": "high",
        },
        {
            "id": "fd-tds",
            "law_code": "TDS",
            "form_code": "24Q",
            "title": "TDS quarterly statement",
            "due_date": (base + timedelta(days=32)).date().isoformat(),
            "penalty_risk": "medium",
        },
        {
            "id": "fd-aoc4",
            "law_code": "CA2013",
            "form_code": "AOC-4",
            "title": "Financials filing with MCA",
            "due_date": (base + timedelta(days=60)).date().isoformat(),
            "penalty_risk": "high",
        },
        {
            "id": "fd-3cd",
            "law_code": "44AB",
            "form_code": "3CD",
            "title": "Tax audit report filing",
            "due_date": (base + timedelta(days=45)).date().isoformat(),
            "penalty_risk": "high",
        },
    ]


def compliance_requirements_to_csv_rows(requirements: List[Dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "law_code", "section", "title", "status", "penalty_risk", "evidence_uri", "notes"])
    for r in requirements:
        w.writerow(
            [
                r.get("id", ""),
                r.get("law_code", ""),
                r.get("section", ""),
                r.get("title", ""),
                r.get("status", ""),
                r.get("penalty_risk", ""),
                r.get("evidence_uri") or "",
                (r.get("notes") or "").replace("\n", " "),
            ]
        )
    return buf.getvalue()
