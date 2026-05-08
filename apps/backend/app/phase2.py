"""Phase 2 expansion: Order-to-Cash, Payroll, Treasury (deeper), Tax (deeper), Fixed Assets.

Keeps synthetic data generation + idempotent seeding isolated from the original seed so
existing Phase 1 installs can be upgraded in place without a full wipe.
"""
from __future__ import annotations
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


ENTITY_CODES = ["US-HQ", "UK-OPS", "IN-SVC", "SG-APAC"]


# --------- Phase 2 control catalog (appended to the 12-rule pack) ---------
CONTROLS_PHASE2 = [
    {"code": "C-OTC-001", "name": "Customer Credit Limit Breach", "process": "Order-to-Cash",
     "risk": "Credit exposure / bad debt", "criticality": "High", "frequency": "Daily",
     "owner_email": "controller@onetouch.ai",
     "description": "Sales orders or open AR that push customer exposure past their approved credit limit.",
     "framework": "SOX 404; COSO"},
    {"code": "C-OTC-002", "name": "Aged Customer Receivables > 90d", "process": "Order-to-Cash",
     "risk": "Uncollectible AR", "criticality": "Medium", "frequency": "Weekly",
     "owner_email": "controller@onetouch.ai",
     "description": "Customer invoices open beyond 90 days without allowance or write-off evidence.",
     "framework": "SOX 404; IFRS 9"},
    {"code": "C-OTC-003", "name": "Revenue Cutoff Risk", "process": "Order-to-Cash",
     "risk": "Revenue misstatement", "criticality": "Critical", "frequency": "Monthly",
     "owner_email": "gl.lead@onetouch.ai",
     "description": "AR invoices booked within 3 days of period-end where shipment is post period-end.",
     "framework": "SOX 404; ASC 606"},
    {"code": "C-PAY-001", "name": "Ghost Employee Payment", "process": "Payroll",
     "risk": "Payroll fraud", "criticality": "Critical", "frequency": "Monthly",
     "owner_email": "compliance@onetouch.ai",
     "description": "Payroll entries issued to employees whose HR status is terminated or inactive.",
     "framework": "SOX 404; ACFE"},
    {"code": "C-PAY-002", "name": "Duplicate Payroll Entry", "process": "Payroll",
     "risk": "Overpayment", "criticality": "High", "frequency": "Monthly",
     "owner_email": "compliance@onetouch.ai",
     "description": "Same employee paid twice within a single payroll period with identical net amount.",
     "framework": "SOX 404"},
    {"code": "C-TR-002", "name": "Off-Hours Large Bank Transfer", "process": "Treasury",
     "risk": "Fraudulent wire", "criticality": "High", "frequency": "Daily",
     "owner_email": "controller@onetouch.ai",
     "description": "Outbound bank transfers above USD 250k posted on weekends or outside 07–19 UTC.",
     "framework": "SOX ITGC; AFP"},
    {"code": "C-TR-003", "name": "FX Rate Deviation", "process": "Treasury",
     "risk": "Revaluation misstatement", "criticality": "Medium", "frequency": "Monthly",
     "owner_email": "controller@onetouch.ai",
     "description": "Journal/translation booked with FX rate deviating >1.5% from the official daily mid rate.",
     "framework": "IFRS / US GAAP"},
    {"code": "C-TX-002", "name": "Withholding Tax Shortfall", "process": "Tax",
     "risk": "Statutory non-compliance", "criticality": "High", "frequency": "Monthly",
     "owner_email": "compliance@onetouch.ai",
     "description": "Vendor invoices/receipts requiring WHT where amount withheld is below the statutory rate.",
     "framework": "Statutory; OECD"},
    {"code": "C-FA-001", "name": "Fixed Asset Depreciation Missing", "process": "Fixed Assets",
     "risk": "P&L understatement", "criticality": "Medium", "frequency": "Monthly",
     "owner_email": "gl.lead@onetouch.ai",
     "description": "In-service assets with no depreciation entry for the current open period.",
     "framework": "SOX 404; IAS 16"},
    {"code": "C-FA-002", "name": "Depreciation on Disposed Asset", "process": "Fixed Assets",
     "risk": "Asset overstatement", "criticality": "High", "frequency": "Monthly",
     "owner_email": "gl.lead@onetouch.ai",
     "description": "Depreciation entries booked for assets whose disposal has already been recorded.",
     "framework": "SOX 404; IAS 16"},
    {"code": "C-FA-003", "name": "CapEx Project Over Budget", "process": "Fixed Assets",
     "risk": "Unauthorized spend", "criticality": "High", "frequency": "Monthly",
     "owner_email": "controller@onetouch.ai",
     "description": "Capital projects whose actual-to-date spend exceeds approved budget without a change order.",
     "framework": "SOX 404"},
]


