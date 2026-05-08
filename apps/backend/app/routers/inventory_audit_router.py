"""Phase 23 — Inventory Audit & Valuation (seed-friendly)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.deps import audit_log, db
from app.services.kpi_service import as_of_now


router = APIRouter(prefix="/inventory-audit", tags=["inventory-audit"])


def _now() -> str:
    return as_of_now()


async def _ensure_seed_inventory(entity_code: Optional[str] = None) -> int:
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    existing = await db.inventory_items.count_documents(q)
    if existing > 0:
        return 0

    # Synthesize inventory items from invoices (vendor names as pseudo SKUs) to keep it deterministic.
    inv_q: Dict[str, Any] = {}
    if entity_code:
        inv_q["entity"] = entity_code
    invs = [i async for i in db.invoices.find(inv_q, {"_id": 0}).sort("invoice_date", -1).limit(120)]
    if not invs:
        return 0

    now = datetime.now(timezone.utc)
    docs = []
    for idx, inv in enumerate(invs[:40]):
        qty = int((idx % 7) + 1) * 10
        unit_cost = round(float(inv.get("amount") or 0.0) / max(qty, 1), 2)
        received_at = datetime.fromisoformat(str(inv.get("invoice_date")).replace("Z", "+00:00")) if inv.get("invoice_date") else now
        # Make a few items slow/non-moving and some negative stock / NRV flags.
        last_moved = received_at + timedelta(days=(idx % 5) * 10)
        if idx % 9 == 0:
            last_moved = now - timedelta(days=240)
        on_hand = qty if idx % 13 else -5
        nrv = round(unit_cost * (0.85 if idx % 11 == 0 else 1.05), 2)
        docs.append(
            {
                "id": f"SKU-{idx:04d}",
                "sku": f"SKU-{idx:04d}",
                "description": f"Item {idx:04d} ({inv.get('vendor_name','')})",
                "entity": inv.get("entity"),
                "category": "raw_material" if idx % 3 else "finished_goods",
                "received_at": received_at.astimezone(timezone.utc).isoformat(),
                "last_moved_at": last_moved.astimezone(timezone.utc).isoformat(),
                "qty_on_hand": on_hand,
                "unit_cost": unit_cost,
                "nrv_unit": nrv,
                "valuation_method": "weighted_avg",
                "created_at": _now(),
            }
        )
    if docs:
        await db.inventory_items.insert_many(docs)
    return len(docs)


@router.get("/summary")
async def inventory_summary(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    await _ensure_seed_inventory(entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    total_items = await db.inventory_items.count_documents(q)
    total_value = 0.0
    negative_stock = 0
    nrv_issues = 0
    async for it in db.inventory_items.find(q, {"_id": 0}).limit(3000):
        qty = float(it.get("qty_on_hand") or 0.0)
        if qty < 0:
            negative_stock += 1
        unit_cost = float(it.get("unit_cost") or 0.0)
        nrv = float(it.get("nrv_unit") or 0.0)
        if nrv < unit_cost:
            nrv_issues += 1
        total_value += max(qty, 0.0) * unit_cost
    return {
        "as_of": _now(),
        "entity_code": entity_code,
        "kpis": {
            "item_count": total_items,
            "inventory_value": round(total_value, 2),
            "negative_stock_items": negative_stock,
            "nrv_issues": nrv_issues,
        },
        "source": "inventory_items (synthesized if empty)",
    }


@router.get("/ageing")
async def inventory_ageing(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    await _ensure_seed_inventory(entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    now = datetime.now(timezone.utc)
    buckets = {"0-30": 0.0, "31-90": 0.0, "91-180": 0.0, "181+": 0.0}
    async for it in db.inventory_items.find(q, {"_id": 0, "received_at": 1, "qty_on_hand": 1, "unit_cost": 1}):
        rdt = datetime.fromisoformat(str(it.get("received_at")).replace("Z", "+00:00"))
        age = (now - rdt).days
        val = max(float(it.get("qty_on_hand") or 0.0), 0.0) * float(it.get("unit_cost") or 0.0)
        if age <= 30:
            buckets["0-30"] += val
        elif age <= 90:
            buckets["31-90"] += val
        elif age <= 180:
            buckets["91-180"] += val
        else:
            buckets["181+"] += val
    return {"items": [{"bucket": k, "value": round(v, 2)} for k, v in buckets.items()], "as_of": _now(), "entity_code": entity_code}


@router.get("/slow-moving")
async def inventory_slow_moving(entity_code: Optional[str] = Query(None), days: int = Query(180, ge=30, le=720), limit: int = Query(50, ge=1, le=500), current=Depends(get_current_user)):
    await _ensure_seed_inventory(entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    now = datetime.now(timezone.utc)
    cur = db.inventory_items.find(q, {"_id": 0}).limit(3000)
    flagged = []
    async for it in cur:
        ldt = datetime.fromisoformat(str(it.get("last_moved_at")).replace("Z", "+00:00"))
        if (now - ldt).days >= int(days):
            flagged.append(it)
    flagged.sort(key=lambda x: x.get("last_moved_at") or "")
    return {"items": flagged[:limit], "count": len(flagged), "as_of": _now(), "note": f"Slow-moving proxy: last_moved_at >= {days}d"}


@router.get("/valuation-exceptions")
async def inventory_valuation_exceptions(entity_code: Optional[str] = Query(None), limit: int = Query(50, ge=1, le=500), current=Depends(get_current_user)):
    await _ensure_seed_inventory(entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    cur = db.inventory_items.find(q, {"_id": 0}).limit(3000)
    out = []
    async for it in cur:
        unit_cost = float(it.get("unit_cost") or 0.0)
        nrv = float(it.get("nrv_unit") or 0.0)
        if nrv < unit_cost or float(it.get("qty_on_hand") or 0.0) < 0:
            out.append(
                {
                    **it,
                    "issue": "nrv_below_cost" if nrv < unit_cost else "negative_stock",
                    "delta_per_unit": round(nrv - unit_cost, 2),
                }
            )
    out.sort(key=lambda x: x.get("delta_per_unit") or 0.0)
    return {"items": out[:limit], "count": len(out), "as_of": _now()}


@router.get("/adjustments")
async def inventory_adjustments(entity_code: Optional[str] = Query(None), limit: int = Query(50, ge=1, le=500), current=Depends(get_current_user)):
    # No real adjustments in seed; expose stable surface backed by optional collection.
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    cur = db.inventory_adjustments.find(q, {"_id": 0}).sort("created_at", -1).limit(limit)
    items = [x async for x in cur]
    return {"items": items, "count": len(items), "as_of": _now(), "note": "Seed inventory_adjustments for full adjustment audit."}


@router.post("/{inventory_id}/create-case")
async def inventory_create_case(inventory_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    it = await db.inventory_items.find_one({"id": inventory_id}, {"_id": 0})
    if not it:
        raise HTTPException(404, "Inventory item not found")

    now = _now()
    cid = f"case-inv-{__import__('uuid').uuid4().hex[:10]}"
    ex_id = f"inv-{inventory_id}"

    exposure = max(float(it.get("qty_on_hand") or 0.0), 0.0) * float(it.get("unit_cost") or 0.0)

    ex_doc = {
        "id": ex_id,
        "control_id": "C-INV-001",
        "control_code": "INV-001",
        "control_name": "Inventory valuation / ageing exception",
        "process": "Financial Audit",
        "entity": it.get("entity") or current.get("entity") or "US-HQ",
        "severity": str(body.get("severity") or "medium"),
        "status": "open",
        "materiality_score": float(body.get("materiality_score") or 0.3),
        "anomaly_score": float(body.get("anomaly_score") or 0.3),
        "financial_exposure": float(body.get("financial_exposure") or exposure),
        "source_record_type": "inventory_item",
        "source_record_id": inventory_id,
        "detected_at": now,
        "title": body.get("title") or f"Inventory audit follow-up: {inventory_id}",
        "summary": body.get("summary") or "Case created from Inventory Audit module.",
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
    await audit_log(current["email"], "inventory_create_case", "case", cid, {"inventory_id": inventory_id})
    return {"status": "ok", "case_id": cid, "exception_id": ex_id, "as_of": _now()}

