"""Statutory schedule-level audit: demo payloads, procedures, exception flag rollups."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

ScheduleType = Literal["assets", "revenue", "expenses", "inventory", "liabilities"]

SCHEDULE_TYPES: tuple[str, ...] = ("assets", "revenue", "expenses", "inventory", "liabilities")


def _iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_audit_procedures(schedule_type: str) -> List[Dict[str, Any]]:
    """ISA-style procedure lines per FS area (demo checklist)."""
    common = [
        {"id": str(uuid.uuid4()), "title": "Obtain detailed schedule and agree to GL", "area": "reconciliation", "status": "pending"},
        {"id": str(uuid.uuid4()), "title": "Test arithmetic accuracy and cross-foot", "area": "mechanical", "status": "pending"},
        {"id": str(uuid.uuid4()), "title": "Enquire of management on judgements and estimates", "area": "inquiry", "status": "pending"},
    ]
    if schedule_type == "assets":
        return common + [
            {"id": str(uuid.uuid4()), "title": "Verify title / existence for sample assets", "area": "rights", "status": "pending"},
            {"id": str(uuid.uuid4()), "title": "Recalculate depreciation for sample period", "area": "valuation", "status": "pending"},
            {"id": str(uuid.uuid4()), "title": "Review additions and disposals for capitalisation", "area": "classification", "status": "pending"},
            {"id": str(uuid.uuid4()), "title": "Assess impairment indicators and triggers", "area": "impairment", "status": "pending"},
        ]
    if schedule_type == "revenue":
        return common + [
            {"id": str(uuid.uuid4()), "title": "Test revenue recognition against policy (Ind AS 115)", "area": "recognition", "status": "pending"},
            {"id": str(uuid.uuid4()), "title": "Perform sales cut-off around year-end", "area": "cutoff", "status": "pending"},
            {"id": str(uuid.uuid4()), "title": "Analytical review by customer / segment", "area": "analytics", "status": "pending"},
            {"id": str(uuid.uuid4()), "title": "Review credit notes and returns near period end", "area": "returns", "status": "pending"},
        ]
    if schedule_type == "expenses":
        return common + [
            {"id": str(uuid.uuid4()), "title": "Verify expense classification (Opex vs Capex)", "area": "classification", "status": "pending"},
            {"id": str(uuid.uuid4()), "title": "Vendor concentration and duplicate payment scan", "area": "fraud", "status": "pending"},
            {"id": str(uuid.uuid4()), "title": "Related party expense identification", "area": "RPT", "status": "pending"},
        ]
    if schedule_type == "inventory":
        return common + [
            {"id": str(uuid.uuid4()), "title": "Attend / observe stock count where material", "area": "existence", "status": "pending"},
            {"id": str(uuid.uuid4()), "title": "Test NRV and costing method", "area": "valuation", "status": "pending"},
            {"id": str(uuid.uuid4()), "title": "Slow-moving and obsolete analysis", "area": "NRV", "status": "pending"},
            {"id": str(uuid.uuid4()), "title": "Reconcile inventory sub-ledger to GL", "area": "reconciliation", "status": "pending"},
        ]
    if schedule_type == "liabilities":
        return common + [
            {"id": str(uuid.uuid4()), "title": "Review creditor ageing and long-outstanding items", "area": "ageing", "status": "pending"},
            {"id": str(uuid.uuid4()), "title": "Evaluate provision methodology and supporting data", "area": "provisions", "status": "pending"},
            {"id": str(uuid.uuid4()), "title": "Update contingent liability inquiry letter", "area": "contingencies", "status": "pending"},
        ]
    return common


def build_demo_payload(schedule_type: str) -> Dict[str, Any]:
    if schedule_type == "assets":
        return {
            "asset_register": [
                {"id": "FA-1", "name": "Plant — Mumbai", "category": "PPE", "cost": 48_000_000, "acc_dep": 35_600_000, "nbv": 12_400_000, "exception_flag": False},
                {"id": "FA-2", "name": "IT servers", "category": "Equipment", "cost": 8_200_000, "acc_dep": 6_100_000, "nbv": 2_100_000, "exception_flag": False},
                {"id": "FA-3", "name": "CWIP — automation", "category": "CWIP", "cost": 3_400_000, "acc_dep": 0, "nbv": 3_400_000, "exception_flag": True},
            ],
            "additions": [
                {"id": "ADD-1", "description": "New press line", "amount": 450_000, "date": _iso(), "capitalised": True},
                {"id": "ADD-2", "description": "Spares capitalised (review)", "amount": 88_000, "date": _iso(), "capitalised": False},
            ],
            "deletions": [{"id": "DEL-1", "description": "Scrapped vehicles", "proceeds": 120_000, "nbv_removed": 95_000}],
            "depreciation_recalculation": {
                "method": "SLM / useful lives per policy",
                "book_charge": 2_040_000,
                "recalculated_charge": 2_052_000,
                "variance": 12_000,
                "within_tolerance": False,
                "notes": "Recalculation variance — extend sample for high-value classes",
            },
            "impairment_indicators": [
                {"id": "IMP-1", "asset_id": "FA-1", "signal": "Declining capacity utilisation", "severity": "medium"},
                {"id": "IMP-2", "asset_id": "FA-3", "signal": "CWIP delay > 18 months", "severity": "high"},
            ],
        }
    if schedule_type == "revenue":
        return {
            "revenue_recognition_checks": [
                {"id": "RR-1", "document": "SO-9921", "amount": 1_200_000, "status": "ok", "note": "Performance obligation met — delivery accepted"},
                {"id": "RR-2", "document": "SO-9988", "amount": 640_000, "status": "review", "note": "Bill-and-hold — obtain management representation"},
            ],
            "cutoff_testing": [
                {"id": "CO-1", "invoice_date": "2025-03-31", "shipment_date": "2025-04-02", "amount": 890_000, "near_period_end": True, "flag": True},
                {"id": "CO-2", "invoice_date": "2025-03-28", "shipment_date": "2025-03-28", "amount": 120_000, "near_period_end": True, "flag": False},
            ],
            "customer_wise_revenue": [
                {"customer": "Acme Ltd", "amount": 4_200_000, "pct_of_revenue": 0.22},
                {"customer": "Globex", "amount": 2_100_000, "pct_of_revenue": 0.11},
                {"customer": "Others", "amount": 12_800_000, "pct_of_revenue": 0.67},
            ],
            "unusual_credit_notes": [
                {"id": "CN-1", "amount": 12_000, "reason": "Pricing rebate", "unusual": False},
                {"id": "CN-2", "amount": 520_000, "reason": "Post-year credit — large reversal", "unusual": True},
            ],
            "trends": [{"month": "Jan", "amt": 1_000_000}, {"month": "Feb", "amt": 1_200_000}, {"month": "Mar", "amt": 980_000}],
        }
    if schedule_type == "expenses":
        return {
            "expense_classification": [
                {"vendor": "Vendor A", "bucket": "opex", "amount": 220_000, "misclassified_risk": False},
                {"vendor": "Vendor B", "bucket": "capex", "amount": 410_000, "misclassified_risk": True},
            ],
            "vendor_concentration": [
                {"vendor": "Vendor A", "amount": 2_200_000, "pct": 0.34},
                {"vendor": "Vendor C", "amount": 1_100_000, "pct": 0.17},
            ],
            "duplicate_expenses": [
                {"id": "DUP-1", "invoice_a": "INV-221", "invoice_b": "INV-221-R", "amount": 18_500, "match_score": 0.97},
            ],
            "related_party_suspicion": [
                {"vendor": "Affiliate X", "amount": 890_000, "suspicion_score": 0.72, "note": "Pricing vs third-party benchmark"},
            ],
            "spikes": [{"month": "Mar", "pct_change": 0.42, "category": "repairs"}],
        }
    if schedule_type == "inventory":
        return {
            "stock_valuation": [
                {"sku": "SKU-100", "qty": 2400, "unit_cost": 141.67, "value": 340_000, "nrv_test": "ok"},
                {"sku": "SKU-200", "qty": 500, "unit_cost": 900, "value": 450_000, "nrv_test": "review"},
            ],
            "slow_moving_inventory": [
                {"sku": "SKU-77", "days_on_hand": 420, "provision_suggested": 45_000},
            ],
            "negative_stock": [{"sku": "SKU-9", "qty": -3, "system": "SAP", "flag": True}],
            "gl_reconciliation": {"gl_balance": 1_258_500, "subledger": 1_240_000, "variance": 18_500, "resolved": False},
        }
    if schedule_type == "liabilities":
        return {
            "ageing": [
                {"bucket": "0-30", "amount": 1_200_000},
                {"bucket": "31-60", "amount": 340_000},
                {"bucket": "61-90", "amount": 180_000},
                {"bucket": "90+", "amount": 95_000, "flag_stale": True},
            ],
            "unpaid_liabilities": [{"id": "L-1", "vendor": "Utility board", "amount": 55_000, "days_outstanding": 112}],
            "provision_adequacy": [
                {"name": "Warranty", "balance": 1_200_000, "adequacy": "review", "actuary_report": False},
                {"name": "Tax disputes", "balance": 3_400_000, "adequacy": "legal_opinion", "actuary_report": False},
            ],
            "contingent_liabilities": [
                {"matter": "Supplier arbitration", "estimate": 250_000, "disclosure": "yes"},
                {"matter": "Regulatory inquiry", "estimate": None, "disclosure": "possible"},
            ],
        }
    raise ValueError(f"Unknown schedule type: {schedule_type}")


def compute_exception_flags(schedule_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Roll-up booleans for dashboard chips (derived from payload; supports legacy demo keys)."""
    if schedule_type == "assets":
        dep = payload.get("depreciation_recalculation") or payload.get("depreciation") or {}
        var = float(dep.get("variance") or 0)
        imp = payload.get("impairment_indicators") or []
        add = payload.get("additions") or []
        reg = payload.get("asset_register") or payload.get("register") or []
        return {
            "depreciation_variance": abs(var) > 5000,
            "impairment_indicator": len(imp) > 0,
            "capitalisation_review": any(isinstance(a, dict) and not a.get("capitalised", True) for a in add),
            "cwip_or_long_standing": any(
                (x.get("category") == "CWIP" or x.get("exception_flag")) for x in reg if isinstance(x, dict)
            ),
        }
    if schedule_type == "revenue":
        cn = payload.get("unusual_credit_notes") or payload.get("credit_notes") or []
        co = payload.get("cutoff_testing") or payload.get("cutoff") or []
        rec = payload.get("revenue_recognition_checks") or payload.get("recognition_checks") or []
        cust = payload.get("customer_wise_revenue") or payload.get("customer_wise") or []
        unusual_cn = any(
            (c.get("unusual") if "unusual" in c else (float(c.get("amount") or 0) > 100_000))
            for c in cn
            if isinstance(c, dict)
        )
        return {
            "cutoff_flag": any(c.get("flag") or c.get("near_period_end") for c in co if isinstance(c, dict)),
            "unusual_credit_note": unusual_cn,
            "recognition_review": any((c.get("status") == "review") for c in rec if isinstance(c, dict)),
            "concentration": max(((r.get("pct_of_revenue") or r.get("pct") or 0) for r in cust if isinstance(r, dict)), default=0) > 0.2,
        }
    if schedule_type == "expenses":
        dups = payload.get("duplicate_expenses") or payload.get("duplicates") or []
        rpt = payload.get("related_party_suspicion") or payload.get("related_party_flags") or []
        cls = payload.get("expense_classification") or payload.get("classification") or []
        vlist = payload.get("vendor_concentration") or []
        return {
            "duplicate_suspected": len(dups) > 0,
            "related_party": len(rpt) > 0,
            "classification_risk": any(x.get("misclassified_risk") for x in cls if isinstance(x, dict)),
            "vendor_concentration": max(((v.get("pct") or 0) for v in vlist if isinstance(v, dict)), default=0) > 0.25,
        }
    if schedule_type == "inventory":
        gl = payload.get("gl_reconciliation") or payload.get("gl_recon") or {}
        neg = payload.get("negative_stock") or []
        slow = payload.get("slow_moving_inventory") or payload.get("slow_moving") or []
        val = payload.get("stock_valuation") or payload.get("valuation") or []
        return {
            "gl_variance": abs(float(gl.get("variance") or 0)) > 1000,
            "negative_stock": any((n.get("qty") or 0) < 0 or n.get("flag") for n in neg if isinstance(n, dict)),
            "slow_moving": len(slow) > 0,
            "nrv_review": any((v.get("nrv_test") == "review") for v in val if isinstance(v, dict)),
        }
    if schedule_type == "liabilities":
        age = payload.get("ageing") or []
        prov = payload.get("provision_adequacy") or payload.get("provisions") or []
        cont = payload.get("contingent_liabilities") or payload.get("contingent") or []
        return {
            "stale_payables": any(a.get("flag_stale") for a in age if isinstance(a, dict)),
            "unpaid_overdue": len(payload.get("unpaid_liabilities") or payload.get("unpaid") or []) > 0,
            "provision_review": any((p.get("adequacy") == "review") for p in prov if isinstance(p, dict)),
            "contingent_not_quantified": any(c.get("estimate") in (None, 0) for c in cont if isinstance(c, dict)),
        }
    return {}


def augment_schedule_for_api(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Merge defaults so API responses always include procedures, flags, evidence envelope."""
    out = dict(doc)
    st = out.get("schedule_type") or ""
    out.setdefault("evidence", [])
    if not out.get("audit_procedures"):
        out["audit_procedures"] = default_audit_procedures(st)
    payload = out.get("payload") or {}
    out["exception_flags"] = compute_exception_flags(st, payload)
    return out