# --------- Phase 2 collections managed by this module ---------
PHASE2_COLLECTIONS = [
    "customers", "sales_orders", "ar_invoices", "customer_receipts",
    "employees", "payroll_runs", "payroll_entries",
    "bank_accounts", "bank_transactions", "fx_rates",
    "tax_filings", "withholding_records",
    "fixed_assets", "depreciation_schedules", "capex_projects",
]


def _rand_customer_name(i: int) -> str:
    a = ["Atlas", "Kingfisher", "Nimbus", "Solace", "Vertex", "Ember", "Quartz", "Beacon", "Luma", "Strata"]
    b = ["Retail", "Media", "Healthcare", "Energy", "Capital", "Foods", "Automotive", "Tech", "Biotech", "Logistics"]
    return f"{a[i % len(a)]} {b[(i // 10) % len(b)]} {['Inc', 'PLC', 'GmbH', 'Pte', 'Pvt'][i % 5]}"


def _rand_employee_name(i: int) -> str:
    first = ["Alex", "Sam", "Priya", "Noah", "Ivy", "Zara", "Ravi", "Maya", "Leo", "Kira",
             "Omar", "Talia", "Ben", "Nora", "Eli", "Juno", "Raj", "Ava", "Ines", "Theo"]
    last = ["Tan", "Novak", "Sharma", "Kaur", "Park", "Silva", "Oduya", "Yusuf", "Lindqvist",
            "Okafor", "Chen", "Abrams", "Khan", "Rossi", "Patel", "Dubois", "Moreno", "Haas"]
    return f"{first[i % len(first)]} {last[(i * 7) % len(last)]}"


