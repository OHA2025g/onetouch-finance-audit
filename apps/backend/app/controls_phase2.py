"""Phase 2 continuous control runners for the expanded process coverage."""
from __future__ import annotations
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _exc(control: dict, *, entity: str, severity: str, title: str, summary: str,
         source_record_type: str, source_record_id: str,
         financial_exposure: float, materiality_score: float, anomaly_score: float) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "control_id": control["id"],
        "control_code": control["code"],
        "control_name": control["name"],
        "process": control["process"],
        "entity": entity,
        "severity": severity,
        "status": "open",
        "materiality_score": round(materiality_score, 2),
        "anomaly_score": round(anomaly_score, 2),
        "financial_exposure": round(financial_exposure, 2),
        "source_record_type": source_record_type,
        "source_record_id": source_record_id,
        "detected_at": _iso(datetime.now(timezone.utc)),
        "title": title,
        "summary": summary,
        "recurrence_count": 0,
    }


# ---------------- ORDER TO CASH ----------------

async def run_customer_credit_limit_breach(db, control):
    exs = []
    # Sum exposure (open sales orders + open AR invoices) per customer
    exposure = defaultdict(float)
    async for so in db.sales_orders.find({"status": {"$in": ["open", "shipped"]}}, {"_id": 0}):
        exposure[so["customer_id"]] += so["amount"]
    async for inv in db.ar_invoices.find({"status": "open"}, {"_id": 0}):
        exposure[inv["customer_id"]] += inv["amount"]
    async for cust in db.customers.find({}, {"_id": 0}):
        exp = exposure.get(cust["id"], 0.0)
        if exp > cust["credit_limit"] and cust["credit_limit"] > 0:
            over = exp - cust["credit_limit"]
            pct = over / cust["credit_limit"]
            sev = "critical" if pct > 0.5 else "high" if pct > 0.2 else "medium"
            exs.append(_exc(control,
                            entity=cust["entity"],
                            severity=sev,
                            title=f"{cust['customer_name']} exposure ${exp:,.0f} over ${cust['credit_limit']:,.0f} limit",
                            summary=(f"Customer {cust['customer_name']} has total open exposure of ${exp:,.2f} "
                                     f"vs approved credit limit ${cust['credit_limit']:,.2f} — breach ${over:,.2f} ({pct*100:.1f}%)."),
                            source_record_type="customer",
                            source_record_id=cust["id"],
                            financial_exposure=over,
                            materiality_score=min(1.0, over / 500_000),
                            anomaly_score=min(0.99, 0.5 + pct)))
    return exs


async def run_aged_receivables(db, control):
    exs = []
    now = datetime.now(timezone.utc)
    async for inv in db.ar_invoices.find({"status": "open"}, {"_id": 0}):
        try:
            due = datetime.fromisoformat(inv["due_date"])
        except Exception:
            continue
        days_overdue = (now - due).days
        if days_overdue > 90:
            sev = "high" if days_overdue > 150 else "medium"
            exs.append(_exc(control,
                            entity=inv["entity"],
                            severity=sev,
                            title=f"AR {inv['ar_number']} · {inv['customer_name']} · {days_overdue}d overdue",
                            summary=(f"Invoice {inv['ar_number']} for {inv['customer_name']} "
                                     f"(${inv['amount']:,.2f}) is {days_overdue} days past the "
                                     f"{inv['due_date'][:10]} due date with no allowance or write-off."),
                            source_record_type="ar_invoice",
                            source_record_id=inv["id"],
                            financial_exposure=inv["amount"],
                            materiality_score=min(1.0, inv["amount"] / 200_000),
                            anomaly_score=min(0.95, 0.4 + days_overdue / 365)))
    return exs


async def run_revenue_cutoff(db, control):
    exs = []
    async for inv in db.ar_invoices.find({}, {"_id": 0}):
        try:
            inv_date = datetime.fromisoformat(inv["invoice_date"])
            ship_date = datetime.fromisoformat(inv["shipment_date"])
        except Exception:
            continue
        # Revenue cut-off issue: invoice booked before shipment occurred
        gap_days = (ship_date - inv_date).days
        if gap_days >= 3:  # shipment more than 3 days after invoice date
            exs.append(_exc(control,
                            entity=inv["entity"],
                            severity="critical",
                            title=f"Cutoff: {inv['ar_number']} billed {gap_days}d before shipment",
                            summary=(f"AR invoice {inv['ar_number']} dated {inv['invoice_date'][:10]} "
                                     f"recognizes revenue {gap_days} days before shipment on "
                                     f"{inv['shipment_date'][:10]} — potential ASC 606 breach."),
                            source_record_type="ar_invoice",
                            source_record_id=inv["id"],
                            financial_exposure=inv["amount"],
                            materiality_score=min(1.0, inv["amount"] / 300_000),
                            anomaly_score=0.9))
    return exs


# ---------------- PAYROLL ----------------

