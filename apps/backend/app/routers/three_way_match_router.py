"""Phase 20 — Three-Way Match Engine (PO-GRN-Invoice matching, seed-backed)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.deps import audit_log, db
from app.services.kpi_service import as_of_now
from app.services.rbac_service import enforce_entity_scope


router = APIRouter(prefix="/three-way-match", tags=["three-way-match"])


def _now() -> str:
    return as_of_now()


async def _get_tolerances() -> Dict[str, Any]:
    tol = await db.three_way_match_tolerances.find_one({"id": "singleton"}, {"_id": 0})
    if tol:
        return tol
    tol = {
        "id": "singleton",
        "amount_tolerance_pct": 5.0,
        "amount_tolerance_abs": 500.0,
        "updated_at": _now(),
        "updated_by": "system",
    }
    await db.three_way_match_tolerances.insert_one(dict(tol))
    return tol


def _within_tol(inv_amt: float, po_amt: float, grn_amt: float, tol: Dict[str, Any]) -> bool:
    abs_tol = float(tol.get("amount_tolerance_abs") or 0.0)
    pct_tol = float(tol.get("amount_tolerance_pct") or 0.0) / 100.0
    max_base = max(abs(po_amt), abs(grn_amt), 1.0)
    band = max(abs_tol, pct_tol * max_base)
    return abs(inv_amt - po_amt) <= band and abs(inv_amt - grn_amt) <= band


async def _build_exception(inv: Dict[str, Any], tol: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    po_id = inv.get("po_id")
    if not po_id:
        return None
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
    if not po:
        return None
    grn = await db.goods_receipts.find_one({"po_id": po_id}, {"_id": 0})
    if not grn:
        return None

    inv_amt = float(inv.get("amount") or 0.0)
    po_amt = float(po.get("amount") or 0.0)
    grn_amt = float(grn.get("amount") or 0.0)
    if _within_tol(inv_amt, po_amt, grn_amt, tol):
        return None

    ex_id = f"twm-{inv.get('id')}"
    return {
        "id": ex_id,
        "entity": inv.get("entity"),
        "vendor_id": inv.get("vendor_id"),
        "invoice_id": inv.get("id"),
        "po_id": po_id,
        "grn_id": grn.get("id"),
        "invoice_amount": inv_amt,
        "po_amount": po_amt,
        "grn_amount": grn_amt,
        "variance_inv_po": round(inv_amt - po_amt, 2),
        "variance_inv_grn": round(inv_amt - grn_amt, 2),
        "status": "open",
        "severity": "high" if abs(inv_amt - po_amt) > 5000 else "medium",
        "created_at": _now(),
        "tolerance": {"pct": tol.get("amount_tolerance_pct"), "abs": tol.get("amount_tolerance_abs")},
    }


@router.get("/tolerances")
async def get_tolerances(current=Depends(get_current_user)):
    tol = await _get_tolerances()
    return {"tolerances": tol, "as_of": _now()}


@router.post("/tolerances")
async def set_tolerances(body: Dict[str, Any], current=Depends(get_current_user)):
    doc = {
        "id": "singleton",
        "amount_tolerance_pct": float(body.get("amount_tolerance_pct") or 5.0),
        "amount_tolerance_abs": float(body.get("amount_tolerance_abs") or 500.0),
        "updated_at": _now(),
        "updated_by": current.get("email"),
    }
    await db.three_way_match_tolerances.update_one({"id": "singleton"}, {"$set": doc}, upsert=True)
    await audit_log(current["email"], "three_way_match_tolerances_update", "three_way_match_tolerances", "singleton", doc)
    return {"status": "ok", "as_of": _now(), "tolerances": doc}


@router.post("/run")
async def run_three_way_match(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    tol = await _get_tolerances()
    inv_q: Dict[str, Any] = {"po_id": {"$ne": None}}
    if entity_code:
        inv_q["entity"] = entity_code
    invs = [i async for i in db.invoices.find(inv_q, {"_id": 0}).limit(800)]

    exceptions = []
    for inv in invs:
        ex = await _build_exception(inv, tol)
        if ex:
            exceptions.append(ex)

    # Persist exceptions (idempotent upsert)
    for ex in exceptions:
        await db.three_way_match_exceptions.update_one({"id": ex["id"]}, {"$set": ex}, upsert=True)

    run_id = f"twmr-{__import__('uuid').uuid4().hex[:10]}"
    await db.three_way_match_runs.insert_one(
        {
            "id": run_id,
            "entity": entity_code,
            "status": "success",
            "started_at": _now(),
            "ended_at": _now(),
            "exceptions": len(exceptions),
            "tolerances": tol,
        }
    )
    await audit_log(current["email"], "three_way_match_run", "three_way_match_run", run_id, {"entity": entity_code, "exceptions": len(exceptions)})
    return {"status": "ok", "run_id": run_id, "exceptions": len(exceptions), "as_of": _now()}


@router.get("/summary")
async def three_way_match_summary(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    total = await db.three_way_match_exceptions.count_documents(q)
    cur = db.three_way_match_exceptions.find(q, {"_id": 0}).sort("created_at", -1).limit(20)
    latest = [x async for x in cur]
    return {"as_of": _now(), "entity_code": entity_code, "open_exceptions": total, "latest": latest, "source": "three_way_match_exceptions"}


@router.get("/exceptions")
async def three_way_match_exceptions(entity_code: Optional[str] = Query(None), limit: int = Query(100, ge=1, le=1000), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    cur = db.three_way_match_exceptions.find(q, {"_id": 0}).sort("created_at", -1).limit(limit)
    items = [x async for x in cur]
    return {"items": items, "count": len(items), "as_of": _now()}


@router.get("/{exception_id}")
async def three_way_match_detail(exception_id: str, current=Depends(get_current_user)):
    ex = await db.three_way_match_exceptions.find_one({"id": exception_id}, {"_id": 0})
    if not ex:
        raise HTTPException(404, "Three-way match exception not found")
    if ex.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=ex.get("entity"))
    inv = await db.invoices.find_one({"id": ex.get("invoice_id")}, {"_id": 0})
    po = await db.purchase_orders.find_one({"id": ex.get("po_id")}, {"_id": 0})
    grn = await db.goods_receipts.find_one({"id": ex.get("grn_id")}, {"_id": 0})
    return {"exception": ex, "invoice": inv, "purchase_order": po, "goods_receipt": grn, "as_of": _now()}


@router.post("/{exception_id}/create-case")
async def three_way_match_create_case(exception_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    ex = await db.three_way_match_exceptions.find_one({"id": exception_id}, {"_id": 0})
    if not ex:
        raise HTTPException(404, "Three-way match exception not found")
    if ex.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=ex.get("entity"))

    now = _now()
    cid = f"case-twm-{__import__('uuid').uuid4().hex[:10]}"
    link_ex_id = f"twm-{exception_id}"

    ex_doc = {
        "id": link_ex_id,
        "control_id": "C-AP-003",
        "control_code": "C-AP-003",
        "control_name": "3-Way Match Exception",
        "process": "Procure-to-Pay",
        "entity": ex.get("entity") or current.get("entity") or "US-HQ",
        "severity": ex.get("severity") or "high",
        "status": "open",
        "materiality_score": float(body.get("materiality_score") or 0.5),
        "anomaly_score": float(body.get("anomaly_score") or 0.5),
        "financial_exposure": float(body.get("financial_exposure") or abs(float(ex.get("variance_inv_po") or 0.0))),
        "source_record_type": "three_way_match_exception",
        "source_record_id": exception_id,
        "detected_at": now,
        "title": body.get("title") or "3-way match variance follow-up",
        "summary": body.get("summary") or f"Case created for three-way match exception {exception_id}.",
        "recurrence_count": 0,
        "department_id": None,
        "cost_center_id": None,
    }
    await db.exceptions.update_one({"id": link_ex_id}, {"$setOnInsert": ex_doc}, upsert=True)

    case_doc = {
        "id": cid,
        "exception_id": link_ex_id,
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
    await audit_log(current["email"], "three_way_match_create_case", "case", cid, {"exception_id": exception_id})
    return {"status": "ok", "case_id": cid, "exception_id": link_ex_id, "as_of": _now()}