def generate_phase2_data() -> Dict[str, List[dict]]:
    """Deterministic Phase 2 dataset."""
    random.seed(84)
    now = datetime.now(timezone.utc)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_period = (period_start - timedelta(days=1)).replace(day=1)

    # ---------- Customers ----------
    customers = []
    for i in range(40):
        entity = random.choice(ENTITY_CODES)
        credit_limit = random.choice([50_000, 150_000, 300_000, 750_000, 1_500_000])
        customers.append({
            "id": f"CUST-{1000+i}",
            "customer_code": f"CUST-{1000+i}",
            "customer_name": _rand_customer_name(i),
            "entity": entity,
            "credit_limit": credit_limit,
            "payment_terms_days": random.choice([15, 30, 45, 60]),
            "status": "active" if i < 38 else "on_hold",
            "created_at": _iso(now - timedelta(days=random.randint(180, 2000))),
        })

    # ---------- Sales Orders ----------
    sales_orders = []
    for i in range(120):
        c = random.choice(customers)
        amount = round(random.uniform(4_000, 260_000), 2)
        so_date = now - timedelta(days=random.randint(0, 90))
        sales_orders.append({
            "id": f"SO-{60000+i}",
            "so_number": f"SO-{60000+i}",
            "customer_id": c["id"],
            "customer_name": c["customer_name"],
            "entity": c["entity"],
            "amount": amount,
            "currency": "USD",
            "so_date": _iso(so_date),
            "ship_date": _iso(so_date + timedelta(days=random.randint(2, 14))),
            "status": random.choice(["open", "shipped", "billed"]),
        })

    # Inject 6 credit-limit breaches: pile large SOs onto a few customers
    for i in range(6):
        c = customers[i]
        sales_orders.append({
            "id": f"SO-BREACH-{i}",
            "so_number": f"SO-BREACH-{i}",
            "customer_id": c["id"],
            "customer_name": c["customer_name"],
            "entity": c["entity"],
            "amount": round(c["credit_limit"] * random.uniform(1.15, 1.85), 2),
            "currency": "USD",
            "so_date": _iso(now - timedelta(days=random.randint(1, 12))),
            "ship_date": _iso(now + timedelta(days=random.randint(2, 10))),
            "status": "open",
        })

    # ---------- AR Invoices ----------
    ar_invoices = []
    for i in range(220):
        c = random.choice(customers)
        amount = round(random.uniform(2_500, 180_000), 2)
        inv_date = now - timedelta(days=random.randint(1, 180))
        due_date = inv_date + timedelta(days=c["payment_terms_days"])
        paid = random.random() > 0.35
        ar_invoices.append({
            "id": f"AR-{80000+i}",
            "ar_number": f"AR-{80000+i}",
            "customer_id": c["id"],
            "customer_name": c["customer_name"],
            "entity": c["entity"],
            "amount": amount,
            "currency": "USD",
            "invoice_date": _iso(inv_date),
            "due_date": _iso(due_date),
            "shipment_date": _iso(inv_date - timedelta(days=random.randint(-2, 5))),
            "status": "paid" if paid else "open",
        })
    # 8 aged receivables > 90 days past due, still open
    for i in range(8):
        inv_date = now - timedelta(days=random.randint(120, 260))
        c = random.choice(customers)
        ar_invoices.append({
            "id": f"AR-AGED-{i}",
            "ar_number": f"AR-AGED-{i}",
            "customer_id": c["id"],
            "customer_name": c["customer_name"],
            "entity": c["entity"],
            "amount": round(random.uniform(20_000, 140_000), 2),
            "currency": "USD",
            "invoice_date": _iso(inv_date),
            "due_date": _iso(inv_date + timedelta(days=c["payment_terms_days"])),
            "shipment_date": _iso(inv_date - timedelta(days=1)),
            "status": "open",
        })
    # 4 cutoff-risk: invoice dated just before month-end, shipment after period-end
    for i in range(4):
        c = random.choice(customers)
        inv_date = prev_period.replace(day=28)  # near period-end
        ar_invoices.append({
            "id": f"AR-CUTOFF-{i}",
            "ar_number": f"AR-CUTOFF-{i}",
            "customer_id": c["id"],
            "customer_name": c["customer_name"],
            "entity": c["entity"],
            "amount": round(random.uniform(40_000, 200_000), 2),
            "currency": "USD",
            "invoice_date": _iso(inv_date),
            "due_date": _iso(inv_date + timedelta(days=c["payment_terms_days"])),
            "shipment_date": _iso(inv_date + timedelta(days=random.randint(5, 12))),  # ships AFTER invoice
            "status": "open",
        })

    # ---------- Customer Receipts ----------
    customer_receipts = []
    for i, inv in enumerate(ar_invoices[:160]):
        if inv["status"] == "paid":
            rec_date = datetime.fromisoformat(inv["invoice_date"]) + timedelta(days=random.randint(10, 70))
            customer_receipts.append({
                "id": f"RCP-{90000+i}",
                "receipt_number": f"RCP-{90000+i}",
                "customer_id": inv["customer_id"],
                "customer_name": inv["customer_name"],
                "ar_invoice_id": inv["id"],
                "entity": inv["entity"],
                "amount": inv["amount"],
                "currency": "USD",
                "receipt_date": _iso(rec_date),
                "bank_reference": f"ACH-{95000+i}",
            })

    # ---------- Employees ----------
    employees = []
    for i in range(45):
        entity = random.choice(ENTITY_CODES)
        terminated = i in (2, 17, 31, 39)  # 4 terminated
        employees.append({
            "id": f"EMP-{5000+i}",
            "employee_code": f"EMP-{5000+i}",
            "full_name": _rand_employee_name(i),
            "email": f"emp{5000+i}@onetouch.ai",
            "entity": entity,
            "department": random.choice(["Finance", "Ops", "Engineering", "Sales", "HR", "IT"]),
            "base_salary": round(random.uniform(40_000, 180_000), 2),
            "status": "terminated" if terminated else "active",
            "hired_at": _iso(now - timedelta(days=random.randint(90, 3500))),
            "terminated_at": _iso(now - timedelta(days=random.randint(10, 120))) if terminated else None,
        })

    # ---------- Payroll Runs + Entries ----------
    payroll_runs = []
    payroll_entries = []
    for m in range(3):  # last three payroll periods
        period = (now.replace(day=1) - timedelta(days=30 * m)).strftime("%Y-%m")
        run_id = f"PR-{period}"
        payroll_runs.append({
            "id": run_id,
            "period": period,
            "entity": "US-HQ",
            "run_date": _iso(now - timedelta(days=30 * m + 2)),
            "status": "posted",
            "total_gross": 0.0,
        })
        total = 0.0
        for emp in employees:
            # Skip terminated employees normally — but inject ghost-employee payments for the current period
            if emp["status"] == "terminated" and m > 0:
                continue
            gross = round(emp["base_salary"] / 12.0 * random.uniform(0.95, 1.1), 2)
            tax = round(gross * 0.28, 2)
            net = round(gross - tax, 2)
            entry_id = f"PE-{period}-{emp['id']}"
            payroll_entries.append({
                "id": entry_id,
                "payroll_run_id": run_id,
                "period": period,
                "employee_id": emp["id"],
                "employee_name": emp["full_name"],
                "entity": emp["entity"],
                "gross_amount": gross,
                "tax_amount": tax,
                "net_amount": net,
                "status": "paid",
            })
            total += gross
        payroll_runs[-1]["total_gross"] = round(total, 2)

    # Inject 2 ghost-employee payments in the current period
    current_period = (now.replace(day=1)).strftime("%Y-%m")
    ghosts = [e for e in employees if e["status"] == "terminated"][:2]
    for g in ghosts:
        payroll_entries.append({
            "id": f"PE-{current_period}-{g['id']}-GHOST",
            "payroll_run_id": f"PR-{current_period}",
            "period": current_period,
            "employee_id": g["id"],
            "employee_name": g["full_name"],
            "entity": g["entity"],
            "gross_amount": round(g["base_salary"] / 12.0, 2),
            "tax_amount": round(g["base_salary"] / 12.0 * 0.28, 2),
            "net_amount": round(g["base_salary"] / 12.0 * 0.72, 2),
            "status": "paid",
        })

    # Inject 2 duplicate payroll entries (same employee, same period)
    for emp in employees[:2]:
        base = next((p for p in payroll_entries if p["employee_id"] == emp["id"] and p["period"] == current_period), None)
        if base:
            dup = dict(base)
            dup["id"] = base["id"] + "-DUP"
            payroll_entries.append(dup)

    # ---------- Treasury ----------
    bank_accounts = []
    for i, ent in enumerate(ENTITY_CODES):
        bank_accounts.append({
            "id": f"BA-{ent}",
            "entity": ent,
            "bank_name": random.choice(["Citibank", "HSBC", "DBS", "Barclays"]),
            "account_number_masked": f"****{1000+i}",
            "currency": random.choice(["USD", "GBP", "INR", "SGD"]),
            "status": "active",
            "balance": round(random.uniform(500_000, 8_000_000), 2),
        })

    bank_transactions = []
    for i in range(200):
        ba = random.choice(bank_accounts)
        ts = now - timedelta(days=random.randint(0, 45), hours=random.randint(0, 23), minutes=random.randint(0, 59))
        amount = round(random.uniform(5_000, 200_000), 2)
        bank_transactions.append({
            "id": f"BT-{40000+i}",
            "bank_account_id": ba["id"],
            "entity": ba["entity"],
            "txn_ts": _iso(ts),
            "amount": amount,
            "direction": random.choice(["outbound", "inbound"]),
            "counterparty": random.choice([c["customer_name"] for c in customers[:5]] + ["Vendor " + str(j) for j in range(5)]),
            "reference": f"WIRE-{70000+i}",
            "currency": ba["currency"],
        })
    # Inject 5 off-hours large outbound transfers (weekend or <07:00/>19:00 UTC)
    for i in range(5):
        ba = random.choice(bank_accounts)
        # Saturday at 03:00 UTC
        base = now - timedelta(days=(now.weekday() + 2) % 7)  # roll to previous Saturday
        ts = base.replace(hour=3, minute=12)
        bank_transactions.append({
            "id": f"BT-OFF-{i}",
            "bank_account_id": ba["id"],
            "entity": ba["entity"],
            "txn_ts": _iso(ts - timedelta(days=7 * i)),
            "amount": round(random.uniform(300_000, 850_000), 2),
            "direction": "outbound",
            "counterparty": f"Counterparty Unknown {i}",
            "reference": f"WIRE-OFF-{i}",
            "currency": ba["currency"],
        })

    fx_rates = []
    for days_back in range(45):
        day = (now - timedelta(days=days_back)).date().isoformat()
        for pair, mid in [("USD/GBP", 0.79), ("USD/INR", 83.2), ("USD/SGD", 1.34)]:
            fx_rates.append({
                "id": f"FX-{day}-{pair.replace('/', '-')}",
                "pair": pair,
                "date": day,
                "mid_rate": round(mid * random.uniform(0.995, 1.005), 4),
                "source": "Reuters",
            })
    # Inject 3 deviation rates used in journals (tracked separately)
    fx_journal_usage = [
        {"id": "FXJ-1", "journal_ref": "JE-TX-001", "pair": "USD/GBP", "rate_used": 0.84, "date": now.date().isoformat(), "entity": "UK-OPS", "booked_amount": 210_000},
        {"id": "FXJ-2", "journal_ref": "JE-TX-002", "pair": "USD/INR", "rate_used": 79.1, "date": now.date().isoformat(), "entity": "IN-SVC", "booked_amount": 145_000},
        {"id": "FXJ-3", "journal_ref": "JE-TX-003", "pair": "USD/SGD", "rate_used": 1.41, "date": now.date().isoformat(), "entity": "SG-APAC", "booked_amount": 98_000},
    ]
    # Stored inside fx_rates collection under type flag so seed stays small
    for f in fx_journal_usage:
        f["type"] = "journal_usage"
        fx_rates.append(f)

    # ---------- Tax ----------
    tax_filings = []
    for i in range(8):
        due = now - timedelta(days=random.randint(-10, 40))
        tax_filings.append({
            "id": f"TF-{1000+i}",
            "entity": random.choice(ENTITY_CODES),
            "filing_type": random.choice(["VAT", "GST", "Corporate Income Tax", "Payroll Tax"]),
            "period": (now.replace(day=1) - timedelta(days=30)).strftime("%Y-%m"),
            "due_date": _iso(due),
            "filed_date": _iso(due - timedelta(days=2)) if random.random() > 0.3 else None,
            "amount": round(random.uniform(30_000, 450_000), 2),
            "status": random.choice(["filed", "pending", "overdue"]),
        })

    withholding_records = []
    for i in range(60):
        required_rate = random.choice([0.05, 0.10, 0.15])
        required = round(random.uniform(5_000, 80_000) * required_rate, 2)
        shortfall = random.random() < 0.15
        withheld = required if not shortfall else round(required * random.uniform(0.3, 0.75), 2)
        withholding_records.append({
            "id": f"WHT-{2000+i}",
            "entity": random.choice(ENTITY_CODES),
            "vendor_id": f"V-{1000 + random.randint(0, 59)}",
            "invoice_ref": f"INV-{20000 + random.randint(0, 499)}",
            "required_rate": required_rate,
            "required_amount": required,
            "withheld_amount": withheld,
            "period": (now.replace(day=1) - timedelta(days=30)).strftime("%Y-%m"),
            "booked_at": _iso(now - timedelta(days=random.randint(0, 60))),
        })

    # ---------- Fixed Assets ----------
    fixed_assets = []
    for i in range(30):
        in_service_date = now - timedelta(days=random.randint(180, 3000))
        cost = round(random.uniform(25_000, 1_200_000), 2)
        useful_life_months = random.choice([36, 60, 84, 120])
        disposed = i in (7, 19)
        fixed_assets.append({
            "id": f"FA-{3000+i}",
            "asset_code": f"FA-{3000+i}",
            "asset_name": random.choice(["Server Rack", "Office Fitout", "Vehicle Fleet", "Factory Line",
                                         "Laptop Batch", "HVAC System", "Testing Rig"]) + f" #{i}",
            "entity": random.choice(ENTITY_CODES),
            "category": random.choice(["IT Hardware", "Buildings", "Vehicles", "Plant & Machinery", "Furniture"]),
            "cost": cost,
            "useful_life_months": useful_life_months,
            "in_service_date": _iso(in_service_date),
            "status": "disposed" if disposed else "in_service",
            "disposed_at": _iso(now - timedelta(days=random.randint(30, 180))) if disposed else None,
            "monthly_depreciation": round(cost / useful_life_months, 2),
        })

    depreciation_schedules = []
    current_period = (now.replace(day=1)).strftime("%Y-%m")
    for a in fixed_assets:
        # Depreciation entries for last two periods
        for m in (1, 2):
            period = (now.replace(day=1) - timedelta(days=30 * m)).strftime("%Y-%m")
            # Skip 3 in-service assets' current month to seed "Depreciation Missing"
            if m == 1 and a["id"] in ("FA-3002", "FA-3011", "FA-3024") and a["status"] == "in_service":
                continue
            depreciation_schedules.append({
                "id": f"DEP-{a['id']}-{period}",
                "asset_id": a["id"],
                "period": period,
                "amount": a["monthly_depreciation"],
                "entity": a["entity"],
                "posted_at": _iso(now - timedelta(days=30 * m)),
            })
    # Inject depreciation entries that should NOT exist — disposed assets depreciated this period
    for a in fixed_assets:
        if a["status"] == "disposed":
            depreciation_schedules.append({
                "id": f"DEP-BAD-{a['id']}-{current_period}",
                "asset_id": a["id"],
                "period": current_period,
                "amount": a["monthly_depreciation"],
                "entity": a["entity"],
                "posted_at": _iso(now - timedelta(days=2)),
            })

    # ---------- CapEx projects ----------
    capex_projects = []
    for i in range(10):
        budget = round(random.uniform(200_000, 3_500_000), 2)
        over_budget = i < 3
        actual = round(budget * (random.uniform(1.08, 1.35) if over_budget else random.uniform(0.3, 0.95)), 2)
        capex_projects.append({
            "id": f"CPX-{4000+i}",
            "project_code": f"CPX-{4000+i}",
            "project_name": random.choice(["Warehouse Expansion", "ERP Upgrade", "Data Center", "Fleet Renewal",
                                           "Office Reno", "R&D Lab", "Solar Panels"]) + f" Phase {i+1}",
            "entity": random.choice(ENTITY_CODES),
            "budget_amount": budget,
            "actual_amount": actual,
            "start_date": _iso(now - timedelta(days=random.randint(90, 500))),
            "status": "in_progress" if i < 6 else "completed",
            "sponsor": "controller@onetouch.ai",
        })

    return {
        "customers": customers,
        "sales_orders": sales_orders,
        "ar_invoices": ar_invoices,
        "customer_receipts": customer_receipts,
        "employees": employees,
        "payroll_runs": payroll_runs,
        "payroll_entries": payroll_entries,
        "bank_accounts": bank_accounts,
        "bank_transactions": bank_transactions,
        "fx_rates": fx_rates,
        "tax_filings": tax_filings,
        "withholding_records": withholding_records,
        "fixed_assets": fixed_assets,
        "depreciation_schedules": depreciation_schedules,
        "capex_projects": capex_projects,
    }


