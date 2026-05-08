"""India statutory compliance checklist rows (seed + checklist builder)."""
from __future__ import annotations

import uuid
from typing import Any, Dict, List

# law_code values: CA2013, IT1961, GST, TDS, CARO, 44AB

_RAW: List[Dict[str, Any]] = [
    # Companies Act 2013 — board / accounts / audit
    {"law_code": "CA2013", "section": "128", "title": "Books of account to be kept by company", "penalty_risk": "high"},
    {"law_code": "CA2013", "section": "129", "title": "Financial statement / true & fair view", "penalty_risk": "high"},
    {"law_code": "CA2013", "section": "134", "title": "Board report & CSR / vigil disclosures", "penalty_risk": "medium"},
    {"law_code": "CA2013", "section": "143", "title": "Auditor powers & duties; reporting fraud", "penalty_risk": "high"},
    {"law_code": "CA2013", "section": "177", "title": "Audit committee (where applicable)", "penalty_risk": "medium"},
    {"law_code": "CA2013", "section": "188", "title": "Related party transactions approval", "penalty_risk": "high"},
    {"law_code": "CA2013", "section": "447", "title": "Punishment for fraud (financial statement)", "penalty_risk": "critical"},
    # Income Tax Act 1961 — selected
    {"law_code": "IT1961", "section": "44AB", "title": "Tax audit threshold & Form 3CD", "penalty_risk": "high"},
    {"law_code": "IT1961", "section": "271(1)(b)", "title": "Penalty for under-reporting / misreporting", "penalty_risk": "high"},
    {"law_code": "IT1961", "section": "201", "title": "Consequences of failure to deduct / pay TDS", "penalty_risk": "high"},
    {"law_code": "IT1961", "section": "234E", "title": "Late filing fee for TDS statements", "penalty_risk": "medium"},
    # GST
    {"law_code": "GST", "section": "GSTR-1 vs 3B", "title": "Outward supplies reconciliation (1 vs 3B)", "penalty_risk": "high"},
    {"law_code": "GST", "section": "GSTR-2B vs PR", "title": "ITC eligibility vs purchase register", "penalty_risk": "high"},
    {"law_code": "GST", "section": "ITC section 16", "title": "Conditions for availing ITC", "penalty_risk": "medium"},
    {"law_code": "GST", "section": "RCM", "title": "Reverse charge applicability & documentation", "penalty_risk": "medium"},
    {"law_code": "GST", "section": "Annual return", "title": "GSTR-9 / 9C reconciliation (if applicable)", "penalty_risk": "medium"},
    # TDS / TCS
    {"law_code": "TDS", "section": "194C", "title": "TDS on contractor payments — rates & thresholds", "penalty_risk": "medium"},
    {"law_code": "TDS", "section": "194J", "title": "TDS on professional / technical fees", "penalty_risk": "medium"},
    {"law_code": "TDS", "section": "201(1)", "title": "Default in deduction — interest u/s 201", "penalty_risk": "high"},
    {"law_code": "TDS", "section": "Challan", "title": "Challan vs ledger reconciliation", "penalty_risk": "high"},
    {"law_code": "TDS", "section": "Form 26AS", "title": "Credit in 26AS vs books (vendor perspective)", "penalty_risk": "medium"},
    # CARO 2020 (representative clauses)
    {"law_code": "CARO", "section": "3(i)(a)", "title": "Fixed assets — title deeds & physical verification", "penalty_risk": "medium"},
    {"law_code": "CARO", "section": "3(i)(c)", "title": "Revaluation of PPE (if applicable)", "penalty_risk": "medium"},
    {"law_code": "CARO", "section": "3(ii)", "title": "Inventory — physical verification & valuation", "penalty_risk": "medium"},
    {"law_code": "CARO", "section": "3(iii)", "title": "Loans granted to promoters / related parties", "penalty_risk": "high"},
    {"law_code": "CARO", "section": "3(vii)(a)", "title": "Fraud / notification by company to auditor", "penalty_risk": "critical"},
    {"law_code": "CARO", "section": "3(x)", "title": "Default in repayment of loans / borrowing", "penalty_risk": "high"},
    {"law_code": "CARO", "section": "3(xi)", "title": "Whistle-blower complaints (material)", "penalty_risk": "medium"},
    # Tax audit 44AB clauses (Form 3CD style)
    {"law_code": "44AB", "section": "10A", "title": "Observations on books of account (3CD)", "penalty_risk": "medium"},
    {"law_code": "44AB", "section": "11", "title": "Payment of actual expenses / provisions", "penalty_risk": "medium"},
    {"law_code": "44AB", "section": "34", "title": "Compliance with TDS/TCS provisions", "penalty_risk": "high"},
    {"law_code": "44AB", "section": "43", "title": "GST turnover reconciliation with audited revenue", "penalty_risk": "high"},
]


def compliance_rows_for_laws(law_codes: List[str]) -> List[Dict[str, Any]]:
    """Build requirement rows with ids and default status."""
    codes = set(law_codes) if law_codes else {"CA2013", "IT1961", "GST", "TDS", "CARO", "44AB"}
    out: List[Dict[str, Any]] = []
    for r in _RAW:
        if r["law_code"] not in codes:
            continue
        out.append(
            {
                "id": str(uuid.uuid4()),
                "law_code": r["law_code"],
                "section": r["section"],
                "title": f"{r['law_code']} · {r['section']} — {r['title']}",
                "status": "pending evidence",
                "penalty_risk": r.get("penalty_risk", "medium"),
            }
        )
    return out
