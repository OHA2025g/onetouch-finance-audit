"""Synthetic data seeder + reset. All date strings ISO format."""
from __future__ import annotations
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from .auth import hash_password


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


# ----- Fixed reference data -----
ENTITIES = [
    {"code": "US-HQ", "name": "OneTouch Global, Inc. (US HQ)", "geo": "US"},
    {"code": "UK-OPS", "name": "OneTouch UK Operations Ltd", "geo": "UK"},
    {"code": "IN-SVC", "name": "OneTouch India Services Pvt Ltd", "geo": "IN"},
    {"code": "SG-APAC", "name": "OneTouch APAC Holdings Pte", "geo": "SG"},
]

PROCESSES = ["Procure-to-Pay", "Record-to-Report", "Order-to-Cash", "Payroll", "Treasury", "Tax", "Access/SoD"]

USERS_SEED = [
    {"email": "system@onetouch.ai", "full_name": "System (platform automation)", "role": "Service account", "entity": "US-HQ"},
    {"email": "superadmin@onetouch.ai", "full_name": "Alex Rivera", "role": "Super Admin", "entity": "US-HQ"},
    {"email": "cfo@onetouch.ai", "full_name": "Marion Acheson", "role": "CFO", "entity": "US-HQ"},
    {"email": "controller@onetouch.ai", "full_name": "Derek Whitmore", "role": "Controller", "entity": "US-HQ"},
    {"email": "auditor@onetouch.ai", "full_name": "Priya Rangan", "role": "Internal Auditor", "entity": "US-HQ"},
    {"email": "compliance@onetouch.ai", "full_name": "Tomás Leiva", "role": "Compliance Head", "entity": "UK-OPS"},
    {"email": "owner@onetouch.ai", "full_name": "Sana Kibet", "role": "Process Owner", "entity": "IN-SVC"},
    {"email": "ap.clerk@onetouch.ai", "full_name": "Ravi Subramanian", "role": "Process Owner", "entity": "IN-SVC"},
    {"email": "gl.lead@onetouch.ai", "full_name": "Anneli Jansen", "role": "Process Owner", "entity": "UK-OPS"},
    {"email": "external.auditor@bigfour.example", "full_name": "Hannah Oduya", "role": "External Auditor", "entity": "US-HQ"},
]

