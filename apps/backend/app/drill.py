"""Drill-down data assembly: given a record type + id, return the record and all related records.

Supported types: invoice, payment, journal, vendor, user, control.
Each response has: {primary, related, exceptions, cases, timeline}.

L4 drill standard: summary/dashboard → list API → detail API → ``GET /api/drill/{type}/{id}``
(or module-specific drill) with at least two drill targets per shipped module; reuse
``DrillContextBar`` / ``drillPaths`` on the frontend.
"""
from __future__ import annotations
from collections import defaultdict
from typing import Any, Dict, List


async def drill_invoice(db, invoice_id: str) -> Dict[str, Any]:
    inv = await db.invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not inv:
        return {"error": "not_found"}
    vendor = await db.vendors.find_one({"id": inv["vendor_id"]}, {"_id": 0})
    po = await db.purchase_orders.find_one({"id": inv.get("po_id")}, {"_id": 0}) if inv.get("po_id") else None
    grn = await db.goods_receipts.find_one({"po_id": po["id"]}, {"_id": 0}) if po else None
    payments = [p async for p in db.payments.find({"invoice_id": invoice_id}, {"_id": 0})]
    exceptions = [e async for e in db.exceptions.find(
        {"source_record_type": "invoice", "source_record_id": invoice_id}, {"_id": 0})]
    cases = []
    for ex in exceptions:
        c = await db.cases.find_one({"exception_id": ex["id"]}, {"_id": 0})
        if c: cases.append(c)

    # Also surface duplicate siblings (same vendor/amount/invoice_number)
    dupes = []
    async for d in db.invoices.find(
        {"vendor_id": inv["vendor_id"], "amount": inv["amount"],
         "invoice_number": inv["invoice_number"], "id": {"$ne": invoice_id}},
        {"_id": 0}
    ): dupes.append(d)

    return {
        "type": "invoice",
        "primary": inv,
        "vendor": vendor,
        "purchase_order": po,
        "goods_receipt": grn,
        "payments": payments,
        "duplicates": dupes,
        "exceptions": exceptions,
        "cases": cases,
    }


async def drill_payment(db, payment_id: str) -> Dict[str, Any]:
    pay = await db.payments.find_one({"id": payment_id}, {"_id": 0})
    if not pay:
        return {"error": "not_found"}
    vendor = await db.vendors.find_one({"id": pay["vendor_id"]}, {"_id": 0})
    invoice = await db.invoices.find_one({"id": pay.get("invoice_id")}, {"_id": 0}) if pay.get("invoice_id") else None
    exceptions = [e async for e in db.exceptions.find(
        {"source_record_type": "payment", "source_record_id": payment_id}, {"_id": 0})]
    cases = []
    for ex in exceptions:
        c = await db.cases.find_one({"exception_id": ex["id"]}, {"_id": 0})
        if c: cases.append(c)
    return {
        "type": "payment",
        "primary": pay,
        "vendor": vendor,
        "invoice": invoice,
        "exceptions": exceptions,
        "cases": cases,
    }


async def drill_journal(db, journal_id: str) -> Dict[str, Any]:
    jrn = await db.journals.find_one({"id": journal_id}, {"_id": 0})
    if not jrn:
        return {"error": "not_found"}
    creator = await db.users.find_one({"email": jrn["created_by"]}, {"_id": 0, "password_hash": 0})
    approver = await db.users.find_one({"email": jrn.get("approver_email")}, {"_id": 0, "password_hash": 0}) if jrn.get("approver_email") else None
    exceptions = [e async for e in db.exceptions.find(
        {"source_record_type": "journal", "source_record_id": journal_id}, {"_id": 0})]
    cases = []
    for ex in exceptions:
        c = await db.cases.find_one({"exception_id": ex["id"]}, {"_id": 0})
        if c: cases.append(c)
    # Other journals by the same user recent
    siblings = [j async for j in db.journals.find(
        {"created_by": jrn["created_by"], "id": {"$ne": journal_id}}, {"_id": 0}
    ).sort("created_at", -1).limit(10)]
    return {
        "type": "journal",
        "primary": jrn,
        "creator": creator,
        "approver": approver,
        "recent_by_same_user": siblings,
        "exceptions": exceptions,
        "cases": cases,
    }