async def seed_phase2(db, force: bool = False) -> Dict[str, Any]:
    """Idempotent Phase 2 seeding.

    Ensures all Phase 2 collections, Phase 2 controls, and Fixed Assets process exist.
    Safe to run on an existing Phase 1 DB — will only insert what is missing.
    """
    actions: Dict[str, Any] = {}

    # 1) Seed collections if empty
    if force:
        for c in PHASE2_COLLECTIONS:
            await db[c].delete_many({})
        # Remove any previously seeded Phase 2 controls so they are re-inserted
        await db.controls.delete_many({"code": {"$in": [c["code"] for c in CONTROLS_PHASE2]}})

    needs_data = await db.customers.count_documents({}) == 0
    if needs_data:
        data = generate_phase2_data()
        inserted = {}
        for coll, docs in data.items():
            if docs:
                await db[coll].insert_many([dict(d) for d in docs])
                inserted[coll] = len(docs)
        actions["phase2_seeded"] = inserted
    else:
        actions["phase2_seeded"] = "already_present"

    # 2) Upsert Phase 2 controls idempotently (only when missing)
    added_controls = 0
    now_iso = _iso(datetime.now(timezone.utc))
    for c in CONTROLS_PHASE2:
        existing = await db.controls.find_one({"code": c["code"]}, {"_id": 0})
        if not existing:
            await db.controls.insert_one({
                "id": str(uuid.uuid4()),
                **c,
                "active": True,
                "last_run_at": None,
                "last_run_pass": None,
                "last_run_exceptions": None,
                "version": 1,
                "created_at": now_iso,
            })
            added_controls += 1
    actions["phase2_controls_added"] = added_controls

    return actions
