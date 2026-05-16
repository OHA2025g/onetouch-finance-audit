"""Control library + execution + exceptions list."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.deps import db, audit_log
from app.services.rbac_service import enforce_entity_scope
from app.models import ControlOut, ExceptionOut
from app.controls_engine import normalize_exception_for_api, run_control, run_all_controls
from app.analytics import _scope_exceptions

router = APIRouter(tags=["controls"])


def _exceptions_list_query(
    *,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    process: Optional[str] = None,
    entity: Optional[str] = None,
    entity_code: Optional[str] = None,
    control_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
) -> Dict[str, Any]:
    base: Dict[str, Any] = {}
    if severity:
        base["severity"] = severity
    if status:
        base["status"] = status
    if process:
        base["process"] = process
    ent = entity or entity_code
    if ent:
        base["entity"] = ent
    if control_code:
        base["control_code"] = control_code
    ex_q = _scope_exceptions(
        base if base else None,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    return ex_q if ex_q else {}


@router.get("/controls", response_model=List[ControlOut])
async def controls_list(
    process: Optional[str] = None,
    criticality: Optional[str] = None,
    entity_code: Optional[str] = Query(None, description="Optional legal-entity scope (Phase 40 RBAC)"),
    current=Depends(get_current_user),
):
    await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    q: Dict[str, Any] = {}
    if process:
        q["process"] = process
    if criticality:
        q["criticality"] = criticality
    return [c async for c in db.controls.find(q, {"_id": 0}).sort("code", 1)]


@router.get("/controls/{control_id}")
async def control_detail(
    control_id: str,
    entity_code: Optional[str] = Query(None, description="Phase 6 — scope open exceptions"),
    period_ym: Optional[str] = Query(None, description="YYYY-MM — detected_at prefix"),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    c = await db.controls.find_one({"id": control_id}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Control not found")
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    runs = [r async for r in db.test_runs.find({"control_id": control_id}, {"_id": 0}).sort("run_ts", -1).limit(20)]
    ex_q = _scope_exceptions(
        {"control_id": control_id, "status": {"$ne": "closed"}},
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    open_ex = [e async for e in db.exceptions.find(ex_q, {"_id": 0}).sort("financial_exposure", -1).limit(50)]
    filters_applied = {k: v for k, v in {
        "entity_code": entity_code,
        "period_ym": period_ym,
        "department_id": department_id,
        "cost_center_id": cost_center_id,
    }.items() if v}
    return {"control": c, "recent_runs": runs, "open_exceptions": open_ex, "filters_applied": filters_applied}


@router.post("/controls/{control_id}/run")
async def control_run(control_id: str, current=Depends(get_current_user)):
    if current["role"] == "External Auditor":
        raise HTTPException(403, "Read-only auditor role cannot execute controls")
    c = await db.controls.find_one({"id": control_id}, {"_id": 0})
    if not c:
        raise HTTPException(404, "Control not found")
    result = await run_control(db, c)
    await audit_log(current["email"], "run_control", "control", control_id, {"result": result})
    return result


@router.post("/controls/run-all")
async def controls_run_all(current=Depends(get_current_user)):
    if current["role"] == "External Auditor":
        raise HTTPException(403, "Read-only auditor role cannot execute controls")
    result = await run_all_controls(db)
    from app.services.cfo_command_center_service import clear_all_cache

    clear_all_cache()
    await audit_log(current["email"], "run_all_controls", "controls", "all",
                    {"total_exceptions": result["total_exceptions"]})
    return result


@router.get("/exceptions", response_model=List[ExceptionOut])
async def exceptions_list(
    severity: Optional[str] = None,
    status: Optional[str] = None,
    process: Optional[str] = None,
    entity: Optional[str] = None,
    entity_code: Optional[str] = None,
    control_code: Optional[str] = None,
    period_ym: Optional[str] = Query(None, description="Phase 5 — detected_at YYYY-MM prefix"),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    offset: int = Query(0, ge=0, le=50_000, description="Phase 6 — pagination offset"),
    limit: int = Query(200, ge=1, le=1000),
    current=Depends(get_current_user),
):
    ent_resolved = await enforce_entity_scope(db, current=current, requested_entity_code=(entity or entity_code))
    ex_q = _exceptions_list_query(
        severity=severity,
        status=status,
        process=process,
        entity=ent_resolved,
        entity_code=ent_resolved,
        control_code=control_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    cur = db.exceptions.find(ex_q, {"_id": 0}).sort(
        [("financial_exposure", -1), ("id", 1)]
    ).skip(offset).limit(limit)
    out: List[Dict[str, Any]] = []
    async for e in cur:
        out.append(normalize_exception_for_api(dict(e)))
    return out


@router.get("/exceptions/count")
async def exceptions_count(
    severity: Optional[str] = None,
    status: Optional[str] = None,
    process: Optional[str] = None,
    entity: Optional[str] = None,
    entity_code: Optional[str] = None,
    control_code: Optional[str] = None,
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    """Same filters as ``GET /exceptions``; returns total row count for pagination UIs (Phase 6)."""
    ent_resolved = await enforce_entity_scope(db, current=current, requested_entity_code=(entity or entity_code))
    ex_q = _exceptions_list_query(
        severity=severity,
        status=status,
        process=process,
        entity=ent_resolved,
        entity_code=ent_resolved,
        control_code=control_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    n = await db.exceptions.count_documents(ex_q)
    return {"count": n}


@router.get("/exceptions/{exception_id}")
async def exception_detail(exception_id: str, current=Depends(get_current_user)):
    e = await db.exceptions.find_one({"id": exception_id}, {"_id": 0})
    if not e:
        raise HTTPException(404, "Exception not found")
    if e.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=e.get("entity"))
    case = await db.cases.find_one({"exception_id": exception_id}, {"_id": 0})
    return {"exception": normalize_exception_for_api(e), "case": case}
