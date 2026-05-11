"""REST namespaces aligned to SRS (delegate to existing dashboard analytics)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.deps import audit_log, db
from app.analytics import cash_conversion_dashboard, working_capital_dashboard, treasury_dashboard, fpa_dashboard
from app.services.kpi_service import as_of_now
from app.services.rbac_service import enforce_entity_scope


wc_router = APIRouter(prefix="/working-capital", tags=["working-capital"])
ar_router = APIRouter(prefix="/ar", tags=["ar"])
ap_router = APIRouter(prefix="/ap", tags=["ap"])
treasury_router = APIRouter(prefix="/treasury", tags=["treasury"])
budget_router = APIRouter(prefix="/budget", tags=["budget"])
forecast_router = APIRouter(prefix="/forecast", tags=["forecast"])


def _scope_kwargs(
    entity_code: Optional[str],
    period_ym: Optional[str],
    department_id: Optional[str],
    cost_center_id: Optional[str],
) -> Dict[str, Any]:
    return {
        "entity_code": entity_code,
        "period_ym": period_ym,
        "department_id": department_id,
        "cost_center_id": cost_center_id,
    }


async def _enforce_scope(
    current: dict,
    entity_code: Optional[str],
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
) -> Dict[str, Any]:
    ec = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return _scope_kwargs(ec, period_ym, department_id, cost_center_id)


def _parse_dt(s: Any) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:  # noqa: BLE001
        return None


async def _ensure_seed_phase26_treasury(entity_code: Optional[str] = None) -> Dict[str, int]:
    """Seed-on-first-use for Phase 26 collections (safe on existing DBs)."""
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code

    out = {"debt_register": 0, "repayment_schedule": 0, "investments": 0, "covenants": 0, "bank_signatories": 0}
    now = datetime.now(timezone.utc)

    if await db.debt_register.count_documents(q) == 0:
        docs = []
        for i in range(5):
            principal = round(5_000_000 * (1.0 + i * 0.35), 2)
            rate = 0.09 + (i * 0.01)
            start = now - timedelta(days=365 * (2 + i))
            maturity = now + timedelta(days=365 * (1 + i))
            did = f"DEBT-{5000+i}"
            docs.append(
                {
                    "id": did,
                    "entity": entity_code or "US-HQ",
                    "facility_name": ["Term Loan", "Working Capital Loan", "OD Facility", "Equipment Finance", "Debenture"][i],
                    "lender": ["Axis Bank", "ICICI Bank", "HDFC Bank", "SBI", "NBFC Partner"][i],
                    "principal_amount": principal,
                    "interest_rate": round(rate, 4),
                    "start_date": start.isoformat(),
                    "maturity_date": maturity.isoformat(),
                    "repayment_frequency": "monthly",
                    "status": "active",
                    "currency": "INR",
                }
            )
        await db.debt_register.insert_many(docs)
        out["debt_register"] = len(docs)

    if await db.repayment_schedule.count_documents(q) == 0:
        debts = [d async for d in db.debt_register.find(q, {"_id": 0}).limit(50)]
        docs = []
        for d in debts:
            principal = float(d.get("principal_amount") or 0.0)
            rate = float(d.get("interest_rate") or 0.0)
            monthly_principal = round(principal / 24.0, 2) if principal else 0.0
            for m in range(1, 7):
                due = (now.replace(day=1) + timedelta(days=30 * m)).date().isoformat()
                interest = round((principal * rate) / 12.0, 2)
                pid = f"RP-{d['id']}-{m}"
                docs.append(
                    {
                        "id": pid,
                        "entity": d.get("entity"),
                        "debt_id": d["id"],
                        "due_date": due,
                        "principal_due": monthly_principal,
                        "interest_due": interest,
                        "total_due": round(monthly_principal + interest, 2),
                        "status": "due" if m <= 2 else "scheduled",
                    }
                )
        if docs:
            await db.repayment_schedule.insert_many(docs)
            out["repayment_schedule"] = len(docs)

    if await db.investments.count_documents(q) == 0:
        docs = []
        for i in range(6):
            iid = f"INVEST-{6000+i}"
            amount = round(750_000 * (1.0 + i * 0.45), 2)
            yield_pct = round(0.06 + (i * 0.005), 4)
            start = now - timedelta(days=30 * (20 + i * 3))
            maturity = now + timedelta(days=30 * (60 + i * 6))
            docs.append(
                {
                    "id": iid,
                    "entity": entity_code or "US-HQ",
                    "instrument_type": ["FD", "T-Bill", "Mutual Fund", "Bond", "Commercial Paper", "FD"][i],
                    "counterparty": ["Axis Bank", "GoI", "AMC-Alpha", "Issuer-Beta", "Issuer-Gamma", "HDFC Bank"][i],
                    "amount": amount,
                    "yield_rate": yield_pct,
                    "start_date": start.isoformat(),
                    "maturity_date": maturity.isoformat(),
                    "status": "active",
                    "currency": "INR",
                }
            )
        await db.investments.insert_many(docs)
        out["investments"] = len(docs)

    if await db.covenants.count_documents(q) == 0:
        debts = [d async for d in db.debt_register.find(q, {"_id": 0}).limit(50)]
        docs = []
        for i, d in enumerate(debts):
            cid = f"COV-{d['id']}"
            req = 1.25 if i % 2 == 0 else 1.10
            actual = req - (0.15 if i in (1, 3) else -0.05)
            docs.append(
                {
                    "id": cid,
                    "entity": d.get("entity"),
                    "debt_id": d["id"],
                    "covenant_type": "DSCR",
                    "required_min": req,
                    "actual": round(actual, 2),
                    "status": "breach" if actual < req else "ok",
                    "as_of_period": now.replace(day=1).strftime("%Y-%m"),
                }
            )
        if docs:
            await db.covenants.insert_many(docs)
            out["covenants"] = len(docs)

    if await db.bank_signatories.count_documents(q) == 0:
        accounts = [a async for a in db.bank_accounts.find({"entity": entity_code} if entity_code else {}, {"_id": 0}).limit(30)]
        docs = []
        for i, a in enumerate(accounts[:8]):
            sid = f"SIG-{a.get('id') or i}"
            docs.append(
                {
                    "id": sid,
                    "entity": a.get("entity") or entity_code or "US-HQ",
                    "bank_account_id": a.get("id"),
                    "bank_name": a.get("bank_name") or a.get("bank") or "Bank",
                    "account_number": a.get("account_number") or a.get("account_no"),
                    "signatories": [
                        {"name": "CFO", "email": "cfo@onetouch.ai", "role": "cfo", "status": "active"},
                        {"name": "Controller", "email": "controller@onetouch.ai", "role": "controller", "status": "active"},
                        {"name": "Treasury Manager", "email": "treasury@onetouch.ai", "role": "treasury", "status": "active" if i % 3 else "inactive"},
                    ],
                    "last_reviewed_at": (now - timedelta(days=30 * (2 + i))).isoformat(),
                }
            )
        if docs:
            await db.bank_signatories.insert_many(docs)
            out["bank_signatories"] = len(docs)

    return out


@wc_router.get("")
@wc_router.get("/summary")
async def wc_summary(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    kw = await _enforce_scope(current, entity_code, period_ym, department_id, cost_center_id)
    data = await working_capital_dashboard(db, **kw)
    return {"source": "analytics.working_capital_dashboard", "as_of": as_of_now(), "data": data}


@wc_router.get("/ccc")
async def wc_ccc(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    kw = await _enforce_scope(current, entity_code, period_ym, department_id, cost_center_id)
    ccc = await cash_conversion_dashboard(db, **kw)
    return {"source": "analytics.cash_conversion_dashboard", "as_of": as_of_now(), "data": ccc}


@wc_router.get("/blocked-cash")
async def wc_blocked_cash(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    kw = await _enforce_scope(current, entity_code, period_ym, department_id, cost_center_id)
    wc = await working_capital_dashboard(db, **kw)
    k = wc.get("kpis") or {}
    ar_overdue = float(k.get("ar_overdue_amount") or 0.0)
    ap_overdue = float(k.get("ap_overdue_amount") or 0.0)
    blocked = round(ar_overdue + ap_overdue, 2)
    return {
        "as_of": as_of_now(),
        "filters_applied": wc.get("filters_applied") or {},
        "kpis": {
            "blocked_cash_total": blocked,
            "blocked_cash_ar_overdue": round(ar_overdue, 2),
            "blocked_cash_ap_overdue": round(ap_overdue, 2),
        },
        "note": "Blocked cash proxy = overdue AR + overdue AP until dedicated holds/disputes models are implemented.",
        "source": "working_capital_dashboard.proxy",
    }


@wc_router.get("/bridge")
async def wc_bridge(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    kw = await _enforce_scope(current, entity_code, period_ym, department_id, cost_center_id)
    wc = await working_capital_dashboard(db, **kw)
    k = wc.get("kpis") or {}
    return {
        "as_of": as_of_now(),
        "filters_applied": wc.get("filters_applied") or {},
        "bridge": [
            {"key": "ar_open", "label": "AR open", "amount": float(k.get("ar_open_amount") or 0.0)},
            {"key": "ap_open", "label": "AP open", "amount": float(k.get("ap_open_amount") or 0.0)},
            {"key": "ar_overdue", "label": "AR overdue", "amount": float(k.get("ar_overdue_amount") or 0.0)},
            {"key": "ap_overdue", "label": "AP overdue", "amount": float(k.get("ap_overdue_amount") or 0.0)},
        ],
        "source": "working_capital_dashboard.proxy",
    }


@wc_router.get("/entity-view")
async def wc_entity_view(
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    entities = [e async for e in db.entities.find({}, {"_id": 0, "code": 1, "name": 1}).sort("code", 1)]
    scoped = await enforce_entity_scope(db, current=current, requested_entity_code=None)
    if scoped and current.get("role") != "Super Admin":
        entities = [e for e in entities if (e or {}).get("code") == scoped]
    rows = []
    for e in entities:
        kw = await _enforce_scope(current, (e or {}).get("code"), period_ym, department_id, cost_center_id)
        wc = await working_capital_dashboard(db, **kw)
        k = wc.get("kpis") or {}
        rows.append(
            {
                "entity_code": e.get("code"),
                "entity_name": e.get("name"),
                "ar_open_amount": k.get("ar_open_amount"),
                "ar_overdue_amount": k.get("ar_overdue_amount"),
                "ap_open_amount": k.get("ap_open_amount"),
                "ap_overdue_amount": k.get("ap_overdue_amount"),
                "wc_exception_open": k.get("wc_exception_open"),
            }
        )
    return {"items": rows, "count": len(rows), "as_of": as_of_now(), "source": "per-entity working_capital_dashboard"}


@wc_router.get("/ar-ageing")
async def wc_ar_ageing(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    """Phase 9 — AR ageing buckets derived from Phase 2 `ar_invoices`."""
    kw = await _enforce_scope(current, entity_code, period_ym, department_id, cost_center_id)
    wc = await working_capital_dashboard(db, **kw)
    return {
        "as_of": as_of_now(),
        "filters_applied": wc.get("filters_applied") or {},
        "ar_ageing": wc.get("ar_aging") or [],
        "ar_open_total": wc.get("ar_open_total"),
        "top_overdue_ar": wc.get("top_overdue_ar") or [],
        "source": "analytics.working_capital_dashboard",
    }


@wc_router.get("/ap-ageing")
async def wc_ap_ageing(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    """Phase 10 — AP ageing buckets derived from Phase 1 `invoices`."""
    kw = await _enforce_scope(current, entity_code, period_ym, department_id, cost_center_id)
    wc = await working_capital_dashboard(db, **kw)
    return {
        "as_of": as_of_now(),
        "filters_applied": wc.get("filters_applied") or {},
        "ap_ageing": wc.get("ap_aging") or [],
        "ap_open_total": wc.get("ap_open_total"),
        "top_overdue_ap": wc.get("top_overdue_ap") or [],
        "source": "analytics.working_capital_dashboard",
    }


@ar_router.get("/summary")
async def ar_summary(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    kw = await _enforce_scope(current, entity_code, period_ym, department_id, cost_center_id)
    full = await working_capital_dashboard(db, **kw)
    return {
        "source": "working_capital_dashboard.ar_slice",
        "ar_ageing": full.get("ar_ageing"),
        "ar_open_total": full.get("ar_open_total"),
        "top_overdue_ar": full.get("top_overdue_ar"),
        "filters_applied": full.get("filters_applied"),
    }


@ar_router.get("/customers")
async def ar_customers(
    entity_code: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current=Depends(get_current_user),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    filt: Dict[str, Any] = {}
    if entity_code:
        filt["entity"] = entity_code
    if q and q.strip():
        rq = {"$regex": q.strip(), "$options": "i"}
        filt["$or"] = [{"customer_name": rq}, {"customer_code": rq}, {"id": rq}]
    cur = db.customers.find(filt, {"_id": 0}).sort("customer_code", 1).skip(offset).limit(limit)
    items = [c async for c in cur]
    total = await db.customers.count_documents(filt)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": as_of_now()}


@ar_router.get("/customers/{customer_id}")
async def ar_customer_detail(
    customer_id: str,
    current=Depends(get_current_user),
):
    c = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not c:
        c = await db.customers.find_one({"customer_code": customer_id}, {"_id": 0})
    if not c:
        return {"id": customer_id, "found": False, "as_of": as_of_now()}
    await enforce_entity_scope(db, current=current, requested_entity_code=c.get("entity"))
    open_amt = 0.0
    async for inv in db.ar_invoices.find({"customer_id": c["id"], "status": {"$in": ["open", "overdue"]}}, {"_id": 0, "amount": 1}):
        open_amt += float(inv.get("amount") or 0.0)
    return {"customer": c, "ar_open_amount": round(open_amt, 2), "found": True, "as_of": as_of_now()}


@ar_router.get("/invoices")
async def ar_invoices(
    entity_code: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    current=Depends(get_current_user),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    filt: Dict[str, Any] = {}
    if entity_code:
        filt["entity"] = entity_code
    if status:
        filt["status"] = status
    if customer_id:
        filt["customer_id"] = customer_id
    cur = db.ar_invoices.find(filt, {"_id": 0}).sort("invoice_date", -1).skip(offset).limit(limit)
    items = [x async for x in cur]
    total = await db.ar_invoices.count_documents(filt)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": as_of_now()}


@ar_router.post("/collection-case")
async def ar_collection_case(
    body: Dict[str, Any],
    current=Depends(get_current_user),
):
    """Phase 9 — create a case from an overdue AR invoice/customer context."""
    resolved_entity = await enforce_entity_scope(
        db,
        current=current,
        requested_entity_code=str(body.get("entity") or body.get("entity_code") or "US-HQ"),
    )
    cid = f"case-ar-{__import__('uuid').uuid4().hex[:10]}"
    ex_id = str(body.get("invoice_id") or cid)
    payload = {
        "id": cid,
        # Align to CaseOut schema used by /cases list response_model.
        "exception_id": ex_id,
        "control_code": "AR-COLLECT-001",
        "control_name": "AR Collection Follow-up",
        "title": str(body.get("title") or "AR collection follow-up"),
        "summary": str(body.get("summary") or "Collection follow-up created from AR module."),
        "severity": str(body.get("severity") or "medium"),
        "status": "open",
        "priority": str(body.get("priority") or "P2"),
        "owner_email": body.get("owner_email") or current.get("email"),
        "owner_name": None,
        "due_date": as_of_now(),
        "financial_exposure": float(body.get("exposure") or 0.0),
        "entity": str(resolved_entity),
        "process": "Order-to-Cash",
        "detected_at": as_of_now(),
        "opened_at": as_of_now(),
        "closed_at": None,
        "root_cause_category": None,
        "source": "ar.collection_case",
        "detail": body,
    }
    # Ensure an exception document exists so /cases/{id} returns `exception` and close workflow can close it.
    await db.exceptions.update_one(
        {"id": ex_id},
        {
            "$setOnInsert": {
                "id": ex_id,
                "control_id": "adhoc-ar-collect",
                "control_code": payload["control_code"],
                "control_name": payload["control_name"],
                "process": payload["process"],
                "entity": payload["entity"],
                "title": payload["title"],
                "summary": payload["summary"],
                "severity": payload["severity"],
                "status": "open",
                "materiality_score": 0.0,
                "anomaly_score": 0.0,
                "financial_exposure": payload["financial_exposure"],
                "source_record_type": "ar_invoice",
                "source_record_id": ex_id,
                "detected_at": payload["detected_at"],
            }
        },
        upsert=True,
    )
    await db.cases.insert_one(dict(payload))
    await audit_log(
        current["email"],
        "ar_collection_case_create",
        "case",
        cid,
        {"customer_id": body.get("customer_id"), "invoice_id": body.get("invoice_id")},
    )
    return {"status": "ok", "case": payload, "as_of": as_of_now()}


@ar_router.post("/dispute")
async def ar_dispute(
    body: Dict[str, Any],
    current=Depends(get_current_user),
):
    be = body.get("entity") or body.get("entity_code")
    if be and str(be).strip():
        await enforce_entity_scope(db, current=current, requested_entity_code=str(be))
    did = f"dispute-{__import__('uuid').uuid4().hex[:10]}"
    doc = {**body, "id": did, "created_at": as_of_now(), "created_by": current.get("email")}
    await db.ar_disputes.insert_one(dict(doc))
    await audit_log(current["email"], "ar_dispute_create", "ar_dispute", did, {"invoice_id": body.get("invoice_id")})
    return {"status": "ok", "dispute_id": did, "as_of": as_of_now()}


@ar_router.post("/promised-payment")
async def ar_promised_payment(
    body: Dict[str, Any],
    current=Depends(get_current_user),
):
    be = body.get("entity") or body.get("entity_code")
    if be and str(be).strip():
        await enforce_entity_scope(db, current=current, requested_entity_code=str(be))
    pid = f"pp-{__import__('uuid').uuid4().hex[:10]}"
    doc = {**body, "id": pid, "created_at": as_of_now(), "created_by": current.get("email")}
    await db.ar_promised_payments.insert_one(dict(doc))
    await audit_log(
        current["email"],
        "ar_promised_payment_create",
        "ar_promised_payment",
        pid,
        {"invoice_id": body.get("invoice_id")},
    )
    return {"status": "ok", "promised_payment_id": pid, "as_of": as_of_now()}


@ap_router.get("/summary")
async def ap_summary(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    kw = await _enforce_scope(current, entity_code, period_ym, department_id, cost_center_id)
    full = await working_capital_dashboard(db, **kw)
    return {
        "source": "working_capital_dashboard.ap_slice",
        "ap_ageing": full.get("ap_ageing"),
        "ap_open_total": full.get("ap_open_total"),
        "top_overdue_ap": full.get("top_overdue_ap"),
        "filters_applied": full.get("filters_applied"),
    }


@ap_router.get("/vendors")
async def ap_vendors(
    entity_code: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current=Depends(get_current_user),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    filt: Dict[str, Any] = {}
    if entity_code:
        filt["entity"] = entity_code
    if q and q.strip():
        rq = {"$regex": q.strip(), "$options": "i"}
        filt["$or"] = [{"vendor_name": rq}, {"vendor_code": rq}, {"id": rq}]
    cur = db.vendors.find(filt, {"_id": 0}).sort("vendor_code", 1).skip(offset).limit(limit)
    items = [v async for v in cur]
    total = await db.vendors.count_documents(filt)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": as_of_now()}


@ap_router.get("/vendors/{vendor_id}")
async def ap_vendor_detail(vendor_id: str, current=Depends(get_current_user)):
    v = await db.vendors.find_one({"id": vendor_id}, {"_id": 0})
    if not v:
        v = await db.vendors.find_one({"vendor_code": vendor_id}, {"_id": 0})
    if not v:
        return {"id": vendor_id, "found": False, "as_of": as_of_now()}
    await enforce_entity_scope(db, current=current, requested_entity_code=v.get("entity"))
    open_amt = 0.0
    async for inv in db.invoices.find({"vendor_id": v["id"], "status": {"$in": ["open", "overdue"]}}, {"_id": 0, "amount": 1}):
        open_amt += float(inv.get("amount") or 0.0)
    return {"vendor": v, "ap_open_amount": round(open_amt, 2), "found": True, "as_of": as_of_now()}


@ap_router.get("/invoices")
async def ap_invoices(
    entity_code: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    vendor_id: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    current=Depends(get_current_user),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    filt: Dict[str, Any] = {}
    if entity_code:
        filt["entity"] = entity_code
    if status:
        filt["status"] = status
    if vendor_id:
        filt["vendor_id"] = vendor_id
    cur = db.invoices.find(filt, {"_id": 0}).sort("invoice_date", -1).skip(offset).limit(limit)
    items = [x async for x in cur]
    total = await db.invoices.count_documents(filt)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": as_of_now()}


@ap_router.get("/payment-calendar")
async def ap_payment_calendar(
    entity_code: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    current=Depends(get_current_user),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    q: Dict[str, Any] = {"status": {"$in": ["open", "overdue"]}}
    if entity_code:
        q["entity"] = entity_code
    cur = db.invoices.find(q, {"_id": 0}).sort("due_date", 1).limit(limit)
    items = [x async for x in cur]
    return {"items": items, "count": len(items), "as_of": as_of_now()}


@ap_router.get("/payment-prioritization")
async def ap_payment_prioritization(
    entity_code: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=200),
    current=Depends(get_current_user),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    q: Dict[str, Any] = {"status": {"$in": ["open", "overdue"]}}
    if entity_code:
        q["entity"] = entity_code
    cur = db.invoices.find(q, {"_id": 0}).sort([("status", 1), ("due_date", 1), ("amount", -1)]).limit(limit)
    items = [x async for x in cur]
    return {
        "items": items,
        "count": len(items),
        "as_of": as_of_now(),
        "note": "Prioritization proxy sorts by status(overdue first), due_date, and amount until policy + cash constraints are modeled.",
    }


@ap_router.post("/payment-hold")
async def ap_payment_hold(
    body: Dict[str, Any],
    current=Depends(get_current_user),
):
    be = body.get("entity") or body.get("entity_code")
    if be and str(be).strip():
        await enforce_entity_scope(db, current=current, requested_entity_code=str(be))
    hid = f"hold-{__import__('uuid').uuid4().hex[:10]}"
    doc = {**body, "id": hid, "created_at": as_of_now(), "created_by": current.get("email")}
    await db.ap_payment_holds.insert_one(dict(doc))
    await audit_log(current["email"], "ap_payment_hold", "ap_payment_hold", hid, {"invoice_id": body.get("invoice_id")})
    return {"status": "ok", "hold_id": hid, "as_of": as_of_now()}


@treasury_router.get("/summary")
async def treasury_summary(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_phase26_treasury(entity_code=entity_code)
    kw = _scope_kwargs(entity_code, period_ym, department_id, cost_center_id)
    data = await treasury_dashboard(db, **kw)
    # Phase 26 snapshot additions (debt + investments)
    debt_q: Dict[str, Any] = {"entity": entity_code} if entity_code else {}
    debt_count = await db.debt_register.count_documents(debt_q)
    inv_count = await db.investments.count_documents(debt_q)
    cov_breaches = await db.covenants.count_documents({**debt_q, "status": "breach"})
    return {
        "as_of": as_of_now(),
        "source": "analytics.treasury_dashboard",
        "data": {**(data or {}), "phase26": {"debt_count": debt_count, "investment_count": inv_count, "covenant_breaches": cov_breaches}},
    }


@treasury_router.get("/debt")
async def treasury_debt(entity_code: Optional[str] = Query(None), limit: int = Query(200, ge=1, le=2000), offset: int = Query(0, ge=0), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_phase26_treasury(entity_code=entity_code)
    q: Dict[str, Any] = {"entity": entity_code} if entity_code else {}
    cur = db.debt_register.find(q, {"_id": 0}).sort("maturity_date", 1).skip(offset).limit(limit)
    items = [d async for d in cur]
    total = await db.debt_register.count_documents(q)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": as_of_now()}


@treasury_router.get("/repayment-schedule")
async def treasury_repayment_schedule(entity_code: Optional[str] = Query(None), debt_id: Optional[str] = Query(None), limit: int = Query(500, ge=1, le=5000), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_phase26_treasury(entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    if debt_id:
        q["debt_id"] = debt_id
    cur = db.repayment_schedule.find(q, {"_id": 0}).sort("due_date", 1).limit(limit)
    items = [x async for x in cur]
    total = await db.repayment_schedule.count_documents(q)
    return {"items": items, "total": total, "as_of": as_of_now()}


@treasury_router.get("/investments")
async def treasury_investments(entity_code: Optional[str] = Query(None), limit: int = Query(200, ge=1, le=2000), offset: int = Query(0, ge=0), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_phase26_treasury(entity_code=entity_code)
    q: Dict[str, Any] = {"entity": entity_code} if entity_code else {}
    cur = db.investments.find(q, {"_id": 0}).sort("maturity_date", 1).skip(offset).limit(limit)
    items = [x async for x in cur]
    total = await db.investments.count_documents(q)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": as_of_now()}


@treasury_router.get("/covenants")
async def treasury_covenants(entity_code: Optional[str] = Query(None), status: Optional[str] = Query(None), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_phase26_treasury(entity_code=entity_code)
    q: Dict[str, Any] = {"entity": entity_code} if entity_code else {}
    if status:
        q["status"] = status
    cur = db.covenants.find(q, {"_id": 0}).sort("status", 1).limit(500)
    items = [x async for x in cur]
    breaches = [x for x in items if x.get("status") == "breach"]
    return {"items": items, "count": len(items), "breach_count": len(breaches), "as_of": as_of_now()}


@treasury_router.get("/bank-signatories")
async def treasury_bank_signatories(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_phase26_treasury(entity_code=entity_code)
    q: Dict[str, Any] = {"entity": entity_code} if entity_code else {}
    cur = db.bank_signatories.find(q, {"_id": 0}).sort("bank_name", 1).limit(200)
    items = [x async for x in cur]
    return {"items": items, "count": len(items), "as_of": as_of_now()}


@treasury_router.post("/{source_id}/create-case")
async def treasury_create_case(source_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    await _ensure_seed_phase26_treasury()
    debt = await db.debt_register.find_one({"id": source_id}, {"_id": 0})
    inv = None if debt else await db.investments.find_one({"id": source_id}, {"_id": 0})
    cov = None if (debt or inv) else await db.covenants.find_one({"id": source_id}, {"_id": 0})
    if not debt and not inv and not cov:
        raise HTTPException(404, "Treasury item not found")

    now_iso = as_of_now()
    cid = f"case-treasury-{__import__('uuid').uuid4().hex[:10]}"
    ex_id = f"treasury-{source_id}"
    entity = (debt or inv or cov).get("entity") or current.get("entity") or "US-HQ"
    entity = await enforce_entity_scope(db, current=current, requested_entity_code=entity)

    if cov and cov.get("status") == "breach":
        title = body.get("title") or "Covenant breach follow-up"
        control_code = "TR-COV-001"
        control_name = "Covenant breach"
        exposure = float(body.get("financial_exposure") or 0.0)
        summary = body.get("summary") or "Case created due to covenant breach detection."
        src_type = "covenant"
    elif debt:
        title = body.get("title") or f"Debt review: {debt.get('facility_name')}"
        control_code = "TR-DEBT-001"
        control_name = "Debt register follow-up"
        exposure = float(body.get("financial_exposure") or float(debt.get("principal_amount") or 0.0))
        summary = body.get("summary") or "Case created from debt register / repayment schedule surface."
        src_type = "debt"
    else:
        title = body.get("title") or f"Investment review: {inv.get('instrument_type')}"
        control_code = "TR-INV-001"
        control_name = "Investment register follow-up"
        exposure = float(body.get("financial_exposure") or float(inv.get("amount") or 0.0))
        summary = body.get("summary") or "Case created from investment register surface."
        src_type = "investment"

    ex_doc = {
        "id": ex_id,
        "control_id": f"adhoc-{control_code.lower()}",
        "control_code": control_code,
        "control_name": control_name,
        "process": "Treasury",
        "entity": entity,
        "severity": str(body.get("severity") or ("high" if cov and cov.get("status") == "breach" else "medium")),
        "status": "open",
        "materiality_score": float(body.get("materiality_score") or 0.4),
        "anomaly_score": float(body.get("anomaly_score") or 0.4),
        "financial_exposure": exposure,
        "source_record_type": src_type,
        "source_record_id": source_id,
        "detected_at": now_iso,
        "title": title,
        "summary": summary,
        "recurrence_count": 0,
        "department_id": None,
        "cost_center_id": None,
    }
    await db.exceptions.update_one({"id": ex_id}, {"$setOnInsert": ex_doc}, upsert=True)

    case_doc = {
        "id": cid,
        "exception_id": ex_id,
        "control_code": control_code,
        "control_name": control_name,
        "title": title,
        "summary": summary,
        "severity": ex_doc["severity"],
        "status": "open",
        "priority": body.get("priority") or ("P1" if cov and cov.get("status") == "breach" else "P2"),
        "owner_email": body.get("owner_email") or current.get("email"),
        "owner_name": None,
        "due_date": body.get("due_date") or now_iso,
        "financial_exposure": float(ex_doc.get("financial_exposure") or 0.0),
        "entity": entity,
        "process": "Treasury",
        "detected_at": now_iso,
        "opened_at": now_iso,
        "closed_at": None,
        "root_cause_category": None,
        "engagement_id": None,
        "material_impact": body.get("material_impact"),
        "material_watch": None,
        "department_id": None,
        "cost_center_id": None,
    }
    await db.cases.insert_one(dict(case_doc))
    await audit_log(current["email"], "treasury_create_case", "case", cid, {"source_record_id": source_id, "source_record_type": src_type})
    return {"status": "ok", "case_id": cid, "exception_id": ex_id, "as_of": as_of_now()}


@treasury_router.get("/cash-position")
async def treasury_cash_position(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    kw = _scope_kwargs(entity_code, period_ym, department_id, cost_center_id)
    data = await treasury_dashboard(db, **kw)
    accounts = data.get("bank_accounts") or []
    cash_balance = sum(float(a.get("balance") or 0.0) for a in accounts)
    return {
        "as_of": as_of_now(),
        "entity_code": entity_code,
        "cash_balance": round(cash_balance, 2),
        "bank_accounts": accounts,
        "recent_bank_transactions": data.get("recent_bank_transactions") or [],
        "kpis": data.get("kpis") or {},
        "source": "analytics.treasury_dashboard",
    }


@treasury_router.get("/forecast-13-week")
async def treasury_forecast_13_week(
    entity_code: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    """Phase 11 — lightweight 13-week forecast based on current cash + seeded payables proxy.

    This intentionally avoids claiming forecasting accuracy; it provides stable shapes and
    a usable shortfall-alert surface while the full cash engine is implemented.
    """
    from datetime import datetime, timedelta, timezone

    # IMPORTANT: When calling route handlers internally, always pass plain values for
    # Query(...) params; otherwise defaults are `fastapi.params.Query` objects.
    pos = await treasury_cash_position(
        entity_code=entity_code,
        period_ym=None,
        department_id=None,
        cost_center_id=None,
        current=current,
    )
    starting_cash = float(pos.get("cash_balance") or 0.0)
    entity_code = pos.get("entity_code")

    # Payables proxy: next due invoices (open/overdue) by week bucket.
    inv_q: Dict[str, Any] = {"status": {"$in": ["open", "overdue"]}}
    if entity_code:
        inv_q["entity"] = entity_code
    invs = [x async for x in db.invoices.find(inv_q, {"_id": 0}).sort("due_date", 1).limit(500)]

    now = datetime.now(timezone.utc)
    weeks = []
    running = starting_cash
    for i in range(13):
        ws = now.date() + timedelta(days=i * 7)
        we = ws + timedelta(days=6)
        outflow = 0.0
        for inv in invs:
            dd = inv.get("due_date")
            if not dd:
                continue
            try:
                d = datetime.fromisoformat(str(dd).replace("Z", "+00:00")).date()
            except Exception:  # noqa: BLE001
                continue
            if ws <= d <= we:
                outflow += float(inv.get("amount") or 0.0)

        inflow = 0.0  # placeholder until AR + collection plans are modeled
        ending = running + inflow - outflow
        weeks.append(
            {
                "week_index": i + 1,
                "start_date": str(ws),
                "end_date": str(we),
                "starting_cash": round(running, 2),
                "inflows": round(inflow, 2),
                "outflows": round(outflow, 2),
                "ending_cash": round(ending, 2),
                "notes": ["outflows derived from seeded AP invoices due_dates"] if outflow else [],
            }
        )
        running = ending

    return {
        "as_of": as_of_now(),
        "entity_code": entity_code,
        "starting_cash": round(starting_cash, 2),
        "weeks": weeks,
        "source": "treasury.forecast_13_week_proxy",
        "assumptions": {
            "inflows": "0.0 placeholder until AR forecast is modeled",
            "outflows": "sum of open/overdue invoices by due_date week bucket",
        },
    }


@treasury_router.post("/forecast")
async def treasury_forecast_save(body: Dict[str, Any], current=Depends(get_current_user)):
    be = body.get("entity") or body.get("entity_code")
    if be and str(be).strip():
        await enforce_entity_scope(db, current=current, requested_entity_code=str(be))
    fid = f"fc-{__import__('uuid').uuid4().hex[:10]}"
    doc = {**body, "id": fid, "created_at": as_of_now(), "created_by": current.get("email")}
    await db.treasury_forecasts.insert_one(dict(doc))
    await audit_log(current["email"], "treasury_forecast_create", "treasury_forecast", fid, {"entity": body.get("entity")})
    return {"status": "ok", "forecast_id": fid, "as_of": as_of_now()}


@treasury_router.post("/scenario")
async def treasury_scenario_create(body: Dict[str, Any], current=Depends(get_current_user)):
    be = body.get("entity") or body.get("entity_code")
    if be and str(be).strip():
        await enforce_entity_scope(db, current=current, requested_entity_code=str(be))
    sid = f"sc-{__import__('uuid').uuid4().hex[:10]}"
    doc = {**body, "id": sid, "created_at": as_of_now(), "created_by": current.get("email")}
    await db.treasury_scenarios.insert_one(dict(doc))
    await audit_log(current["email"], "treasury_scenario_create", "treasury_scenario", sid, {"name": body.get("name")})
    return {"status": "ok", "scenario_id": sid, "as_of": as_of_now()}


@treasury_router.get("/shortfall-alerts")
async def treasury_shortfall_alerts(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    fc = await treasury_forecast_13_week(entity_code=entity_code, current=current)
    alerts = [
        {
            "week_index": w["week_index"],
            "start_date": w["start_date"],
            "end_date": w["end_date"],
            "ending_cash": w["ending_cash"],
            "severity": "critical" if float(w["ending_cash"]) < 0 else "warning",
        }
        for w in (fc.get("weeks") or [])
        if float(w.get("ending_cash") or 0.0) < 0.0
    ]
    return {"items": alerts, "count": len(alerts), "as_of": as_of_now(), "entity_code": entity_code, "source": "treasury.forecast_13_week_proxy"}


@treasury_router.get("/payment-prioritization")
async def treasury_payment_prioritization(
    entity_code: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=200),
    current=Depends(get_current_user),
):
    # Reuse the AP prioritization proxy for treasury liquidity planning surfaces.
    return await ap_payment_prioritization(entity_code=entity_code, limit=limit, current=current)


# Backwards-compatible alias kept for older UI paths.
@treasury_router.get("/cash-forecast-13w")
async def treasury_cash_forecast_13w(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    data = await treasury_forecast_13_week(entity_code=entity_code, current=current)
    return {**data, "note": "Alias endpoint; prefer /treasury/forecast-13-week"}


@budget_router.get("/versions")
async def budget_versions(
    entity_code: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    """Immutable budget versions (Wave 2 data model placeholder)."""
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    cur = db.budget_versions.find(
        {"entity": entity_code} if entity_code else {},
        {"_id": 0},
    ).sort("created_at", -1).limit(50)
    items = [v async for v in cur]
    return {"items": items, "count": len(items), "as_of": as_of_now(), "note": "Seed budget_versions in Mongo for full workflow."}


@budget_router.get("")
async def budget_list(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    cur = db.budget_versions.find({"entity": entity_code} if entity_code else {}, {"_id": 0}).sort("created_at", -1).limit(50)
    items = [v async for v in cur]
    return {"items": items, "count": len(items), "as_of": as_of_now()}


@budget_router.post("/upload")
async def budget_upload(body: Dict[str, Any], current=Depends(get_current_user)):
    be = body.get("entity") or body.get("entity_code")
    if be and str(be).strip():
        await enforce_entity_scope(db, current=current, requested_entity_code=str(be))
    lines = body.get("lines")
    if lines is not None:
        if not isinstance(lines, list):
            raise HTTPException(400, "lines must be an array")
        for i, row in enumerate(lines):
            if not isinstance(row, dict):
                raise HTTPException(400, f"lines[{i}] must be an object")
            code = str(row.get("account_code") or row.get("gl_account") or "").strip()
            if not code:
                raise HTTPException(400, f"lines[{i}] requires account_code or gl_account")
            amt = row.get("amount")
            if amt is None:
                raise HTTPException(400, f"lines[{i}] requires amount")
            try:
                float(amt)
            except (TypeError, ValueError) as e:
                raise HTTPException(400, f"lines[{i}] amount must be numeric") from e
    bid = f"bud-{__import__('uuid').uuid4().hex[:10]}"
    doc = {
        **body,
        "id": bid,
        "status": body.get("status") or "draft",
        "locked": bool(body.get("locked") or False),
        "approved_by": None,
        "approved_at": None,
        "created_at": as_of_now(),
        "created_by": current.get("email"),
    }
    await db.budget_versions.insert_one(dict(doc))
    await audit_log(current["email"], "budget_upload", "budget_version", bid, {"entity": body.get("entity"), "name": body.get("name")})
    return {"status": "ok", "budget_id": bid, "as_of": as_of_now()}


# Phase 13 — Budget vs Actual dashboard + variance workflow
# IMPORTANT: define fixed paths BEFORE `/{budget_id}` to avoid route shadowing.
@budget_router.get("/budget-vs-actual")
async def budget_vs_actual_alias(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    kw = await _enforce_scope(current, entity_code, period_ym, department_id, cost_center_id)
    fpa = await fpa_dashboard(db, **kw)
    return {"as_of": as_of_now(), "source": "analytics.fpa_dashboard", "data": fpa}


@budget_router.get("/vs-actual")
async def budget_vs_actual(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    kw = await _enforce_scope(current, entity_code, period_ym, department_id, cost_center_id)
    fpa = await fpa_dashboard(db, **kw)
    return {"source": "analytics.fpa_dashboard", "data": fpa}


# Phase 14 — Forecast vs Actual + Forecast accuracy/bias
@forecast_router.post("/upload")
async def forecast_upload(body: Dict[str, Any], current=Depends(get_current_user)):
    be = body.get("entity") or body.get("entity_code")
    if be and str(be).strip():
        await enforce_entity_scope(db, current=current, requested_entity_code=str(be))
    fid = f"fct-{__import__('uuid').uuid4().hex[:10]}"
    doc = {
        **body,
        "id": fid,
        "status": body.get("status") or "draft",
        "created_at": as_of_now(),
        "created_by": current.get("email"),
    }
    await db.forecast_versions.insert_one(dict(doc))
    await audit_log(current["email"], "forecast_upload", "forecast_version", fid, {"entity": body.get("entity"), "name": body.get("name")})
    return {"status": "ok", "forecast_id": fid, "as_of": as_of_now()}


@forecast_router.get("")
async def forecast_list(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    cur = db.forecast_versions.find({"entity": entity_code} if entity_code else {}, {"_id": 0}).sort("created_at", -1).limit(50)
    items = [v async for v in cur]
    return {"items": items, "count": len(items), "as_of": as_of_now()}


@forecast_router.get("/vs-actual")
async def forecast_vs_actual(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    # Seed-friendly: compare latest forecast lines vs a simple "actual proxy" derived from forecast itself.
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    f = await db.forecast_versions.find_one({"entity": entity_code} if entity_code else {}, {"_id": 0}, sort=[("created_at", -1)])
    lines = (f or {}).get("lines") or []
    rows = []
    for ln in lines[:200]:
        if period_ym and ln.get("period_ym") != period_ym:
            continue
        fc = float(ln.get("amount") or 0.0)
        act = round(fc * 0.95, 2)  # placeholder until actuals pipeline exists
        var = round(act - fc, 2)
        rows.append(
            {
                "period_ym": ln.get("period_ym"),
                "gl_account": ln.get("gl_account"),
                "forecast_amount": fc,
                "actual_amount": act,
                "variance": var,
                "abs_variance": abs(var),
            }
        )
    rows.sort(key=lambda r: -float(r.get("abs_variance") or 0.0))
    return {"items": rows[:200], "count": len(rows), "as_of": as_of_now(), "entity_code": entity_code, "source": "forecast_vs_actual_proxy"}


@forecast_router.get("/accuracy")
async def forecast_accuracy(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    data = await forecast_vs_actual(entity_code=entity_code, period_ym=None, current=current)
    items = data.get("items") or []
    enc = data.get("entity_code")
    if not items:
        return {"as_of": as_of_now(), "entity_code": enc, "found": False, "mape": None, "bias": None, "count": 0}
    # MAPE + bias based on proxy items
    ape = []
    errs = []
    for r in items:
        fc = float(r.get("forecast_amount") or 0.0)
        act = float(r.get("actual_amount") or 0.0)
        if act != 0:
            ape.append(abs(act - fc) / abs(act))
        errs.append(act - fc)
    mape = round(100.0 * (sum(ape) / max(len(ape), 1)), 2) if ape else None
    bias = round(sum(errs) / max(len(errs), 1), 2) if errs else None
    return {"as_of": as_of_now(), "entity_code": enc, "found": True, "mape_pct": mape, "bias_amount": bias, "count": len(items)}


@forecast_router.post("/variance/{variance_id}/comment")
async def forecast_variance_comment(variance_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    fv = await db.forecast_variances.find_one({"id": variance_id}, {"_id": 0, "entity": 1})
    if fv and fv.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=fv.get("entity"))
    cid = f"c-{__import__('uuid').uuid4().hex[:8]}"
    item = {"id": cid, "text": str(body.get("text") or ""), "by": current.get("email"), "at": as_of_now()}
    await db.forecast_variances.update_one({"id": variance_id}, {"$push": {"comments": item}, "$set": {"updated_at": as_of_now()}}, upsert=True)
    await audit_log(current["email"], "forecast_variance_comment", "forecast_variance", variance_id, {"comment_id": cid})
    return {"status": "ok", "comment_id": cid, "as_of": as_of_now()}


@budget_router.get("/variance")
async def budget_variance_list(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current=Depends(get_current_user),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    if period_ym:
        q["period_ym"] = period_ym

    # Seed-friendly behavior: if no variances exist, synthesize a small set
    # from the latest budget and spend proxy, then persist for workflow actions.
    if await db.budget_variances.count_documents(q) == 0:
        b = await db.budget_versions.find_one({"entity": entity_code} if entity_code else {}, {"_id": 0}, sort=[("created_at", -1)])
        if b:
            lines = b.get("lines") or []
            for i, ln in enumerate(lines[:20]):
                v_id = f"var-{b.get('id','bud')}-{i}"
                bud = float(ln.get("amount") or 0.0)
                act = round(bud * 0.9, 2)
                var = round(act - bud, 2)
                doc = {
                    "id": v_id,
                    "entity": b.get("entity"),
                    "period_ym": ln.get("period_ym"),
                    "gl_account": ln.get("gl_account"),
                    "budget_amount": bud,
                    "actual_amount": act,
                    "variance": var,
                    "abs_variance": abs(var),
                    "status": "open",
                    "comments": [],
                    "created_at": as_of_now(),
                }
                await db.budget_variances.update_one({"id": v_id}, {"$setOnInsert": doc}, upsert=True)

    cur = db.budget_variances.find(q, {"_id": 0}).sort("abs_variance", -1).skip(offset).limit(limit)
    items = [x async for x in cur]
    total = await db.budget_variances.count_documents(q)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": as_of_now()}


@budget_router.get("/variance/{variance_id}")
async def budget_variance_get(variance_id: str, current=Depends(get_current_user)):
    v = await db.budget_variances.find_one({"id": variance_id}, {"_id": 0})
    if not v:
        return {"id": variance_id, "found": False, "as_of": as_of_now()}
    if v.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=v.get("entity"))
    return {"variance": v, "found": True, "as_of": as_of_now()}


@budget_router.post("/variance/{variance_id}/comment")
async def budget_variance_comment(variance_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    v = await db.budget_variances.find_one({"id": variance_id}, {"_id": 0, "entity": 1})
    if v and v.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=v.get("entity"))
    comment_id = f"c-{__import__('uuid').uuid4().hex[:8]}"
    item = {"id": comment_id, "text": str(body.get("text") or ""), "by": current.get("email"), "at": as_of_now()}
    await db.budget_variances.update_one({"id": variance_id}, {"$push": {"comments": item}, "$set": {"updated_at": as_of_now()}})
    await audit_log(current["email"], "budget_variance_comment", "budget_variance", variance_id, {"comment_id": comment_id})
    return {"status": "ok", "comment_id": comment_id, "as_of": as_of_now()}


@budget_router.post("/variance/{variance_id}/approve-explanation")
async def budget_variance_approve_explanation(variance_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    v = await db.budget_variances.find_one({"id": variance_id}, {"_id": 0, "entity": 1})
    if v and v.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=v.get("entity"))
    explanation = body.get("explanation")
    res = await db.budget_variances.update_one(
        {"id": variance_id},
        {"$set": {"explanation": explanation, "explanation_status": "approved", "approved_by": current.get("email"), "approved_at": as_of_now()}},
    )
    await audit_log(current["email"], "budget_variance_approve_explanation", "budget_variance", variance_id, {})
    return {"status": "ok", "matched": res.matched_count, "modified": res.modified_count, "as_of": as_of_now()}


@budget_router.get("/{budget_id}")
async def budget_get(budget_id: str, current=Depends(get_current_user)):
    b = await db.budget_versions.find_one({"id": budget_id}, {"_id": 0})
    if not b:
        return {"id": budget_id, "found": False, "as_of": as_of_now()}
    if b.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=b.get("entity"))
    return {"budget": b, "found": True, "as_of": as_of_now()}


@budget_router.post("/{budget_id}/approve")
async def budget_approve(budget_id: str, current=Depends(get_current_user)):
    b = await db.budget_versions.find_one({"id": budget_id}, {"_id": 0, "entity": 1})
    if b and b.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=b.get("entity"))
    res = await db.budget_versions.update_one(
        {"id": budget_id},
        {"$set": {"status": "approved", "approved_by": current.get("email"), "approved_at": as_of_now()}},
    )
    await audit_log(current["email"], "budget_approve", "budget_version", budget_id, {})
    return {"status": "ok", "matched": res.matched_count, "modified": res.modified_count, "as_of": as_of_now()}


@budget_router.post("/{budget_id}/lock")
async def budget_lock(budget_id: str, current=Depends(get_current_user)):
    b = await db.budget_versions.find_one({"id": budget_id}, {"_id": 0, "entity": 1})
    if b and b.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=b.get("entity"))
    res = await db.budget_versions.update_one(
        {"id": budget_id},
        {"$set": {"locked": True, "locked_at": as_of_now(), "locked_by": current.get("email")}},
    )
    await audit_log(current["email"], "budget_lock", "budget_version", budget_id, {})
    return {"status": "ok", "matched": res.matched_count, "modified": res.modified_count, "as_of": as_of_now()}


@budget_router.post("/{budget_id}/unlock")
async def budget_unlock(budget_id: str, current=Depends(get_current_user)):
    b = await db.budget_versions.find_one({"id": budget_id}, {"_id": 0, "entity": 1})
    if b and b.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=b.get("entity"))
    res = await db.budget_versions.update_one(
        {"id": budget_id},
        {"$set": {"locked": False, "unlocked_at": as_of_now(), "unlocked_by": current.get("email")}},
    )
    await audit_log(current["email"], "budget_unlock", "budget_version", budget_id, {})
    return {"status": "ok", "matched": res.matched_count, "modified": res.modified_count, "as_of": as_of_now()}


# --- SRS top-level aliases (integrator docs) — same payloads as nested routes ---
srs_budget_vs_actual_router = APIRouter(prefix="/budget-vs-actual", tags=["budget-srs-alias"])


@srs_budget_vs_actual_router.get("")
async def srs_get_budget_vs_actual(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    """SRS: ``GET /api/budget-vs-actual`` — canonical: ``GET /api/budget/budget-vs-actual``."""
    kw = await _enforce_scope(current, entity_code, period_ym, department_id, cost_center_id)
    fpa = await fpa_dashboard(db, **kw)
    return {
        "as_of": as_of_now(),
        "source": "analytics.fpa_dashboard",
        "data": fpa,
        "canonical_paths": ["/api/budget/budget-vs-actual", "/api/budget/vs-actual"],
    }


srs_forecast_vs_actual_router = APIRouter(prefix="/forecast-vs-actual", tags=["forecast-srs-alias"])


@srs_forecast_vs_actual_router.get("")
async def srs_get_forecast_vs_actual(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    """SRS: ``GET /api/forecast-vs-actual`` — canonical: ``GET /api/forecast/vs-actual``."""
    return await forecast_vs_actual(entity_code=entity_code, period_ym=period_ym, current=current)
