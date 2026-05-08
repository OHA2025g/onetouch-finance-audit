"""Phase 24 — Physical Verification & Stock Variance (seed-backed workflow)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.deps import audit_log, db
from app.services.kpi_service import as_of_now


router = APIRouter(prefix="/physical-verification", tags=["physical-verification"])


def _now() -> str:
    return as_of_now()


@router.get("/cycles")
async def pv_cycles(entity_code: Optional[str] = Query(None), limit: int = Query(50, ge=1, le=500), current=Depends(get_current_user)):
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    cur = db.physical_cycles.find(q, {"_id": 0}).sort("created_at", -1).limit(limit)
    items = [c async for c in cur]
    return {"items": items, "count": len(items), "as_of": _now()}


@router.post("/cycles")
async def pv_create_cycle(body: Dict[str, Any], current=Depends(get_current_user)):
    cid = f"pvc-{__import__('uuid').uuid4().hex[:10]}"
    doc = {
        **body,
        "id": cid,
        "entity": body.get("entity") or current.get("entity") or "US-HQ",
        "status": body.get("status") or "open",
        "created_at": _now(),
        "created_by": current.get("email"),
    }
    await db.physical_cycles.insert_one(dict(doc))
    await audit_log(current["email"], "physical_cycle_create", "physical_cycle", cid, {"entity": doc.get("entity")})
    return {"status": "ok", "cycle_id": cid, "as_of": _now()}


@router.post("/{cycle_id}/upload-count")
async def pv_upload_count(cycle_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    """Upload counts via JSON payload for container-friendly tests.

    body: { items: [{sku, counted_qty}] }
    """
    cyc = await db.physical_cycles.find_one({"id": cycle_id}, {"_id": 0})
    if not cyc:
        raise HTTPException(404, "Cycle not found")
    upl_id = f"pvu-{__import__('uuid').uuid4().hex[:10]}"
    items = body.get("items") or []
    doc = {
        "id": upl_id,
        "cycle_id": cycle_id,
        "entity": cyc.get("entity"),
        "items": items,
        "created_at": _now(),
        "created_by": current.get("email"),
    }
    await db.physical_counts.insert_one(dict(doc))
    await audit_log(current["email"], "physical_count_upload", "physical_cycle", cycle_id, {"upload_id": upl_id, "count": len(items)})
    return {"status": "ok", "upload_id": upl_id, "as_of": _now()}


async def _compute_variances(cycle_id: str) -> list[Dict[str, Any]]:
    cyc = await db.physical_cycles.find_one({"id": cycle_id}, {"_id": 0})
    if not cyc:
        return []
    entity = cyc.get("entity")
    latest = await db.physical_counts.find_one({"cycle_id": cycle_id}, {"_id": 0}, sort=[("created_at", -1)])
    counts = (latest or {}).get("items") or []
    counted_map = {c.get("sku"): float(c.get("counted_qty") or 0.0) for c in counts if c.get("sku")}

    inv_q: Dict[str, Any] = {}
    if entity:
        inv_q["entity"] = entity
    inv_items = [i async for i in db.inventory_items.find(inv_q, {"_id": 0, "id": 1, "sku": 1, "qty_on_hand": 1, "unit_cost": 1}).limit(3000)]
    variances = []
    for it in inv_items:
        sku = it.get("sku") or it.get("id")
        if sku not in counted_map:
            continue
        book = float(it.get("qty_on_hand") or 0.0)
        phys = float(counted_map.get(sku) or 0.0)
        diff = phys - book
        if diff == 0:
            continue
        unit_cost = float(it.get("unit_cost") or 0.0)
        variances.append(
            {
                "id": f"pvvar-{cycle_id}-{sku}",
                "cycle_id": cycle_id,
                "entity": entity,
                "sku": sku,
                "book_qty": book,
                "physical_qty": phys,
                "variance_qty": diff,
                "variance_value": round(diff * unit_cost, 2),
                "status": "open",
                "reason": None,
                "approved": False,
                "created_at": _now(),
            }
        )
    # Upsert for stable ids
    for v in variances:
        await db.physical_variances.update_one({"id": v["id"]}, {"$set": v}, upsert=True)
    return variances


@router.get("/{cycle_id}/variance")
async def pv_variance(cycle_id: str, current=Depends(get_current_user)):
    items = await _compute_variances(cycle_id)
    return {"items": items, "count": len(items), "as_of": _now()}


@router.post("/variance/{variance_id}/reason")
async def pv_reason(variance_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    reason = body.get("reason")
    await db.physical_variances.update_one({"id": variance_id}, {"$set": {"reason": reason, "updated_at": _now(), "updated_by": current.get("email")}})
    await audit_log(current["email"], "physical_variance_reason", "physical_variance", variance_id, {"reason": reason})
    return {"status": "ok", "as_of": _now()}


@router.post("/variance/{variance_id}/approve")
async def pv_approve(variance_id: str, current=Depends(get_current_user)):
    await db.physical_variances.update_one({"id": variance_id}, {"$set": {"approved": True, "approved_at": _now(), "approved_by": current.get("email"), "status": "approved"}})
    await audit_log(current["email"], "physical_variance_approve", "physical_variance", variance_id, {})
    return {"status": "ok", "as_of": _now()}


@router.post("/variance/{variance_id}/create-case")
async def pv_create_case(variance_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    v = await db.physical_variances.find_one({"id": variance_id}, {"_id": 0})
    if not v:
        raise HTTPException(404, "Variance not found")
    now = _now()
    cid = f"case-pv-{__import__('uuid').uuid4().hex[:10]}"
    ex_id = f"pv-{variance_id}"

    exposure = abs(float(v.get("variance_value") or 0.0))
    ex_doc = {
        "id": ex_id,
        "control_id": "C-PV-001",
        "control_code": "PV-001",
        "control_name": "Physical stock variance",
        "process": "Financial Audit",
        "entity": v.get("entity") or current.get("entity") or "US-HQ",
        "severity": str(body.get("severity") or ("high" if exposure > 20000 else "medium")),
        "status": "open",
        "materiality_score": float(body.get("materiality_score") or 0.4),
        "anomaly_score": float(body.get("anomaly_score") or 0.4),
        "financial_exposure": float(body.get("financial_exposure") or exposure),
        "source_record_type": "physical_variance",
        "source_record_id": variance_id,
        "detected_at": now,
        "title": body.get("title") or f"Physical variance follow-up: {v.get('sku')}",
        "summary": body.get("summary") or "Case created from Physical Verification module.",
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
        "priority": body.get("priority") or "P2",
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
    await audit_log(current["email"], "physical_variance_create_case", "case", cid, {"variance_id": variance_id})
    return {"status": "ok", "case_id": cid, "exception_id": ex_id, "as_of": _now()}