async def run_ghost_employee(db, control):
    exs = []
    # Build employee status lookup
    status = {e["id"]: e async for e in db.employees.find({}, {"_id": 0})}
    async for pe in db.payroll_entries.find({}, {"_id": 0}):
        emp = status.get(pe["employee_id"])
        if emp and emp["status"] == "terminated":
            term_date = emp.get("terminated_at")
            exs.append(_exc(control,
                            entity=pe["entity"],
                            severity="critical",
                            title=f"Ghost payment: {pe['employee_name']} (terminated {term_date[:10] if term_date else '?'})",
                            summary=(f"Payroll entry {pe['id']} paid ${pe['net_amount']:,.2f} net "
                                     f"to {pe['employee_name']} for period {pe['period']} — "
                                     f"employee status is terminated."),
                            source_record_type="payroll_entry",
                            source_record_id=pe["id"],
                            financial_exposure=pe["net_amount"],
                            materiality_score=min(1.0, pe["net_amount"] / 50_000),
                            anomaly_score=0.96))
    return exs


async def run_duplicate_payroll(db, control):
    exs = []
    grouped = defaultdict(list)
    async for pe in db.payroll_entries.find({}, {"_id": 0}):
        key = (pe["employee_id"], pe["period"], round(pe["net_amount"], 2))
        grouped[key].append(pe)
    for items in grouped.values():
        if len(items) > 1:
            for dup in items[1:]:
                exs.append(_exc(control,
                                entity=dup["entity"],
                                severity="high",
                                title=f"Duplicate payroll: {dup['employee_name']} {dup['period']}",
                                summary=(f"Employee {dup['employee_name']} ({dup['employee_id']}) "
                                         f"has {len(items)} payroll entries in {dup['period']} "
                                         f"with identical net ${dup['net_amount']:,.2f}."),
                                source_record_type="payroll_entry",
                                source_record_id=dup["id"],
                                financial_exposure=dup["net_amount"],
                                materiality_score=min(1.0, dup["net_amount"] / 40_000),
                                anomaly_score=0.92))
    return exs


# ---------------- TREASURY ----------------

async def run_off_hours_transfer(db, control):
    exs = []
    threshold = 250_000
    async for bt in db.bank_transactions.find({"direction": "outbound", "amount": {"$gt": threshold}}, {"_id": 0}):
        try:
            ts = datetime.fromisoformat(bt["txn_ts"])
        except Exception:
            continue
        off_hours = ts.hour < 7 or ts.hour >= 19 or ts.weekday() >= 5
        if off_hours:
            exs.append(_exc(control,
                            entity=bt["entity"],
                            severity="high",
                            title=f"Off-hours wire ${bt['amount']:,.0f} to {bt['counterparty']}",
                            summary=(f"Outbound transfer {bt['reference']} for ${bt['amount']:,.2f} "
                                     f"posted at {ts.isoformat(timespec='minutes')} "
                                     f"({'weekend' if ts.weekday() >= 5 else 'outside 07-19 UTC'})."),
                            source_record_type="bank_transaction",
                            source_record_id=bt["id"],
                            financial_exposure=bt["amount"],
                            materiality_score=min(1.0, bt["amount"] / 1_000_000),
                            anomaly_score=min(0.95, 0.6 + bt["amount"] / 5_000_000)))
    return exs


async def run_fx_deviation(db, control):
    exs = []
    # Load mid rates for today (by pair)
    mid_by_pair = {}
    async for f in db.fx_rates.find({"type": {"$exists": False}}, {"_id": 0}):
        # Keep most recent per pair
        if f["pair"] not in mid_by_pair or f["date"] > mid_by_pair[f["pair"]]["date"]:
            mid_by_pair[f["pair"]] = f
    # Compare journal usage to mid
    async for usage in db.fx_rates.find({"type": "journal_usage"}, {"_id": 0}):
        mid = mid_by_pair.get(usage["pair"])
        if not mid:
            continue
        dev = abs(usage["rate_used"] - mid["mid_rate"]) / mid["mid_rate"]
        if dev > 0.015:  # 1.5%
            exposure = usage["booked_amount"] * dev
            sev = "high" if dev > 0.05 else "medium"
            exs.append(_exc(control,
                            entity=usage["entity"],
                            severity=sev,
                            title=f"FX deviation {dev*100:.2f}% on {usage['pair']} journal {usage['journal_ref']}",
                            summary=(f"Journal {usage['journal_ref']} booked {usage['pair']} at {usage['rate_used']} "
                                     f"vs mid {mid['mid_rate']} ({dev*100:.2f}% deviation) — "
                                     f"translation impact ~${exposure:,.2f}."),
                            source_record_type="fx_rate",
                            source_record_id=usage["id"],
                            financial_exposure=exposure,
                            materiality_score=min(1.0, exposure / 50_000),
                            anomaly_score=min(0.9, 0.4 + dev * 10)))
    return exs


# ---------------- TAX ----------------

