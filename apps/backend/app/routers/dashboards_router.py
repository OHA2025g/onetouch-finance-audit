"""Persona dashboards + audit readiness."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.deps import db
from app.analytics import (cfo_cockpit, controller_dashboard, compliance_dashboard,
                           audit_workspace, compute_readiness, working_capital_dashboard, treasury_dashboard, fpa_dashboard,
                           cash_conversion_dashboard)
from app.services import master_data_service as mds
from app.services.rbac_service import enforce_entity_scope
from app.utils.timeutil import iso_utc

router = APIRouter(tags=["dashboards"])


@router.get("/dashboard/cfo")
async def dashboard_cfo(
    entity_code: Optional[str] = Query(None, description="Legal entity code (Phase 4 scope)"),
    period_ym: Optional[str] = Query(None, description="YYYY-MM — filter exceptions by detected_at prefix and cases by opened_at"),
    department_id: Optional[str] = Query(None, description="Optional department id on exceptions"),
    cost_center_id: Optional[str] = Query(None, description="Optional cost center id on exceptions"),
    process: Optional[str] = Query(None, description="Finance process filter (server-side)"),
    current=Depends(get_current_user),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await cfo_cockpit(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
    )


@router.get("/dashboard/risk-intelligence")
async def dashboard_risk_intelligence(
    entity_code: Optional[str] = Query(None, description="Same scope as /dashboard/cfo (Phase 4)"),
    period_ym: Optional[str] = Query(None, description="YYYY-MM — same as CFO cockpit"),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    risk_scores_limit: int = Query(200, ge=1, le=2000, description="Phase 38 — cap finance_risk_scores rows"),
    current=Depends(get_current_user),
):
    """Phase 38 — One round-trip for Risk intelligence hub: CFO cockpit payload plus master risk scores.
    Phase 40 — Same allowlist as other dashboards (incl. External Auditor) for nav parity with /insights/risk."""
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    cockpit = await cfo_cockpit(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    items = await mds.list_risk_scores(db, entity_code, risk_scores_limit)
    now = datetime.now(timezone.utc)
    risk_scores = {"items": items, "count": len(items), "as_of": iso_utc(now)}
    return {**cockpit, "risk_scores": risk_scores}


@router.get("/dashboard/controller")
async def dashboard_controller(
    entity_code: Optional[str] = Query(None, description="Legal entity code (Phase 4 scope)"),
    period_ym: Optional[str] = Query(None, description="YYYY-MM — filter reconciliations by period and exceptions by detected_at"),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await controller_dashboard(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )


@router.get("/reconciliations/{reconciliation_id}")
async def reconciliation_detail(reconciliation_id: str, current=Depends(get_current_user)):
    """Single reconciliation with optional related journal (same entity) for drill-through."""
    r = await db.reconciliations.find_one({"id": reconciliation_id}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Reconciliation not found")
    ent = r.get("entity")
    related_journal = None
    if ent:
        cur = db.journals.find({"entity": ent}, {"_id": 0}).sort("posting_date", -1).limit(1)
        batch = await cur.to_list(length=1)
        related_journal = batch[0] if batch else None
    return {"reconciliation": r, "related_journal": related_journal}


@router.get("/dashboard/audit")
async def dashboard_audit(
    entity_code: Optional[str] = Query(None, description="Phase 7 — filters recent_runs to test_runs.entities; echoed in filters_applied"),
    period_ym: Optional[str] = Query(None, description="YYYY-MM — scope recent test runs by run_ts prefix"),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    trend_days: int = Query(30, ge=7, le=90, description="Days of exception/run trend series"),
    current=Depends(get_current_user),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await audit_workspace(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        trend_days=trend_days,
    )


@router.get("/dashboard/audit/trends")
async def dashboard_audit_trends(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    days: int = Query(30, ge=7, le=90),
    current=Depends(get_current_user),
):
    """Optional lightweight trends refresh (same payload as ``trends`` on main audit dashboard)."""
    from app.services.audit_workspace_service import build_audit_workspace_trends

    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await build_audit_workspace_trends(
        db,
        days=days,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )


@router.get("/dashboard/compliance")
async def dashboard_compliance(
    entity_code: Optional[str] = Query(None, description="Phase 5 — scope compliance views to entity"),
    period_ym: Optional[str] = Query(None, description="YYYY-MM — exception detected_at prefix"),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await compliance_dashboard(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )


@router.get("/dashboard/working-capital")
async def dashboard_working_capital(
    entity_code: Optional[str] = Query(None, description="Slice 5 — scope AR/AP by entity"),
    period_ym: Optional[str] = Query(None, description="YYYY-MM — scope AR/AP by invoice_date prefix"),
    department_id: Optional[str] = Query(None, description="Applied to exception-derived metrics only (for now)"),
    cost_center_id: Optional[str] = Query(None, description="Applied to exception-derived metrics only (for now)"),
    current=Depends(get_current_user),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await working_capital_dashboard(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )


@router.get("/dashboard/treasury")
async def dashboard_treasury(
    entity_code: Optional[str] = Query(None, description="Slice 6 — scope bank activity by entity"),
    period_ym: Optional[str] = Query(None, description="YYYY-MM — scope bank transactions by txn_ts prefix"),
    department_id: Optional[str] = Query(None, description="Applied to exception-derived metrics only (for now)"),
    cost_center_id: Optional[str] = Query(None, description="Applied to exception-derived metrics only (for now)"),
    current=Depends(get_current_user),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await treasury_dashboard(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )


@router.get("/dashboard/fpa")
async def dashboard_fpa(
    entity_code: Optional[str] = Query(None, description="Slice 7 — scope portfolio by entity"),
    period_ym: Optional[str] = Query(None, description="YYYY-MM — scopes journal spend proxy by posting_date prefix"),
    department_id: Optional[str] = Query(None, description="Applied to exception-derived metrics only (for now)"),
    cost_center_id: Optional[str] = Query(None, description="Applied to exception-derived metrics only (for now)"),
    current=Depends(get_current_user),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await fpa_dashboard(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )


@router.get("/dashboard/cash-conversion")
async def dashboard_cash_conversion(
    entity_code: Optional[str] = Query(None, description="Slice 8 — scope AR/AP by entity"),
    period_ym: Optional[str] = Query(None, description="YYYY-MM — scopes exception-derived metrics"),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    return await cash_conversion_dashboard(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )


@router.get("/dashboard/my-cases")
async def dashboard_my_cases(
    entity_code: Optional[str] = Query(None, description="Phase 5 — filter assigned cases by entity"),
    period_ym: Optional[str] = Query(None, description="YYYY-MM — case opened_at prefix"),
    department_id: Optional[str] = Query(None, description="Phase 9 — filter by denormalized department_id / dept_id"),
    cost_center_id: Optional[str] = Query(None, description="Phase 9 — filter by denormalized cost_center_id / cc_id"),
    current=Depends(get_current_user),
):
    from app.services.case_service import hydrate_case_rows_financial_exposure, merge_cases_master_filters

    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    q = merge_cases_master_filters(
        {"owner_email": current["email"]},
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    cases = [dict(c) async for c in db.cases.find(q, {"_id": 0}).sort("due_date", 1)]
    await hydrate_case_rows_financial_exposure(db, cases)
    open_count = sum(1 for c in cases if c["status"] != "closed")
    overdue = 0
    now = datetime.now(timezone.utc)
    for c in cases:
        try:
            if c["status"] != "closed" and datetime.fromisoformat(c["due_date"]) < now:
                overdue += 1
        except Exception:
            pass
    filters_applied = {k: v for k, v in {
        "entity_code": entity_code,
        "period_ym": period_ym,
        "department_id": department_id,
        "cost_center_id": cost_center_id,
    }.items() if v}
    return {
        "kpis": {"my_open_cases": open_count, "overdue": overdue, "total_assigned": len(cases)},
        "cases": cases,
        "filters_applied": filters_applied,
    }


@router.get("/readiness")
async def readiness(
    entity_code: Optional[str] = Query(None, description="Phase 12 — scope readiness matrix (cells + filters_applied)"),
    period_ym: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    cost_center_id: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    rows = await compute_readiness(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    filters_applied = {k: v for k, v in {
        "entity_code": entity_code,
        "period_ym": period_ym,
        "department_id": department_id,
        "cost_center_id": cost_center_id,
    }.items() if v}
    return {"rows": rows, "filters_applied": filters_applied}