async def drill_vendor(db, vendor_id: str) -> Dict[str, Any]:
    v = await db.vendors.find_one({"id": vendor_id}, {"_id": 0})
    if not v:
        return {"error": "not_found"}
    invoices = [i async for i in db.invoices.find({"vendor_id": vendor_id}, {"_id": 0}).sort("invoice_date", -1).limit(50)]
    payments = [p async for p in db.payments.find({"vendor_id": vendor_id}, {"_id": 0}).sort("payment_date", -1).limit(50)]
    pos = [p async for p in db.purchase_orders.find({"vendor_id": vendor_id}, {"_id": 0}).limit(20)]
    # Exceptions that reference this vendor's invoices/payments
    inv_ids = [i["id"] for i in invoices]
    pay_ids = [p["id"] for p in payments]
    exceptions = [e async for e in db.exceptions.find({
        "$or": [
            {"source_record_type": "invoice", "source_record_id": {"$in": inv_ids}},
            {"source_record_type": "payment", "source_record_id": {"$in": pay_ids}},
        ]
    }, {"_id": 0}).limit(50)]
    total_invoiced = sum(i["amount"] for i in invoices)
    total_paid = sum(p["amount"] for p in payments)
    return {
        "type": "vendor",
        "primary": v,
        "stats": {
            "invoice_count": len(invoices),
            "payment_count": len(payments),
            "total_invoiced": round(total_invoiced, 2),
            "total_paid": round(total_paid, 2),
            "exception_count": len(exceptions),
        },
        "invoices": invoices,
        "payments": payments,
        "purchase_orders": pos,
        "exceptions": exceptions,
    }


async def drill_user(db, raw_id: str) -> Dict[str, Any]:
    """Resolve ``user`` drill by email, or by ``user_access_events.id`` (e.g. ``UA-17`` from exception source_record_id)."""
    raw = (raw_id or "").strip()
    email = raw
    # Exceptions from inactive-user control store access_event id, not email — resolve first.
    if "@" not in raw:
        ev_by_id = await db.user_access_events.find_one({"id": raw}, {"_id": 0})
        if ev_by_id and ev_by_id.get("user_email"):
            email = str(ev_by_id["user_email"]).strip()

    access_events = [a async for a in db.user_access_events.find({"user_email": email}, {"_id": 0}).sort("event_ts", -1).limit(50)]
    u = await db.users.find_one({"email": email}, {"_id": 0, "password_hash": 0})
    if not u:
        ent = access_events[0].get("entity") if access_events else None
        term = bool(access_events and access_events[0].get("user_terminated"))
        u = {
            "email": email,
            "full_name": email,
            "role": None,
            "entity": ent,
            "status": "terminated" if term else "inactive",
        }
    roles = [r async for r in db.sod_role_map.find({"user_email": email}, {"_id": 0})]
    cases = [c async for c in db.cases.find({"owner_email": email}, {"_id": 0}).sort("due_date", 1).limit(30)]
    journals_posted = [j async for j in db.journals.find({"created_by": email}, {"_id": 0}).sort("created_at", -1).limit(20)]
    audit_log = [l async for l in db.audit_logs.find({"actor_user_email": email}, {"_id": 0}).sort("event_ts", -1).limit(30)]
    return {
        "type": "user",
        "primary": u,
        "roles": roles,
        "access_events": access_events,
        "cases": cases,
        "journals_posted": journals_posted,
        "audit_log": audit_log,
    }


async def drill_control(db, control_id: str) -> Dict[str, Any]:
    c = await db.controls.find_one({"id": control_id}, {"_id": 0})
    if not c:
        c = await db.controls.find_one({"code": control_id}, {"_id": 0})
    if not c:
        return {"error": "not_found"}
    runs = [r async for r in db.test_runs.find({"control_id": c["id"]}, {"_id": 0}).sort("run_ts", -1).limit(20)]
    exceptions = [e async for e in db.exceptions.find({"control_id": c["id"]}, {"_id": 0}).sort("financial_exposure", -1).limit(100)]
    cases = []
    for ex in exceptions[:20]:
        ca = await db.cases.find_one({"exception_id": ex["id"]}, {"_id": 0})
        if ca: cases.append(ca)
    exposure_total = sum(e["financial_exposure"] for e in exceptions)
    by_entity = defaultdict(int)
    for e in exceptions:
        by_entity[e["entity"]] += 1
    return {
        "type": "control",
        "primary": c,
        "stats": {
            "exception_count": len(exceptions),
            "total_exposure": round(exposure_total, 2),
            "open_cases": len([ca for ca in cases if ca["status"] != "closed"]),
            "by_entity": dict(by_entity),
        },
        "recent_runs": runs,
        "exceptions": exceptions,
        "cases": cases,
    }


