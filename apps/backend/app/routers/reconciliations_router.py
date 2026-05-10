"""Phase 17 — Reconciliation Management Suite (seed-backed workflow)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.deps import audit_log, db
from app.services.kpi_service import as_of_now
from app.services.rbac_service import enforce_entity_scope


router = APIRouter(prefix="/reconciliations", tags=["reconciliations"])


def _now() -> str:
    return as_of_now()


@router.get("")
async def recon_list(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current=Depends(get_current_user),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    if period_ym:
        q["period"] = period_ym
    if status:
        q["status"] = status
    cur = db.reconciliations.find(q, {"_id": 0}).sort("due_date", -1).skip(offset).limit(limit)
    items = [r async for r in cur]
    total = await db.reconciliations.count_documents(q)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": _now()}


@router.post("")
async def recon_create(body: Dict[str, Any], current=Depends(get_current_user)):
    be = body.get("entity") or body.get("entity_code")
    if be and str(be).strip():
        await enforce_entity_scope(db, current=current, requested_entity_code=str(be))
    rid = f"rec-{__import__('uuid').uuid4().hex[:10]}"
    doc = {
        **body,
        "id": rid,
        "status": body.get("status") or "open",
        "created_at": _now(),
        "created_by": current.get("email"),
        "evidence": [],
        "logs": [{"at": _now(), "by": current.get("email"), "action": "create"}],
    }
    await db.reconciliations.insert_one(dict(doc))
    await audit_log(current["email"], "reconciliation_create", "reconciliation", rid, {"entity": body.get("entity"), "type": body.get("reconciliation_type")})
    return {"status": "ok", "reconciliation_id": rid, "as_of": _now()}


@router.get("/{reconciliation_id}")
async def recon_get(reconciliation_id: str, current=Depends(get_current_user)):
    r = await db.reconciliations.find_one({"id": reconciliation_id}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Reconciliation not found")
    if r.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=r.get("entity"))
    return {"reconciliation": r, "as_of": _now()}


@router.patch("/{reconciliation_id}")
async def recon_patch(reconciliation_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    r0 = await db.reconciliations.find_one({"id": reconciliation_id}, {"_id": 0, "entity": 1})
    if not r0:
        raise HTTPException(404, "Reconciliation not found")
    if r0.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=r0.get("entity"))
    await db.reconciliations.update_one({"id": reconciliation_id}, {"$set": {**body, "updated_at": _now()}})
    await audit_log(current["email"], "reconciliation_update", "reconciliation", reconciliation_id, {"fields": list(body.keys())})
    return {"status": "ok", "as_of": _now()}


@router.post("/{reconciliation_id}/items")
async def recon_add_items(reconciliation_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    r0 = await db.reconciliations.find_one({"id": reconciliation_id}, {"_id": 0, "entity": 1})
    if not r0:
        raise HTTPException(404, "Reconciliation not found")
    if r0.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=r0.get("entity"))
    items = body.get("items") or []
    await db.reconciliations.update_one({"id": reconciliation_id}, {"$push": {"items": {"$each": items}}, "$set": {"updated_at": _now()}})
    await audit_log(current["email"], "reconciliation_add_items", "reconciliation", reconciliation_id, {"count": len(items)})
    return {"status": "ok", "added": len(items), "as_of": _now()}


@router.post("/{reconciliation_id}/evidence")
async def recon_add_evidence(reconciliation_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    r0 = await db.reconciliations.find_one({"id": reconciliation_id}, {"_id": 0, "entity": 1})
    if not r0:
        raise HTTPException(404, "Reconciliation not found")
    if r0.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=r0.get("entity"))
    ev_id = f"ev-{__import__('uuid').uuid4().hex[:8]}"
    ev = {"id": ev_id, "type": body.get("type") or "link", "url": body.get("url"), "notes": body.get("notes"), "by": current.get("email"), "at": _now()}
    await db.reconciliations.update_one({"id": reconciliation_id}, {"$push": {"evidence": ev}, "$set": {"updated_at": _now()}})
    await audit_log(current["email"], "reconciliation_add_evidence", "reconciliation", reconciliation_id, {"evidence_id": ev_id})
    return {"status": "ok", "evidence_id": ev_id, "as_of": _now()}


@router.post("/{reconciliation_id}/submit")
async def recon_submit(reconciliation_id: str, current=Depends(get_current_user)):
    r0 = await db.reconciliations.find_one({"id": reconciliation_id}, {"_id": 0, "entity": 1})
    if not r0:
        raise HTTPException(404, "Reconciliation not found")
    if r0.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=r0.get("entity"))
    await db.reconciliations.update_one(
        {"id": reconciliation_id},
        {"$set": {"status": "submitted", "submitted_at": _now(), "submitted_by": current.get("email")}, "$push": {"logs": {"at": _now(), "by": current.get("email"), "action": "submit"}}},
    )
    await audit_log(current["email"], "reconciliation_submit", "reconciliation", reconciliation_id, {})
    return {"status": "ok", "as_of": _now()}


@router.post("/{reconciliation_id}/approve")
async def recon_approve(reconciliation_id: str, current=Depends(get_current_user)):
    r0 = await db.reconciliations.find_one({"id": reconciliation_id}, {"_id": 0, "entity": 1, "status": 1})
    if not r0:
        raise HTTPException(404, "Reconciliation not found")
    if r0.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=r0.get("entity"))
    if r0.get("status") != "submitted":
        raise HTTPException(409, "Reconciliation must be submitted before it can be approved")
    await db.reconciliations.update_one(
        {"id": reconciliation_id},
        {"$set": {"status": "approved", "approved_at": _now(), "approved_by": current.get("email")}, "$push": {"logs": {"at": _now(), "by": current.get("email"), "action": "approve"}}},
    )
    await audit_log(current["email"], "reconciliation_approve", "reconciliation", reconciliation_id, {})
    return {"status": "ok", "as_of": _now()}


@router.post("/{reconciliation_id}/reopen")
async def recon_reopen(reconciliation_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    r0 = await db.reconciliations.find_one({"id": reconciliation_id}, {"_id": 0, "entity": 1})
    if not r0:
        raise HTTPException(404, "Reconciliation not found")
    if r0.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=r0.get("entity"))
    reason = body.get("reason")
    await db.reconciliations.update_one(
        {"id": reconciliation_id},
        {"$set": {"status": "open", "reopened_at": _now(), "reopened_by": current.get("email"), "reopen_reason": reason}, "$push": {"logs": {"at": _now(), "by": current.get("email"), "action": "reopen", "reason": reason}}},
    )
    await audit_log(current["email"], "reconciliation_reopen", "reconciliation", reconciliation_id, {"reason": reason})
    return {"status": "ok", "as_of": _now()}


@router.post("/{reconciliation_id}/create-case")
async def recon_create_case(reconciliation_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    cid = f"case-rec-{__import__('uuid').uuid4().hex[:10]}"
    # Create a fully-shaped CaseOut-compatible document to avoid downstream 500s
    # when `/cases` serializes existing Mongo docs.
    now = _now()
    rec = await db.reconciliations.find_one({"id": reconciliation_id}, {"_id": 0}) or {}
    entity = body.get("entity") or rec.get("entity") or current.get("entity") or "US-HQ"
    entity = await enforce_entity_scope(db, current=current, requested_entity_code=str(entity))
    process = "Record-to-Report"
    exposure = float(rec.get("variance_amount") or body.get("financial_exposure") or 0.0)
    due_date = body.get("due_date") or rec.get("due_date") or now

    ex_id = f"rec-{reconciliation_id}"
    # Ensure linked ExceptionOut exists for case detail paths that join exceptions.
    ex_doc = {
        "id": ex_id,
        "control_id": "C-REC-001",
        "control_code": "REC-001",
        "control_name": "Reconciliation Variance Follow-up",
        "process": process,
        "entity": entity,
        "severity": body.get("severity") or "medium",
        "status": "open",
        "materiality_score": float(body.get("materiality_score") or 0.3),
        "anomaly_score": float(body.get("anomaly_score") or 0.3),
        "financial_exposure": float(body.get("financial_exposure") or exposure),
        "source_record_type": "reconciliation",
        "source_record_id": reconciliation_id,
        "detected_at": now,
        "title": body.get("title") or "Reconciliation variance detected",
        "summary": body.get("summary") or f"Variance follow-up for reconciliation {reconciliation_id}.",
        "recurrence_count": 0,
        "engagement_id": rec.get("engagement_id"),
        "material_impact": body.get("material_impact"),
        "department_id": rec.get("department_id"),
        "cost_center_id": rec.get("cost_center_id"),
    }
    await db.exceptions.update_one({"id": ex_id}, {"$setOnInsert": ex_doc}, upsert=True)

    payload = {
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
        "due_date": due_date,
        "financial_exposure": exposure,
        "entity": entity,
        "process": process,
        "detected_at": now,
        "opened_at": now,
        "closed_at": None,
        "root_cause_category": None,
        "engagement_id": rec.get("engagement_id"),
        "material_impact": ex_doc.get("material_impact"),
        "material_watch": None,
        "department_id": ex_doc.get("department_id"),
        "cost_center_id": ex_doc.get("cost_center_id"),
    }
    await db.cases.insert_one(dict(payload))
    await audit_log(current["email"], "reconciliation_create_case", "case", cid, {"reconciliation_id": reconciliation_id})
    return {"status": "ok", "case_id": cid, "as_of": _now()}