# 12 controls
CONTROLS_SEED = [
    {"code": "C-AP-001", "name": "Duplicate Invoice Detection", "process": "Procure-to-Pay", "risk": "Duplicate payment / leakage",
     "criticality": "High", "frequency": "Daily", "owner_email": "ap.clerk@onetouch.ai",
     "description": "Detect invoices with identical vendor, amount, and invoice number (or near-duplicate within 3 days).",
     "framework": "SOX ITGC; COSO"},
    {"code": "C-AP-002", "name": "Duplicate Payment Detection", "process": "Procure-to-Pay", "risk": "Duplicate payment",
     "criticality": "Critical", "frequency": "Daily", "owner_email": "ap.clerk@onetouch.ai",
     "description": "Identify payments that share vendor, amount, and reference within a short window.",
     "framework": "SOX; COSO"},
    {"code": "C-AP-003", "name": "3-Way Match Exception", "process": "Procure-to-Pay", "risk": "Unauthorized spend",
     "criticality": "High", "frequency": "Daily", "owner_email": "ap.clerk@onetouch.ai",
     "description": "Invoice amount must match PO and GRN within tolerance.",
     "framework": "SOX 404"},
    {"code": "C-GL-001", "name": "Manual Journals Above Threshold", "process": "Record-to-Report", "risk": "Fraud / misstatement",
     "criticality": "High", "frequency": "Daily", "owner_email": "gl.lead@onetouch.ai",
     "description": "Manual journal entries over USD 100,000 require secondary approval evidence.",
     "framework": "SOX 404"},
    {"code": "C-GL-002", "name": "Backdated Journal Posting", "process": "Record-to-Report", "risk": "Period manipulation",
     "criticality": "Critical", "frequency": "Daily", "owner_email": "gl.lead@onetouch.ai",
     "description": "Flag journals posted after period cutoff with a posting date in a closed period.",
     "framework": "SOX 404; IFRS"},
    {"code": "C-GL-003", "name": "Privileged User Journal Activity", "process": "Record-to-Report", "risk": "SoD breach",
     "criticality": "High", "frequency": "Daily", "owner_email": "gl.lead@onetouch.ai",
     "description": "Privileged system users posting material journals without independent review.",
     "framework": "SOX ITGC"},
    {"code": "C-AP-004", "name": "Approval Bypass / Missing Approver", "process": "Procure-to-Pay", "risk": "Approval override",
     "criticality": "High", "frequency": "Daily", "owner_email": "ap.clerk@onetouch.ai",
     "description": "Invoices paid without a documented approver above threshold.",
     "framework": "COSO"},
    {"code": "C-ACC-001", "name": "Inactive / Terminated User Activity", "process": "Access/SoD", "risk": "Unauthorized access",
     "criticality": "Critical", "frequency": "Daily", "owner_email": "compliance@onetouch.ai",
     "description": "System activity from terminated or dormant users over the last 14 days.",
     "framework": "SOX ITGC; ISO27001"},
    {"code": "C-ACC-002", "name": "Segregation of Duties Conflict", "process": "Access/SoD", "risk": "Fraud risk",
     "criticality": "High", "frequency": "Weekly", "owner_email": "compliance@onetouch.ai",
     "description": "Users holding incompatible finance-sensitive roles (e.g., create vendor + approve payment).",
     "framework": "SOX 404"},
    {"code": "C-TR-001", "name": "Unreconciled Bank/GL Balances", "process": "Treasury", "risk": "Cash misstatement",
     "criticality": "High", "frequency": "Weekly", "owner_email": "controller@onetouch.ai",
     "description": "Reconciliations past due or with unresolved variances above tolerance.",
     "framework": "SOX 404"},
    {"code": "C-TX-001", "name": "GST / Tax Mismatch", "process": "Tax", "risk": "Compliance exposure",
     "criticality": "Medium", "frequency": "Monthly", "owner_email": "compliance@onetouch.ai",
     "description": "Invoices where computed tax differs from expected rate by more than tolerance.",
     "framework": "Statutory"},
    {"code": "C-AP-005", "name": "Vendor Bank Account Recently Changed", "process": "Procure-to-Pay", "risk": "Payment fraud",
     "criticality": "Critical", "frequency": "Daily", "owner_email": "ap.clerk@onetouch.ai",
     "description": "Payments to vendors whose bank account was changed within the last 14 days.",
     "framework": "SOX; AFP"},
]

POLICIES_SEED = [
    {"title": "Global AP Payment Policy v4.2", "effective": "2025-01-01", "clauses": ["2.1 Dual approval > USD 50,000", "4.3 Vendor bank change 14d cool-off"]},
    {"title": "Manual Journal Entry Policy v3.0", "effective": "2025-02-15", "clauses": ["3.1 JEs > USD 100k require reviewer sign-off", "5.2 No postings after close cutoff"]},
    {"title": "Segregation of Duties Matrix v2.1", "effective": "2024-11-01", "clauses": ["Vendor Master + Payment Approver = FORBIDDEN", "JE Post + JE Approve = FORBIDDEN"]},
    {"title": "IT General Controls — Access Policy v5.0", "effective": "2025-03-01", "clauses": ["6.2 Terminated users deactivated within 24h", "6.4 Dormant accounts locked after 90d"]},
]


def _rand_vendor_name(i: int) -> str:
    parts_a = ["Apex", "Harbor", "Brightline", "Northwind", "Sable", "Meridian", "Delphi", "Cascade", "Ridgeback", "Pinnacle"]
    parts_b = ["Logistics", "Systems", "Chemicals", "Marketing", "Industries", "Partners", "Mechanicals", "Analytics", "Trading", "Foods"]
    return f"{parts_a[i % len(parts_a)]} {parts_b[(i // 10) % len(parts_b)]} {['Ltd','LLC','GmbH','Pte','Pvt'][i % 5]}"