# ---------- Phase 2 drill types ----------

async def _exceptions_for(db, src_type: str, src_id: str):
    exs = [e async for e in db.exceptions.find(
        {"source_record_type": src_type, "source_record_id": src_id}, {"_id": 0})]
    cases = []
    for ex in exs:
        ca = await db.cases.find_one({"exception_id": ex["id"]}, {"_id": 0})
        if ca: cases.append(ca)
    return exs, cases


async def drill_customer(db, customer_id: str) -> Dict[str, Any]:
    c = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not c:
        return {"error": "not_found"}
    sales_orders = [s async for s in db.sales_orders.find({"customer_id": customer_id}, {"_id": 0}).sort("so_date", -1).limit(50)]
    ar_invoices = [i async for i in db.ar_invoices.find({"customer_id": customer_id}, {"_id": 0}).sort("invoice_date", -1).limit(50)]
    receipts = [r async for r in db.customer_receipts.find({"customer_id": customer_id}, {"_id": 0}).sort("receipt_date", -1).limit(50)]
    open_exposure = sum(
        s["amount"] for s in sales_orders if s["status"] in ("open", "shipped")
    ) + sum(i["amount"] for i in ar_invoices if i["status"] == "open")
    exceptions, cases = await _exceptions_for(db, "customer", customer_id)
    return {
        "type": "customer",
        "primary": c,
        "stats": {
            "sales_order_count": len(sales_orders),
            "ar_invoice_count": len(ar_invoices),
            "receipt_count": len(receipts),
            "open_exposure": round(open_exposure, 2),
            "credit_limit": c.get("credit_limit", 0),
            "over_limit": max(0.0, round(open_exposure - c.get("credit_limit", 0), 2)),
        },
        "sales_orders": sales_orders,
        "ar_invoices": ar_invoices,
        "receipts": receipts,
        "exceptions": exceptions,
        "cases": cases,
    }


async def drill_ar_invoice(db, ar_id: str) -> Dict[str, Any]:
    inv = await db.ar_invoices.find_one({"id": ar_id}, {"_id": 0})
    if not inv:
        return {"error": "not_found"}
    customer = await db.customers.find_one({"id": inv["customer_id"]}, {"_id": 0})
    receipts = [r async for r in db.customer_receipts.find({"ar_invoice_id": ar_id}, {"_id": 0})]
    exceptions, cases = await _exceptions_for(db, "ar_invoice", ar_id)
    return {
        "type": "ar_invoice",
        "primary": inv,
        "customer": customer,
        "receipts": receipts,
        "exceptions": exceptions,
        "cases": cases,
    }


async def drill_sales_order(db, so_id: str) -> Dict[str, Any]:
    so = await db.sales_orders.find_one({"id": so_id}, {"_id": 0})
    if not so:
        return {"error": "not_found"}
    customer = await db.customers.find_one({"id": so["customer_id"]}, {"_id": 0})
    exceptions, cases = await _exceptions_for(db, "sales_order", so_id)
    return {"type": "sales_order", "primary": so, "customer": customer, "exceptions": exceptions, "cases": cases}


