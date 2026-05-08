"""Phase 19 — Vendor Risk & Procurement Audit (seed-backed)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from app.auth import get_current_user
from app.deps import audit_log, db
from app.services.kpi_service import as_of_now


router = APIRouter(prefix="/vendor-risk", tags=["vendor-risk"])


def _parse_dt(s: Any) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:  # noqa: BLE001
        return None


async def _vendor_open_invoices_total(vendor_id: str) -> float:
    total = 0.0
    async for inv in db.invoices.find({"vendor_id": vendor_id, "status": {"$in": ["open", "posted"]}}, {"_id": 0, "amount": 1}):
        total += float(inv.get("amount") or 0.0)
    return round(total, 2)


@router.get("/summary")
async def vendor_risk_summary(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    vendors = [v async for v in db.vendors.find(q, {"_id": 0})]
    vendor_ids = [v["id"] for v in vendors]

    dup_vendor_count = 0
    pan_seen = set()
    gst_seen = set()
    for v in vendors:
        pan = v.get("pan")
        gst = v.get("gstin")
        if pan and pan in pan_seen:
            dup_vendor_count += 1
        if gst and gst in gst_seen:
            dup_vendor_count += 1
        if pan:
            pan_seen.add(pan)
        if gst:
            gst_seen.add(gst)

    # bank change alerts: changed in last 14 days
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=14)
    bank_changed = 0
    for v in vendors:
        dt = _parse_dt(v.get("bank_changed_at"))
        if dt and dt >= cutoff:
            bank_changed += 1

    inv_q: Dict[str, Any] = {}
    if entity_code:
        inv_q["entity"] = entity_code
    inv_total = await db.invoices.count_documents(inv_q)
    pay_total = await db.payments.count_documents({"entity": entity_code} if entity_code else {})

    return {
        "as_of": as_of_now(),
        "entity_code": entity_code,
        "kpis": {
            "vendor_count": len(vendors),
            "duplicate_vendor_signals": dup_vendor_count,
            "recent_bank_changes": bank_changed,
            "invoice_count": inv_total,
            "payment_count": pay_total,
        },
        "source": "seed.vendors+invoices+payments",
    }


@router.get("/vendors")
async def vendor_risk_vendors(
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
        filt["$or"] = [{"vendor_name": rq}, {"vendor_code": rq}, {"id": rq}]
    cur = db.vendors.find(filt, {"_id": 0}).sort("vendor_code", 1).skip(offset).limit(limit)
    items = [v async for v in cur]
    total = await db.vendors.count_documents(filt)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": as_of_now()}


@router.get("/vendors/{vendor_id}")
async def vendor_risk_vendor_detail(vendor_id: str, current=Depends(get_current_user)):
    v = await db.vendors.find_one({"id": vendor_id}, {"_id": 0})
    if not v:
        v = await db.vendors.find_one({"vendor_code": vendor_id}, {"_id": 0})
    if not v:
        return {"id": vendor_id, "found": False, "as_of": as_of_now()}
    open_ap = await _vendor_open_invoices_total(v["id"])
    return {"vendor": v, "ap_open_amount": open_ap, "found": True, "as_of": as_of_now()}


@router.get("/duplicates")
async def vendor_risk_duplicates(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    vendors = [v async for v in db.vendors.find(q, {"_id": 0})]
    by_pan: Dict[str, list] = {}
    by_gst: Dict[str, list] = {}
    for v in vendors:
        if v.get("pan"):
            by_pan.setdefault(v["pan"], []).append(v)
        if v.get("gstin"):
            by_gst.setdefault(v["gstin"], []).append(v)
    pan_dups = [{"key": k, "vendors": vv} for k, vv in by_pan.items() if len(vv) > 1]
    gst_dups = [{"key": k, "vendors": vv} for k, vv in by_gst.items() if len(vv) > 1]
    return {"as_of": as_of_now(), "entity_code": entity_code, "pan_duplicates": pan_dups, "gstin_duplicates": gst_dups}


@router.get("/bank-change-alerts")
async def vendor_risk_bank_change_alerts(entity_code: Optional[str] = Query(None), days: int = Query(14, ge=1, le=120), current=Depends(get_current_user)):
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    vendors = [v async for v in db.vendors.find(q, {"_id": 0})]
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=int(days))
    alerts = []
    for v in vendors:
        dt = _parse_dt(v.get("bank_changed_at"))
        if dt and dt >= cutoff:
            alerts.append(
                {
                    "vendor_id": v["id"],
                    "vendor_name": v.get("vendor_name"),
                    "entity": v.get("entity"),
                    "bank_changed_at": v.get("bank_changed_at"),
                    "severity": "critical" if (now - dt).days <= 3 else "high",
                }
            )
    alerts.sort(key=lambda a: a.get("bank_changed_at") or "", reverse=True)
    return {"items": alerts, "count": len(alerts), "as_of": as_of_now()}


@router.get("/non-po-spend")
async def vendor_risk_non_po_spend(entity_code: Optional[str] = Query(None), limit: int = Query(50, ge=1, le=500), current=Depends(get_current_user)):
    q: Dict[str, Any] = {"po_id": None}
    if entity_code:
        q["entity"] = entity_code
    cur = db.invoices.find(q, {"_id": 0}).sort("amount", -1).limit(limit)
    items = [x async for x in cur]
    total = await db.invoices.count_documents(q)
    spend = sum(float(x.get("amount") or 0.0) for x in items)
    return {"items": items, "total": total, "top_spend_amount": round(spend, 2), "as_of": as_of_now(), "note": "Non-PO spend proxy: invoices with po_id=None"}


@router.get("/advances")
async def vendor_risk_advances(entity_code: Optional[str] = Query(None), limit: int = Query(100, ge=1, le=1000), current=Depends(get_current_user)):
    # Seed doesn’t explicitly model advances; expose a stable placeholder surface.
    return {"items": [], "count": 0, "as_of": as_of_now(), "entity_code": entity_code, "note": "Seed vendor advances in `vendor_advances` for ageing & concentration."}


@router.post("/{vendor_id}/create-case")
async def vendor_risk_create_case(vendor_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    v = await db.vendors.find_one({"id": vendor_id}, {"_id": 0})
    if not v:
        v = await db.vendors.find_one({"vendor_code": vendor_id}, {"_id": 0})
    if not v:
        return {"status": "not_found", "vendor_id": vendor_id, "as_of": as_of_now()}

    now = as_of_now()
    cid = f"case-vr-{__import__('uuid').uuid4().hex[:10]}"
    ex_id = f"vr-{vendor_id}"

    ex_doc = {
        "id": ex_id,
        "control_id": "C-VR-001",
        "control_code": "VR-001",
        "control_name": "Vendor risk follow-up",
        "process": "Procure-to-Pay",
        "entity": v.get("entity") or current.get("entity") or "US-HQ",
        "severity": str(body.get("severity") or "high"),
        "status": "open",
        "materiality_score": float(body.get("materiality_score") or 0.4),
        "anomaly_score": float(body.get("anomaly_score") or 0.4),
        "financial_exposure": float(body.get("financial_exposure") or 0.0),
        "source_record_type": "vendor",
        "source_record_id": v["id"],
        "detected_at": now,
        "title": body.get("title") or f"Vendor risk case for {v.get('vendor_name')}",
        "summary": body.get("summary") or "Vendor risk case created from Vendor Risk module.",
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
    await audit_log(current["email"], "vendor_risk_create_case", "case", cid, {"vendor_id": v["id"]})
    return {"status": "ok", "case_id": cid, "exception_id": ex_id, "as_of": as_of_now()}