def generate_synthetic_data() -> Dict[str, list]:
    """Return a dict of documents ready to insert. Deterministic via fixed seed for demo."""
    random.seed(42)
    now = datetime.now(timezone.utc)

    vendors = []
    for i in range(60):
        entity = random.choice(ENTITIES)["code"]
        bank_changed_recent = i in (3, 7, 14, 22, 31)  # flag 5 suspicious
        changed_at = now - timedelta(days=random.randint(1, 10) if bank_changed_recent else random.randint(60, 900))
        # Deterministic master-DQ fields: introduce missing and duplicates intentionally.
        has_tax = i % 7 != 0  # ~14% missing PAN/GSTIN
        pan = f"PAN{i:05d}" if has_tax and (i % 2 == 0) else None
        gstin = f"GSTIN{i:05d}" if has_tax and (i % 3 != 0) else None
        # Force duplicates: two vendors share same PAN and GSTIN
        if i in (10, 11):
            pan = "PAN-DUP-00001"
        if i in (12, 13):
            gstin = "GSTIN-DUP-00001"
        bank_masked = f"XXXXXX{1000 + i:04d}" if i % 5 != 0 else None
        ifsc = f"IFSC{i:05d}" if (bank_masked and i % 6 != 0) else None
        vendors.append({
            "id": f"V-{1000+i}",
            "vendor_code": f"V-{1000+i}",
            "vendor_name": _rand_vendor_name(i),
            "entity": entity,
            "bank_account_hash": f"HASH{(i*37) % 99999:05d}",
            "bank_account_number_masked": bank_masked,
            "ifsc": ifsc,
            "pan": pan,
            "gstin": gstin,
            "bank_changed_at": _iso(changed_at),
            "status": "active" if i < 56 else "inactive",
            "created_at": _iso(now - timedelta(days=random.randint(200, 1500))),
        })

    # Invoices: 500. Seed duplicates + tax mismatches.
    invoices = []
    for i in range(500):
        v = random.choice(vendors)
        amount = round(random.uniform(500, 120_000), 2)
        tax_rate = 0.18
        expected_tax = round(amount * tax_rate, 2)
        # Introduce a tax mismatch ~ 8% of the time
        actual_tax = expected_tax if random.random() > 0.08 else round(expected_tax * random.uniform(0.4, 0.9), 2)
        inv_date = now - timedelta(days=random.randint(1, 120))
        invoices.append({
            "id": f"INV-{20000+i}",
            "invoice_number": f"INV-{20000+i}",
            "vendor_id": v["id"],
            "vendor_name": v["vendor_name"],
            "entity": v["entity"],
            "invoice_date": _iso(inv_date),
            "amount": amount,
            "tax_amount": actual_tax,
            "expected_tax_amount": expected_tax,
            "status": random.choice(["posted", "paid", "open"]),
            "po_id": None,
            "approver_email": random.choice([None, "controller@onetouch.ai", "gl.lead@onetouch.ai"]) if amount < 50000 else random.choice([None, "controller@onetouch.ai"]),
            "created_at": _iso(inv_date),
        })
    # Inject 12 exact-duplicate invoices (same vendor, amount, invoice_number)
    for i in range(12):
        base = invoices[i * 3]
        dup = dict(base)
        dup["id"] = f"INV-DUP-{i}"
        dup["created_at"] = _iso(now - timedelta(days=random.randint(0, 5)))
        invoices.append(dup)

    # Purchase Orders + GRNs, with a few 3-way mismatches
    purchase_orders = []
    goods_receipts = []
    for i, inv in enumerate(invoices[:200]):
        po_amount = inv["amount"] if random.random() > 0.06 else round(inv["amount"] * random.uniform(0.6, 0.85), 2)
        po = {
            "id": f"PO-{50000+i}",
            "po_number": f"PO-{50000+i}",
            "vendor_id": inv["vendor_id"],
            "vendor_name": inv["vendor_name"],
            "entity": inv["entity"],
            "amount": po_amount,
            "po_date": _iso(datetime.fromisoformat(inv["invoice_date"]) - timedelta(days=5)),
            "status": "closed",
        }
        purchase_orders.append(po)
        grn_amount = po_amount if random.random() > 0.05 else round(po_amount * random.uniform(0.7, 0.95), 2)
        goods_receipts.append({
            "id": f"GRN-{70000+i}",
            "grn_number": f"GRN-{70000+i}",
            "po_id": po["id"],
            "vendor_id": inv["vendor_id"],
            "entity": inv["entity"],
            "amount": grn_amount,
            "receipt_date": _iso(datetime.fromisoformat(inv["invoice_date"]) - timedelta(days=2)),
        })
        inv["po_id"] = po["id"]

    # Payments -- seed duplicates
    payments = []
    for i, inv in enumerate(invoices[:280]):
        if inv["status"] in ("paid",):
            pay = {
                "id": f"PAY-{80000+i}",
                "vendor_id": inv["vendor_id"],
                "vendor_name": inv["vendor_name"],
                "invoice_id": inv["id"],
                "entity": inv["entity"],
                "amount": inv["amount"],
                "payment_date": _iso(datetime.fromisoformat(inv["invoice_date"]) + timedelta(days=random.randint(10, 45))),
                "bank_reference": f"WIRE-{90000+i}",
            }
            payments.append(pay)
    # Duplicate payments
    for i in range(6):
        base = payments[i * 4]
        dup = dict(base)
        dup["id"] = f"PAY-DUP-{i}"
        dup["bank_reference"] = f"{base['bank_reference']}-D"
        payments.append(dup)

    # Journals
    journals = []
    privileged_posters = {"sysadmin@onetouch.ai", "gl.lead@onetouch.ai"}
    period_cutoff = now - timedelta(days=8)  # "current close cutoff"
    for i in range(220):
        amount = round(random.uniform(10_000, 450_000), 2)
        posting_date = now - timedelta(days=random.randint(0, 60))
        # Introduce some backdated (posting_date far before created_at → posted after cutoff into closed period)
        created_at = posting_date + timedelta(days=random.randint(0, 30))
        is_manual = random.random() > 0.55
        poster = random.choice(["controller@onetouch.ai", "gl.lead@onetouch.ai", "sysadmin@onetouch.ai", "ap.clerk@onetouch.ai"])
        journals.append({
            "id": f"JE-{30000+i}",
            "journal_number": f"JE-{30000+i}",
            "entity": random.choice(ENTITIES)["code"],
            "posting_date": _iso(posting_date),
            "created_at": _iso(created_at),
            "created_by": poster,
            "is_manual": is_manual,
            "is_privileged_poster": poster in privileged_posters,
            "total_amount": amount,
            "approver_email": random.choice([None, "controller@onetouch.ai"]),
            "description": random.choice(["Accrual adj.", "Intercompany reclass", "Reversal", "Top-side entry", "Adjustment"]),
        })
    # Inject clear violations
    for i in range(5):
        journals[i]["is_manual"] = True
        journals[i]["total_amount"] = round(random.uniform(150_000, 400_000), 2)
        journals[i]["approver_email"] = None  # threshold breach
    for i in range(5, 10):
        journals[i]["posting_date"] = _iso(period_cutoff - timedelta(days=random.randint(3, 20)))
        journals[i]["created_at"] = _iso(now - timedelta(days=random.randint(0, 4)))  # created after cutoff

    # Reconciliations
    reconciliations = []
    for i in range(24):
        entity = random.choice(ENTITIES)["code"]
        variance = round(random.uniform(-80000, 80000), 2) if random.random() > 0.6 else 0.0
        due = now - timedelta(days=random.randint(-5, 15))
        reconciliations.append({
            "id": f"REC-{40000+i}",
            "entity": entity,
            "reconciliation_type": random.choice(["Bank", "GL-Suspense", "Intercompany", "AR"]),
            "period": (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m"),
            "status": "overdue" if due < now and abs(variance) > 5000 else random.choice(["open", "closed"]),
            "variance_amount": variance,
            "due_date": _iso(due),
            "tolerance": 5000,
        })

    # ---- Phase 2 masters needed by /api/masters/* endpoints ----
    customers = []
    for i in range(40):
        ent = ENTITIES[i % len(ENTITIES)]["code"]
        customers.append(
            {
                "id": f"C-{2000+i}",
                "customer_code": f"CUST-{2000+i}",
                "customer_name": f"Customer {i+1:02d} · {ent}",
                "entity": ent,
                "status": "active" if i < 36 else "inactive",
                "credit_limit": 50_000 + (i % 10) * 25_000,
                "gstin": f"CUSTGST{i:05d}" if i % 6 != 0 else None,
                "created_at": _iso(now - timedelta(days=random.randint(30, 900))),
            }
        )

    employees = []
    for i in range(30):
        ent = ENTITIES[i % len(ENTITIES)]["code"]
        employees.append(
            {
                "id": f"E-{3000+i}",
                "employee_code": f"EMP-{3000+i}",
                "full_name": f"Employee {i+1:02d}",
                "email": f"emp{i+1:02d}@onetouch.ai",
                "entity": ent,
                # department name maps via master_departments in finance_masters_seed
                "department": random.choice(["Finance", "Operations", "Engineering", "Sales", "HR", "IT"]),
                "status": "active" if i < 28 else "inactive",
                "created_at": _iso(now - timedelta(days=random.randint(30, 900))),
            }
        )

    bank_accounts = []
    for i, e in enumerate(ENTITIES):
        bank_accounts.append(
            {
                "id": f"BA-{100+i}",
                "entity": e["code"],
                "bank_name": random.choice(["HSBC", "Citi", "ICICI", "Barclays"]),
                "currency": "USD" if e["code"] in ("US-HQ", "SG-APAC") else ("GBP" if e["code"] == "UK-OPS" else "INR"),
                "account_number_masked": f"XXXXXX{9000+i}",
                "created_at": _iso(now - timedelta(days=365)),
            }
        )

    # Access events (dormant/terminated)
    user_access_events = []
    for i in range(40):
        email = random.choice(["exemp@onetouch.ai", "jdoe@onetouch.ai", "old.user@onetouch.ai", "controller@onetouch.ai", "ap.clerk@onetouch.ai"])
        terminated = email in ("exemp@onetouch.ai", "old.user@onetouch.ai")
        user_access_events.append({
            "id": f"UA-{i}",
            "user_email": email,
            "entity": random.choice(ENTITIES)["code"],
            "system": random.choice(["ERP", "Banking", "HRMS"]),
            "event_type": random.choice(["login", "post_journal", "approve", "create_vendor"]),
            "event_ts": _iso(now - timedelta(days=random.randint(0, 13))),
            "user_terminated": terminated,
        })

    # SoD role assignments
    sod_role_map = [
        {"user_email": "ap.clerk@onetouch.ai", "role": "Vendor Master Maintainer", "entity": "IN-SVC"},
        {"user_email": "ap.clerk@onetouch.ai", "role": "Payment Approver", "entity": "IN-SVC"},  # conflict
        {"user_email": "gl.lead@onetouch.ai", "role": "JE Poster", "entity": "UK-OPS"},
        {"user_email": "gl.lead@onetouch.ai", "role": "JE Approver", "entity": "UK-OPS"},  # conflict
        {"user_email": "controller@onetouch.ai", "role": "JE Approver", "entity": "US-HQ"},
        {"user_email": "owner@onetouch.ai", "role": "Requisitioner", "entity": "IN-SVC"},
    ]
    sod_forbidden = [
        ("Vendor Master Maintainer", "Payment Approver"),
        ("JE Poster", "JE Approver"),
    ]

    # Users (with pre-hashed password)
    pwd_hash = hash_password("demo1234")
    users = []
    for u in USERS_SEED:
        users.append({
            "id": str(uuid.uuid4()),
            "email": u["email"],
            "full_name": u["full_name"],
            "role": u["role"],
            "entity": u["entity"],
            "password_hash": pwd_hash,
            "status": "active",
            "created_at": _iso(now - timedelta(days=400)),
        })

    # Controls
    controls = []
    for c in CONTROLS_SEED:
        controls.append({
            "id": str(uuid.uuid4()),
            **c,
            "active": True,
            "last_run_at": None,
            "last_run_pass": None,
            "last_run_exceptions": None,
            "version": 1,
        })

    # Policies
    policies = []
    for i, p in enumerate(POLICIES_SEED):
        policies.append({
            "id": f"POL-{100+i}",
            "title": p["title"],
            "effective_date": p["effective"],
            "clauses": p["clauses"],
            "storage_uri": f"s3://onetouch-audit/policies/POL-{100+i}.pdf",
        })

    return {
        "entities": [{**e, "id": e["code"]} for e in ENTITIES],
        "users": users,
        "vendors": vendors,
        "customers": customers,
        "employees": employees,
        "bank_accounts": bank_accounts,
        "invoices": invoices,
        "purchase_orders": purchase_orders,
        "goods_receipts": goods_receipts,
        "payments": payments,
        "journals": journals,
        "reconciliations": reconciliations,
        "user_access_events": user_access_events,
        "sod_role_map": sod_role_map,
        "sod_forbidden": [{"a": a, "b": b} for a, b in sod_forbidden],
        "controls": controls,
        "policies": policies,
    }


COLLECTIONS = [
    "entities", "users", "vendors", "invoices", "purchase_orders", "goods_receipts",
    "payments", "journals", "reconciliations", "user_access_events", "sod_role_map",
    "sod_forbidden", "controls", "policies",
    # Phase 2 domain data:
    "customers", "sales_orders", "ar_invoices", "customer_receipts",
    "employees", "payroll_runs", "payroll_entries",
    "bank_accounts", "bank_transactions", "fx_rates",
    "tax_filings", "withholding_records",
    "fixed_assets", "depreciation_schedules", "capex_projects",
    # Runtime:
    "test_runs", "exceptions", "cases", "case_comments", "case_status_history",
    "evidence_links", "audit_logs", "copilot_sessions", "readiness_scores",
    "ingestion_runs", "model_registry", "prompt_registry",
    "notification_settings", "notifications",
    "organization_hierarchy", "entity_group_map", "reporting_currency_rates", "rollup_snapshots", "rollup_snapshot_history",
    "retention_policies", "artifact_retention_map", "purge_jobs",
    "legal_holds", "hold_artifact_links", "worm_protected_records",
    "source_connectors", "connector_runs", "connector_errors", "connector_schemas", "connector_credentials_ref",
    "tax_records",
    "embedding_index_runs", "embedding_chunks", "embedding_metadata", "retrieval_config_versions",
    "approval_requests", "approval_decisions", "governance_policy_versions",
    # Slice 4 — month-end close:
    "close_task_templates", "close_cycles", "close_tasks", "close_events",
    # CA statutory / engagement modules:
    "audit_engagements",
    "ca_materiality",
    "ca_risks",
    "ca_risk_control_map",
    "ca_trial_balance",
    "ca_trial_balance_lines",
    "ca_fs_snapshots",
    "ca_audit_adjustments",
    "ca_schedule_audit",
    "ca_control_library",
    "ca_control_tests",
    "ca_control_deficiencies",
    "ca_control_certifications",
    "ca_working_papers",
    "ca_audit_evidence",
    "ca_wp_folders",
    "ca_wp_review_notes",
    "ca_wp_signoffs",
    "ca_sampling_plans",
    "ca_sample_transactions",
    "ca_vouching_items",
    "ca_compliance_results",
    "ca_compliance_findings",
    "ca_gst_rec",
    "ca_tds_rec",
    "ca_caro_state",
    "ca_tax44_state",
    "ca_caro_responses",
    "ca_audit_observations",
    "ca_audit_findings",
    "ca_audit_opinions",
    "ca_final_reports",
    "ca_management_letters",
    "ca_mgmt_repr",
    "ca_assurance_snapshots",
    # Phase 2 unified finance masters (additive; not dropped on routine reseed):
    "companies",
    "master_business_units",
    "master_locations",
    "master_departments",
    "master_cost_centers",
    "master_gl_accounts",
    "master_transaction_lines",
    "master_documents",
    "finance_risk_scores",
    "master_data_audit_trail",
]


async def seed_database(db, force: bool = False) -> Dict[str, int]:
    """Seed DB. If `force`, wipes all managed collections first."""
    if force:
        for c in COLLECTIONS:
            await db[c].delete_many({})

    existing_users = await db.users.count_documents({})
    if existing_users > 0 and not force:
        return {"status": "already_seeded"}

    data = generate_synthetic_data()
    counts = {}
    for coll, docs in data.items():
        if docs:
            await db[coll].insert_many([dict(d) for d in docs])
            counts[coll] = len(docs)

    # Seed model + prompt registry
    now_iso = _iso(datetime.now(timezone.utc))
    await db.model_registry.insert_many([
        {"id": "M-001", "model_name": "gemini-3-flash-preview", "provider": "gemini", "use_case": "copilot_qa",
         "governance_tier": "tier-2", "approval_status": "approved", "approved_by": "compliance@onetouch.ai", "approved_at": now_iso, "active": True},
        {"id": "M-002", "model_name": "statistical-zscore-v1", "provider": "internal", "use_case": "anomaly_scoring",
         "governance_tier": "tier-1", "approval_status": "approved", "approved_by": "auditor@onetouch.ai", "approved_at": now_iso, "active": True},
    ])
    await db.prompt_registry.insert_many([
        {"id": "P-001", "name": "copilot_qa_system_v1", "version": 1, "approved_by": "compliance@onetouch.ai",
         "approved_at": now_iso, "template": "You are a finance audit assistant. Cite every fact. Flag material conclusions for human review.", "active": True},
        {"id": "P-002", "name": "audit_committee_narrative_v1", "version": 1, "approved_by": "cfo@onetouch.ai",
         "approved_at": now_iso, "template": "Summarize audit readiness, top risks, remediation status as a 5-paragraph executive narrative.", "active": True},
    ])
    counts["model_registry"] = 2
    counts["prompt_registry"] = 2
    return counts