async def drill_employee(db, emp_id: str) -> Dict[str, Any]:
    e = await db.employees.find_one({"id": emp_id}, {"_id": 0})
    if not e:
        return {"error": "not_found"}
    entries = [p async for p in db.payroll_entries.find({"employee_id": emp_id}, {"_id": 0}).sort("period", -1).limit(36)]
    total_gross = sum(p["gross_amount"] for p in entries)
    total_net = sum(p["net_amount"] for p in entries)
    # Exceptions referencing payroll_entry ids belonging to this employee
    entry_ids = [p["id"] for p in entries]
    exceptions = [x async for x in db.exceptions.find(
        {"source_record_type": "payroll_entry", "source_record_id": {"$in": entry_ids}}, {"_id": 0})]
    return {
        "type": "employee",
        "primary": e,
        "stats": {
            "entry_count": len(entries),
            "total_gross": round(total_gross, 2),
            "total_net": round(total_net, 2),
            "exception_count": len(exceptions),
        },
        "payroll_entries": entries,
        "exceptions": exceptions,
    }


async def drill_payroll_entry(db, pe_id: str) -> Dict[str, Any]:
    pe = await db.payroll_entries.find_one({"id": pe_id}, {"_id": 0})
    if not pe:
        return {"error": "not_found"}
    emp = await db.employees.find_one({"id": pe["employee_id"]}, {"_id": 0})
    run = await db.payroll_runs.find_one({"id": pe["payroll_run_id"]}, {"_id": 0})
    exceptions, cases = await _exceptions_for(db, "payroll_entry", pe_id)
    return {"type": "payroll_entry", "primary": pe, "employee": emp, "payroll_run": run,
            "exceptions": exceptions, "cases": cases}


async def drill_bank_transaction(db, bt_id: str) -> Dict[str, Any]:
    bt = await db.bank_transactions.find_one({"id": bt_id}, {"_id": 0})
    if not bt:
        return {"error": "not_found"}
    ba = await db.bank_accounts.find_one({"id": bt["bank_account_id"]}, {"_id": 0})
    exceptions, cases = await _exceptions_for(db, "bank_transaction", bt_id)
    return {"type": "bank_transaction", "primary": bt, "bank_account": ba,
            "exceptions": exceptions, "cases": cases}


async def drill_fixed_asset(db, fa_id: str) -> Dict[str, Any]:
    a = await db.fixed_assets.find_one({"id": fa_id}, {"_id": 0})
    if not a:
        return {"error": "not_found"}
    depreciation = [d async for d in db.depreciation_schedules.find({"asset_id": fa_id}, {"_id": 0}).sort("period", -1)]
    total_dep = sum(d["amount"] for d in depreciation)
    nbv = max(0.0, a["cost"] - total_dep)
    exceptions, cases = await _exceptions_for(db, "fixed_asset", fa_id)
    return {
        "type": "fixed_asset",
        "primary": a,
        "stats": {
            "depreciation_entries": len(depreciation),
            "accumulated_depreciation": round(total_dep, 2),
            "net_book_value": round(nbv, 2),
        },
        "depreciation": depreciation,
        "exceptions": exceptions,
        "cases": cases,
    }


async def drill_capex_project(db, cpx_id: str) -> Dict[str, Any]:
    p = await db.capex_projects.find_one({"id": cpx_id}, {"_id": 0})
    if not p:
        return {"error": "not_found"}
    exceptions, cases = await _exceptions_for(db, "capex_project", cpx_id)
    variance = p["actual_amount"] - p["budget_amount"]
    return {
        "type": "capex_project",
        "primary": p,
        "stats": {
            "variance": round(variance, 2),
            "variance_pct": round((variance / p["budget_amount"]) * 100, 2) if p["budget_amount"] else 0,
        },
        "exceptions": exceptions,
        "cases": cases,
    }


DRILL_FN = {
    "invoice": drill_invoice,
    "payment": drill_payment,
    "journal": drill_journal,
    "vendor": drill_vendor,
    "user": drill_user,
    "control": drill_control,
    # Phase 2
    "customer": drill_customer,
    "ar_invoice": drill_ar_invoice,
    "sales_order": drill_sales_order,
    "employee": drill_employee,
    "payroll_entry": drill_payroll_entry,
    "bank_transaction": drill_bank_transaction,
    "fixed_asset": drill_fixed_asset,
    "capex_project": drill_capex_project,
}


async def drill(db, type_: str, id_: str) -> Dict[str, Any]:
    fn = DRILL_FN.get(type_)
    if not fn:
        return {"error": "unknown_type"}
    return await fn(db, id_)
