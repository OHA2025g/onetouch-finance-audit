"""Phase 21 — Customer, Revenue and O2C Audit (seed-backed)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.deps import audit_log, db
from app.services.kpi_service import as_of_now


router = APIRouter(prefix="/o2c", tags=["o2c"])


def _parse_dt(s: Any) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:  # noqa: BLE001
        return None


@router.get("/summary")
async def o2c_summary(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    cust_q: Dict[str, Any] = {}
    if entity_code:
        cust_q["entity"] = entity_code
    customers = [c async for c in db.customers.find(cust_q, {"_id": 0}).limit(2000)]

    inv_q: Dict[str, Any] = {"status": {"$in": ["open", "paid"]}}
    if entity_code:
        inv_q["entity"] = entity_code
    inv_total = await db.ar_invoices.count_documents(inv_q)
    open_total = 0.0
    async for inv in db.ar_invoices.find({**inv_q, "status": "open"}, {"_id": 0, "amount": 1}):
        open_total += float(inv.get("amount") or 0.0)

    return {
        "as_of": as_of_now(),
        "entity_code": entity_code,
        "kpis": {
            "customer_count": len(customers),
            "ar_invoice_count": inv_total,
            "ar_open_amount": round(open_total, 2),
        },
        "source": "phase2.customers+ar_invoices",
    }


@router.get("/customers")
async def o2c_customers(
    entity_code: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current=Depends(get_current_user),
):
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


@router.get("/customers/{customer_id}")
async def o2c_customer_detail(customer_id: str, current=Depends(get_current_user)):
    c = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not c:
        c = await db.customers.find_one({"customer_code": customer_id}, {"_id": 0})
    if not c:
        return {"id": customer_id, "found": False, "as_of": as_of_now()}
    open_amt = 0.0
    async for inv in db.ar_invoices.find({"customer_id": c["id"], "status": "open"}, {"_id": 0, "amount": 1}):
        open_amt += float(inv.get("amount") or 0.0)
    return {"customer": c, "ar_open_amount": round(open_amt, 2), "found": True, "as_of": as_of_now()}


@router.get("/revenue-cutoff")
async def o2c_revenue_cutoff(entity_code: Optional[str] = Query(None), limit: int = Query(50, ge=1, le=500), current=Depends(get_current_user)):
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    # Cutoff risk proxy: shipment_date AFTER invoice_date by >3 days, or shipment after month-end (as seeded by Phase 2)
    cur = db.ar_invoices.find(q, {"_id": 0}).sort("invoice_date", -1).limit(1500)
    flagged = []
    async for inv in cur:
        inv_dt = _parse_dt(inv.get("invoice_date"))
        ship_dt = _parse_dt(inv.get("shipment_date"))
        if not inv_dt or not ship_dt:
            continue
        if (ship_dt - inv_dt).days >= 5:
            flagged.append(inv)
    flagged.sort(key=lambda x: x.get("invoice_date") or "", reverse=True)
    return {"items": flagged[:limit], "count": len(flagged), "as_of": as_of_now(), "note": "Cutoff proxy: shipment_date >= invoice_date + 5d"}


@router.get("/credit-limit-breaches")
async def o2c_credit_limit_breaches(entity_code: Optional[str] = Query(None), limit: int = Query(50, ge=1, le=500), current=Depends(get_current_user)):
    cust_q: Dict[str, Any] = {}
    if entity_code:
        cust_q["entity"] = entity_code
    customers = [c async for c in db.customers.find(cust_q, {"_id": 0}).limit(2000)]
    breaches = []
    for c in customers:
        open_amt = 0.0
        async for inv in db.ar_invoices.find({"customer_id": c["id"], "status": "open"}, {"_id": 0, "amount": 1}):
            open_amt += float(inv.get("amount") or 0.0)
        if open_amt > float(c.get("credit_limit") or 0.0):
            breaches.append(
                {
                    "customer_id": c["id"],
                    "customer_name": c.get("customer_name"),
                    "entity": c.get("entity"),
                    "credit_limit": c.get("credit_limit"),
                    "open_ar_amount": round(open_amt, 2),
                    "breach_amount": round(open_amt - float(c.get("credit_limit") or 0.0), 2),
                    "severity": "critical" if open_amt > 1.5 * float(c.get("credit_limit") or 1.0) else "high",
                }
            )
    breaches.sort(key=lambda b: -float(b.get("breach_amount") or 0.0))
    return {"items": breaches[:limit], "count": len(breaches), "as_of": as_of_now()}


@router.get("/customer-concentration")
async def o2c_customer_concentration(entity_code: Optional[str] = Query(None), limit: int = Query(10, ge=1, le=50), current=Depends(get_current_user)):
    q: Dict[str, Any] = {"status": {"$in": ["open", "paid"]}}
    if entity_code:
        q["entity"] = entity_code
    totals: Dict[str, float] = {}
    names: Dict[str, str] = {}
    async for inv in db.ar_invoices.find(q, {"_id": 0, "customer_id": 1, "customer_name": 1, "amount": 1}):
        cid = inv.get("customer_id")
        if not cid:
            continue
        totals[cid] = totals.get(cid, 0.0) + float(inv.get("amount") or 0.0)
        names[cid] = inv.get("customer_name") or names.get(cid) or cid
    rows = [{"customer_id": cid, "customer_name": names.get(cid), "amount": round(amt, 2)} for cid, amt in totals.items()]
    rows.sort(key=lambda r: -float(r.get("amount") or 0.0))
    return {"items": rows[:limit], "count": len(rows), "as_of": as_of_now()}


@router.post("/{customer_id}/create-case")
async def o2c_create_case(customer_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    c = await db.customers.find_one({"id": customer_id}, {"_id": 0})
    if not c:
        c = await db.customers.find_one({"customer_code": customer_id}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Customer not found")

    now = as_of_now()
    cid = f"case-o2c-{__import__('uuid').uuid4().hex[:10]}"
    ex_id = f"o2c-{c['id']}"

    ex_doc = {
        "id": ex_id,
        "control_id": "C-OTC-001",
        "control_code": "C-OTC-001",
        "control_name": "Customer Credit Limit Breach",
        "process": "Order-to-Cash",
        "entity": c.get("entity") or current.get("entity") or "US-HQ",
        "severity": str(body.get("severity") or "high"),
        "status": "open",
        "materiality_score": float(body.get("materiality_score") or 0.4),
        "anomaly_score": float(body.get("anomaly_score") or 0.4),
        "financial_exposure": float(body.get("financial_exposure") or 0.0),
        "source_record_type": "customer",
        "source_record_id": c["id"],
        "detected_at": now,
        "title": body.get("title") or f"O2C follow-up for {c.get('customer_name')}",
        "summary": body.get("summary") or "Case created from O2C module.",
        "recurrence_count": 0,
        "department_id": None,
        "cost_center_id": None,
    }
    await db.exceptions.update_one({"id": ex_id}, {"$setOnInsert": ex_doc}, upsert=True)

    case_doc = {
        "id": cid,
        "exception_id": ex_id,
        "control_code": ex_doc["control_code"],
        "control_name": ex_doc["control_name"],
        "title": ex_doc["title"],
        "summary": ex_doc["summary"],
        "severity": ex_doc["severity"],
        "status": "open",
        "priority": body.get("priority") or "P1",
        "owner_email": body.get("owner_email") or current.get("email"),
        "owner_name": None,
        "due_date": body.get("due_date") or now,
        "financial_exposure": float(ex_doc.get("financial_exposure") or 0.0),
        "entity": ex_doc["entity"],
        "process": ex_doc["process"],
        "detected_at": now,
        "opened_at": now,
        "closed_at": None,
        "root_cause_category": None,
        "engagement_id": None,
        "material_impact": body.get("material_impact"),
        "material_watch": None,
        "department_id": None,
        "cost_center_id": None,
    }
    await db.cases.insert_one(dict(case_doc))
    await audit_log(current["email"], "o2c_create_case", "case", cid, {"customer_id": c["id"]})
    return {"status": "ok", "case_id": cid, "exception_id": ex_id, "as_of": as_of_now()}

