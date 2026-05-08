"""Phase 33 — Master Data Quality Command Center (SRS-aligned endpoints).

This router is a thin facade over Phase 2 `master_dq_service` and seeded masters.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.deps import audit_log, db
from app.services import master_dq_service as mdq
from app.services.kpi_service import as_of_now


router = APIRouter(prefix="/master-data-quality", tags=["master-data-quality"])


async def _ensure_findings() -> Dict[str, Any]:
    """Ensure DQ findings exist (seed-friendly)."""
    if await db.master_data_quality_findings.count_documents({}) > 0:
        return {"status": "already_present"}
    return await mdq.recompute_findings(db, limit_per_type=50_000)


@router.get("/summary")
async def mdq_summary(current=Depends(get_current_user)):
    await _ensure_findings()
    return await mdq.summary(db)


@router.get("/vendors")
async def mdq_vendors(entity_code: Optional[str] = Query(None), limit: int = Query(200, ge=1, le=1000), offset: int = Query(0, ge=0), current=Depends(get_current_user)):
    await _ensure_findings()
    q: Dict[str, Any] = {"master_type": "vendor", "status": "open"}
    if entity_code:
        q["entity_code"] = entity_code
    cur = db.master_data_quality_findings.find(q, {"_id": 0}).sort("severity", 1).skip(offset).limit(limit)
    items = [x async for x in cur]
    total = await db.master_data_quality_findings.count_documents(q)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": as_of_now()}


@router.get("/customers")
async def mdq_customers(entity_code: Optional[str] = Query(None), limit: int = Query(200, ge=1, le=1000), offset: int = Query(0, ge=0), current=Depends(get_current_user)):
    await _ensure_findings()
    q: Dict[str, Any] = {"master_type": "customer", "status": "open"}
    if entity_code:
        q["entity_code"] = entity_code
    cur = db.master_data_quality_findings.find(q, {"_id": 0}).sort("severity", 1).skip(offset).limit(limit)
    items = [x async for x in cur]
    total = await db.master_data_quality_findings.count_documents(q)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": as_of_now()}


@router.get("/employees")
async def mdq_employees(entity_code: Optional[str] = Query(None), limit: int = Query(200, ge=1, le=1000), offset: int = Query(0, ge=0), current=Depends(get_current_user)):
    await _ensure_findings()
    q: Dict[str, Any] = {"master_type": "employee", "status": "open"}
    if entity_code:
        q["entity_code"] = entity_code
    cur = db.master_data_quality_findings.find(q, {"_id": 0}).sort("severity", 1).skip(offset).limit(limit)
    items = [x async for x in cur]
    total = await db.master_data_quality_findings.count_documents(q)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": as_of_now()}


@router.get("/gl")
async def mdq_gl(entity_code: Optional[str] = Query(None), limit: int = Query(200, ge=1, le=1000), offset: int = Query(0, ge=0), current=Depends(get_current_user)):
    await _ensure_findings()
    q: Dict[str, Any] = {"master_type": "gl_account", "status": "open"}
    if entity_code:
        q["entity_code"] = entity_code
    cur = db.master_data_quality_findings.find(q, {"_id": 0}).sort("severity", 1).skip(offset).limit(limit)
    items = [x async for x in cur]
    total = await db.master_data_quality_findings.count_documents(q)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": as_of_now()}


@router.get("/duplicates")
async def mdq_duplicates(entity_code: Optional[str] = Query(None), limit: int = Query(200, ge=1, le=1000), current=Depends(get_current_user)):
    await _ensure_findings()
    # Duplicates are represented by rule_id prefixes.
    q: Dict[str, Any] = {"status": "open", "rule_id": {"$regex": "DUPLICATE"}}
    if entity_code:
        q["entity_code"] = entity_code
    cur = db.master_data_quality_findings.find(q, {"_id": 0}).sort("severity", 1).limit(limit)
    items = [x async for x in cur]
    return {"items": items, "count": len(items), "as_of": as_of_now()}


@router.get("/change-audit")
async def mdq_change_audit(entity_code: Optional[str] = Query(None), limit: int = Query(200, ge=1, le=2000), current=Depends(get_current_user)):
    # Prefer real audit logs; if missing, synthesize a small stable set.
    q: Dict[str, Any] = {"action": {"$regex": "master|vendor|customer|employee|gl|bank", "$options": "i"}}
    if entity_code:
        q["details.entity"] = entity_code
    cur = db.audit_logs.find(q, {"_id": 0}).sort("at", -1).limit(limit)
    items = [x async for x in cur]
    if not items:
        now = datetime.now(timezone.utc)
        items = [
            {"id": "mdq-audit-1", "at": now.isoformat(), "action": "master_vendor_update", "actor": "controller@onetouch.ai", "subject_type": "vendor", "subject_id": "V-1001", "details": {"field": "gstin", "entity": entity_code or "US-HQ"}},
            {"id": "mdq-audit-2", "at": (now.replace(hour=max(now.hour - 2, 0))).isoformat(), "action": "master_employee_update", "actor": "hr@onetouch.ai", "subject_type": "employee", "subject_id": "E-2002", "details": {"field": "department", "entity": entity_code or "US-HQ"}},
        ]
    return {"items": items, "count": len(items), "as_of": as_of_now(), "note": "If audit_logs are empty for masters, response is synthesized."}


@router.post("/{finding_id}/create-case")
async def mdq_create_case(finding_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    await _ensure_findings()
    f = await db.master_data_quality_findings.find_one({"id": finding_id}, {"_id": 0})
    if not f:
        raise HTTPException(404, "Finding not found")

    now = as_of_now()
    cid = f"case-mdq-{__import__('uuid').uuid4().hex[:10]}"
    ex_id = f"mdq-{finding_id}"

    master_type = str(f.get("master_type") or "master")
    obj_id = str(f.get("object_id") or "")
    entity = f.get("entity_code") or body.get("entity") or current.get("entity") or "US-HQ"
    sev = str(body.get("severity") or f.get("severity") or "warning")
    exposure = float(body.get("financial_exposure") or 0.0)

    title = body.get("title") or f"Master DQ: {master_type} {obj_id} — {f.get('rule_id')}"
    summary = body.get("summary") or str(f.get("message") or "Master data quality issue")

    ex_doc = {
        "id": ex_id,
        "control_id": "C-MDQ-001",
        "control_code": "MDQ-001",
        "control_name": "Master data quality exception",
        "process": "Master Data",
        "entity": entity,
        "severity": sev,
        "status": "open",
        "materiality_score": float(body.get("materiality_score") or 0.4),
        "anomaly_score": float(body.get("anomaly_score") or 0.4),
        "financial_exposure": exposure,
        "source_record_type": "master_dq_finding",
        "source_record_id": finding_id,
        "detected_at": now,
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
        "control_code": ex_doc["control_code"],
        "control_name": ex_doc["control_name"],
        "title": title,
        "summary": summary,
        "severity": sev,
        "status": "open",
        "priority": body.get("priority") or ("P1" if sev == "critical" else "P2"),
        "owner_email": body.get("owner_email") or current.get("email"),
        "owner_name": None,
        "due_date": body.get("due_date") or now,
        "financial_exposure": exposure,
        "entity": entity,
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
    await audit_log(current["email"], "master_dq_create_case", "case", cid, {"finding_id": finding_id, "master_type": master_type, "object_id": obj_id})
    return {"status": "ok", "case_id": cid, "exception_id": ex_id, "as_of": as_of_now()}