async def run_withholding_shortfall(db, control):
    exs = []
    async for w in db.withholding_records.find({}, {"_id": 0}):
        if w["required_amount"] > 0:
            shortfall = w["required_amount"] - w["withheld_amount"]
            if shortfall > 100:  # material shortfall
                pct = shortfall / w["required_amount"]
                sev = "high" if pct > 0.3 else "medium"
                exs.append(_exc(control,
                                entity=w["entity"],
                                severity=sev,
                                title=f"WHT short ${shortfall:,.0f} on {w['invoice_ref']}",
                                summary=(f"Invoice {w['invoice_ref']} (vendor {w['vendor_id']}) required "
                                         f"${w['required_amount']:,.2f} WHT at {w['required_rate']*100:.1f}% "
                                         f"but only ${w['withheld_amount']:,.2f} withheld — shortfall ${shortfall:,.2f}."),
                                source_record_type="withholding",
                                source_record_id=w["id"],
                                financial_exposure=shortfall,
                                materiality_score=min(1.0, shortfall / 25_000),
                                anomaly_score=min(0.85, 0.4 + pct)))
    return exs


# ---------------- FIXED ASSETS ----------------

async def run_fa_depreciation_missing(db, control):
    exs = []
    now = datetime.now(timezone.utc)
    current_period = now.strftime("%Y-%m")
    # Build posted depreciation set for current period
    posted = set()
    async for d in db.depreciation_schedules.find({"period": current_period}, {"_id": 0}):
        posted.add(d["asset_id"])
    async for a in db.fixed_assets.find({"status": "in_service"}, {"_id": 0}):
        try:
            in_service = datetime.fromisoformat(a["in_service_date"])
        except Exception:
            continue
        # Only expect depreciation after in-service and still within useful life
        months_used = (now.year - in_service.year) * 12 + (now.month - in_service.month)
        if 0 <= months_used < a["useful_life_months"] and a["id"] not in posted:
            exs.append(_exc(control,
                            entity=a["entity"],
                            severity="medium",
                            title=f"FA {a['asset_code']} missing {current_period} depreciation",
                            summary=(f"Asset {a['asset_name']} ({a['asset_code']}) in service since "
                                     f"{a['in_service_date'][:10]} has no depreciation entry for "
                                     f"{current_period}. Expected ${a['monthly_depreciation']:,.2f}."),
                            source_record_type="fixed_asset",
                            source_record_id=a["id"],
                            financial_exposure=a["monthly_depreciation"],
                            materiality_score=min(1.0, a["monthly_depreciation"] / 20_000),
                            anomaly_score=0.75))
    return exs


async def run_fa_depreciation_on_disposed(db, control):
    exs = []
    disposed = {a["id"]: a async for a in db.fixed_assets.find({"status": "disposed"}, {"_id": 0})}
    async for d in db.depreciation_schedules.find({}, {"_id": 0}):
        a = disposed.get(d["asset_id"])
        if not a:
            continue
        try:
            disposal_date = datetime.fromisoformat(a["disposed_at"])
            posted_at = datetime.fromisoformat(d["posted_at"])
        except Exception:
            continue
        if posted_at > disposal_date:
            exs.append(_exc(control,
                            entity=a["entity"],
                            severity="high",
                            title=f"Depreciation posted after disposal: {a['asset_code']}",
                            summary=(f"Asset {a['asset_name']} disposed on {a['disposed_at'][:10]} "
                                     f"has depreciation {d['id']} posted {d['posted_at'][:10]} for ${d['amount']:,.2f}."),
                            source_record_type="depreciation",
                            source_record_id=d["id"],
                            financial_exposure=d["amount"],
                            materiality_score=min(1.0, d["amount"] / 25_000),
                            anomaly_score=0.88))
    return exs


async def run_capex_overbudget(db, control):
    exs = []
    async for p in db.capex_projects.find({}, {"_id": 0}):
        if p["budget_amount"] <= 0:
            continue
        if p["actual_amount"] > p["budget_amount"]:
            over = p["actual_amount"] - p["budget_amount"]
            pct = over / p["budget_amount"]
            sev = "critical" if pct > 0.25 else "high" if pct > 0.10 else "medium"
            exs.append(_exc(control,
                            entity=p["entity"],
                            severity=sev,
                            title=f"{p['project_name']} over budget ${over:,.0f} ({pct*100:.1f}%)",
                            summary=(f"Project {p['project_code']} actual ${p['actual_amount']:,.2f} "
                                     f"exceeds approved budget ${p['budget_amount']:,.2f} by ${over:,.2f} "
                                     f"({pct*100:.1f}%) without a change order."),
                            source_record_type="capex_project",
                            source_record_id=p["id"],
                            financial_exposure=over,
                            materiality_score=min(1.0, over / 500_000),
                            anomaly_score=min(0.9, 0.4 + pct)))
    return exs


RUNNERS_PHASE2 = {
    "C-OTC-001": run_customer_credit_limit_breach,
    "C-OTC-002": run_aged_receivables,
    "C-OTC-003": run_revenue_cutoff,
    "C-PAY-001": run_ghost_employee,
    "C-PAY-002": run_duplicate_payroll,
    "C-TR-002": run_off_hours_transfer,
    "C-TR-003": run_fx_deviation,
    "C-TX-002": run_withholding_shortfall,
    "C-FA-001": run_fa_depreciation_missing,
    "C-FA-002": run_fa_depreciation_on_disposed,
    "C-FA-003": run_capex_overbudget,
}
