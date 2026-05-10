"""CA audit modules: materiality, RACM, FS engine, schedules, IFC, working papers, India compliance, reporting, aggregates."""
from __future__ import annotations

import io
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from starlette.requests import Request

from app.auth import get_current_user
from app.deps import audit_log, db, iso
from app.services.rbac_service import (
    assert_engagement_entity_scope,
    assert_super_admin_when_entity_scope_enforced,
    enforce_entity_scope,
)
from app.schemas import ca_audit as sch
from app.services import case_service as csvc
from app.services.ca_compliance_templates import compliance_rows_for_laws
from app.services import ca_fs_mapping as fs_map
from app.services import ca_schedule_audit as ca_sched
from app.services import ca_ifc_service as ifc_svc
from app.services import ca_wp_service as wp_svc
from app.services.ca_fs_validation import (
    analyze_trial_balance_line,
    build_fs_validation_summary,
    opening_closing_snapshot_issues,
    prior_period_movement_issues,
    validate_trial_balance_upload,
)
from app.services import racm_service as racm_svc
from app.services import ca_india_compliance_engine as ind_ce
from app.services import ca_report_opinion_engine as rpt_eng
from app.services import ca_executive_advisory as exec_adv
from app.services import ca_engagement_integration as eng_int
from app.services.ca_audit_domain import (
    compute_benchmark_options,
    continuous_assurance_scores,
    default_wp_folders,
    derive_performance_and_trivial,
    enrich_materiality_record,
    risk_scores,
    select_default_benchmark,
)

router = APIRouter(tags=["ca-audit"])


def _now() -> str:
    return iso(datetime.now(timezone.utc))


async def _engagement_or_404(
    engagement_id: str,
    *,
    current: dict,
    request: Optional[Request] = None,
) -> Dict[str, Any]:
    entity_code: Optional[str] = None
    if request is not None:
        qv = request.query_params.get("entity_code")
        entity_code = str(qv).strip() if qv else None
        entity_code = entity_code or None
    await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    doc = await db.audit_engagements.find_one({"engagement_id": engagement_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Engagement not found")
    await assert_engagement_entity_scope(db, current=current, engagement=doc)
    return doc


async def _assert_engagement_scope_for_doc(
    doc: Optional[Dict[str, Any]],
    *,
    current: dict,
    not_found_detail: str = "Resource not found",
    request: Optional[Request] = None,
) -> str:
    """For CA child rows addressed only by id, resolve ``engagement_id`` and apply the same RBAC as engagement routes."""
    if not doc:
        raise HTTPException(404, not_found_detail)
    eid = doc.get("engagement_id")
    if not eid:
        raise HTTPException(404, not_found_detail)
    eid_s = str(eid).strip()
    if not eid_s:
        raise HTTPException(404, not_found_detail)
    await _engagement_or_404(eid_s, current=current, request=request)
    return eid_s


async def _compute_continuous_assurance(engagement_id: str, eng: Dict[str, Any]) -> Dict[str, Any]:
    risks = [r async for r in db.ca_risks.find({"engagement_id": engagement_id}, {"_id": 0})]
    mat = await db.ca_materiality.find_one({"engagement_id": engagement_id}, {"_id": 0})
    exceptions = [e async for e in db.exceptions.find({"engagement_id": engagement_id}, {"_id": 0}).limit(500)]
    open_cases = await db.cases.count_documents({"engagement_id": engagement_id, "status": {"$ne": "closed"}})
    comp = await db.ca_compliance_results.find_one({"engagement_id": engagement_id}, {"_id": 0})
    reqs = comp.get("requirements") if comp else []
    compliant = sum(1 for r in reqs if r.get("status") == "compliant")
    compliance_pct = (compliant / len(reqs) * 100.0) if reqs else 85.0
    wp_total = await db.ca_working_papers.count_documents({"engagement_id": engagement_id})
    wp_signed_pct = min(100.0, 35.0 + min(65.0, float(wp_total) * 4.0))
    return continuous_assurance_scores(eng, risks, mat, exceptions, open_cases, compliance_pct, wp_signed_pct)


# ----- Materiality -----
async def _exceptions_for_engagement(engagement_id: str) -> List[Dict[str, Any]]:
    return [e async for e in db.exceptions.find({"engagement_id": engagement_id}, {"_id": 0}).limit(500)]


@router.post("/audit-engagements/{engagement_id}/materiality")
async def upsert_materiality(request: Request, engagement_id: str, body: sch.MaterialityBaseIn, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    row = body.model_dump()
    prior = await db.ca_materiality.find_one({"engagement_id": engagement_id}, {"_id": 0})
    record_id = (prior or {}).get("id") or str(uuid.uuid4())
    options = compute_benchmark_options(row)
    key, calc = select_default_benchmark(options)
    benchmark = row.get("benchmark_selected") or key
    if benchmark not in options:
        benchmark, calc = select_default_benchmark(options)
    calc_amount = options.get(benchmark, calc)
    final_m = float(row["override_amount"]) if row.get("override_amount") is not None else float(calc_amount)
    perf_lo, perf_hi, trivial = derive_performance_and_trivial(final_m)
    perf_mid = round((perf_lo + perf_hi) / 2.0, 2)
    doc: Dict[str, Any] = {
        "id": record_id,
        "engagement_id": engagement_id,
        **row,
        "benchmark_options": options,
        "benchmark_selected": benchmark,
        "calculated_materiality": round(float(calc_amount), 2),
        "final_materiality": round(final_m, 2),
        "performance_materiality_low": round(perf_lo, 2),
        "performance_materiality_high": round(perf_hi, 2),
        "performance_materiality": perf_mid,
        "trivial_threshold": round(trivial, 2),
        "prepared_by": current["email"],
        "reviewed_by": None,
        "approved_by": None,
        "approval_status": "prepared",
        "updated_at": _now(),
    }
    await db.ca_materiality.update_one({"engagement_id": engagement_id}, {"$set": doc}, upsert=True)
    saved = await db.ca_materiality.find_one({"engagement_id": engagement_id}, {"_id": 0})
    if not saved:
        raise HTTPException(500, "Materiality save failed")
    exs = await _exceptions_for_engagement(engagement_id)
    return enrich_materiality_record(saved, engagement_id, exs)


@router.get("/audit-engagements/{engagement_id}/materiality")
async def get_materiality(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    m = await db.ca_materiality.find_one({"engagement_id": engagement_id}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Materiality not found")
    exs = await _exceptions_for_engagement(engagement_id)
    return enrich_materiality_record(m, engagement_id, exs)


@router.put("/materiality/{materiality_id}")
async def update_materiality(materiality_id: str, body: sch.MaterialityBaseIn, request: Request, current=Depends(get_current_user)):
    existing = await db.ca_materiality.find_one({"id": materiality_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "Materiality not found")
    engagement_id = existing["engagement_id"]
    await _engagement_or_404(str(engagement_id), current=current, request=request)
    merged = {**existing, **{k: v for k, v in body.model_dump().items() if v is not None}}
    if merged.get("override_amount") is not None and abs(float(merged.get("override_amount") or 0)) > 1e-12:
        if not str(merged.get("override_reason") or "").strip():
            raise HTTPException(400, "override_reason is required when override_amount is set")
    options = compute_benchmark_options(merged)
    benchmark = merged.get("benchmark_selected") or select_default_benchmark(options)[0]
    if benchmark not in options:
        benchmark, _calc_fallback = select_default_benchmark(options)
    calc_amount = options.get(benchmark, select_default_benchmark(options)[1])
    final_m = float(merged["override_amount"]) if merged.get("override_amount") is not None else float(calc_amount)
    perf_lo, perf_hi, trivial = derive_performance_and_trivial(final_m)
    merged.update(
        {
            "benchmark_options": options,
            "benchmark_selected": benchmark,
            "calculated_materiality": round(float(calc_amount), 2),
            "final_materiality": round(final_m, 2),
            "performance_materiality_low": round(perf_lo, 2),
            "performance_materiality_high": round(perf_hi, 2),
            "performance_materiality": round((perf_lo + perf_hi) / 2.0, 2),
            "trivial_threshold": round(trivial, 2),
            "updated_at": _now(),
            "approval_status": "prepared",
            "prepared_by": current["email"],
            "reviewed_by": None,
            "approved_by": None,
        }
    )
    await db.ca_materiality.replace_one({"id": materiality_id}, merged)
    saved = await db.ca_materiality.find_one({"id": materiality_id}, {"_id": 0})
    exs = await _exceptions_for_engagement(engagement_id)
    return enrich_materiality_record(saved or merged, engagement_id, exs)


@router.post("/materiality/{materiality_id}/approve")
async def approve_materiality(materiality_id: str, body: sch.MaterialityApproveIn, request: Request, current=Depends(get_current_user)):
    m = await db.ca_materiality.find_one({"id": materiality_id}, {"_id": 0})
    if not m:
        raise HTTPException(404, "Materiality not found")
    eng_id = m.get("engagement_id") or ""
    if eng_id:
        await _engagement_or_404(str(eng_id), current=current, request=request)
    sets: Dict[str, Any] = {"approval_status": body.approval_status, "updated_at": _now()}
    if body.approval_status == "prepared":
        sets["prepared_by"] = body.prepared_by or current["email"]
        sets["reviewed_by"] = None
        sets["approved_by"] = None
    elif body.approval_status == "reviewed":
        sets["reviewed_by"] = body.reviewed_by
    elif body.approval_status == "approved":
        sets["approved_by"] = body.approved_by
    elif body.approval_status == "draft":
        sets["reviewed_by"] = None
        sets["approved_by"] = None
    await db.ca_materiality.update_one({"id": materiality_id}, {"$set": sets})
    saved = await db.ca_materiality.find_one({"id": materiality_id}, {"_id": 0})
    exs = await _exceptions_for_engagement(eng_id)
    return enrich_materiality_record(saved or m, eng_id, exs)


# ----- RACM / Risks -----
@router.post("/audit-engagements/{engagement_id}/risks")
async def create_risk(request: Request, engagement_id: str, body: sch.AuditRiskCreate, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    dump = body.model_dump()
    racm, titles = racm_svc.merge_racm_procedures_from_create(dump)
    dump.pop("procedures", None)
    dump["audit_procedures"] = titles
    scores = risk_scores(body.likelihood_score, body.impact_score, body.control_effectiveness_score)
    rid = str(uuid.uuid4())
    doc = {
        "id": rid,
        "engagement_id": engagement_id,
        **dump,
        "racm_procedures": racm,
        **scores,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.ca_risks.insert_one(dict(doc))
    await audit_log(current["email"], "create_risk", "audit_risk", rid, {"engagement_id": engagement_id})
    return racm_svc.normalize_risk_racm(doc)


@router.get("/audit-engagements/{engagement_id}/risks")
async def list_risks(
    request: Request,
    engagement_id: str,
    high_risk_only: bool = False,
    owner: Optional[str] = None,
    process_area: Optional[str] = None,
    financial_statement_area: Optional[str] = None,
    current=Depends(get_current_user),
):
    await _engagement_or_404(engagement_id, current=current, request=request)
    q: Dict[str, Any] = {"engagement_id": engagement_id}
    if high_risk_only:
        q["risk_rating"] = {"$in": ["high", "critical"]}
    if owner:
        q["owner"] = owner
    if process_area:
        q["process_area"] = {"$regex": process_area, "$options": "i"}
    if financial_statement_area:
        q["financial_statement_area"] = {"$regex": financial_statement_area, "$options": "i"}
    rows = [r async for r in db.ca_risks.find(q, {"_id": 0}).sort("inherent_risk_score", -1)]
    return [racm_svc.normalize_risk_racm(r) for r in rows]


@router.get("/audit-engagements/{engagement_id}/risks/audit-plan-preview")
async def racm_audit_plan_preview(request: Request, engagement_id: str, current=Depends(get_current_user)):
    """High / critical risks and their procedures — auto audit plan emphasis."""
    await _engagement_or_404(engagement_id, current=current, request=request)
    rows = [r async for r in db.ca_risks.find({"engagement_id": engagement_id}, {"_id": 0})]
    norm = [racm_svc.normalize_risk_racm(r) for r in rows]
    return {"engagement_id": engagement_id, "auto_plan_items": racm_svc.build_audit_plan_preview(norm)}


@router.post("/audit-engagements/{engagement_id}/risks/generate-procedures-from-high-risk")
async def generate_procedures_from_high_risk(request: Request, engagement_id: str, current=Depends(get_current_user)):
    """Add default RACM procedures for high/critical risks that have none (links to audit plan)."""
    await _engagement_or_404(engagement_id, current=current, request=request)
    updated = 0
    async for r in db.ca_risks.find(
        {"engagement_id": engagement_id, "risk_rating": {"$in": ["high", "critical"]}}, {"_id": 0}
    ):
        if r.get("racm_procedures") or r.get("audit_procedures"):
            continue
        cat = r.get("risk_category") or "Financial Reporting Risk"
        new_procs = racm_svc.default_procedures_for_category(cat)
        titles = [p["title"] for p in new_procs]
        await db.ca_risks.update_one(
            {"id": r["id"]},
            {"$set": {"racm_procedures": new_procs, "audit_procedures": titles, "updated_at": _now()}},
        )
        updated += 1
    rows = [r async for r in db.ca_risks.find({"engagement_id": engagement_id}, {"_id": 0})]
    return {"updated_risks": updated, "risks": [racm_svc.normalize_risk_racm(r) for r in rows]}


@router.get("/risks/{risk_id}")
async def get_risk(risk_id: str, request: Request, current=Depends(get_current_user)):
    r = await db.ca_risks.find_one({"id": risk_id}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Risk not found")
    await _assert_engagement_scope_for_doc(r, current=current, request=request, not_found_detail="Risk not found")
    return racm_svc.normalize_risk_racm(r)


@router.put("/risks/{risk_id}")
async def update_risk(risk_id: str, body: sch.AuditRiskUpdate, request: Request, current=Depends(get_current_user)):
    r = await db.ca_risks.find_one({"id": risk_id}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Risk not found")
    await _assert_engagement_scope_for_doc(r, current=current, request=request, not_found_detail="Risk not found")
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    merged = {**r, **patch}
    if "audit_procedures" in patch and patch["audit_procedures"] is not None and "racm_procedures" not in patch:
        merged["racm_procedures"] = [
            {"id": str(uuid.uuid4()), "title": t, "description": "", "source": "manual"}
            for t in patch["audit_procedures"]
            if isinstance(t, str) and t.strip()
        ]
        merged["audit_procedures"] = [p["title"] for p in merged["racm_procedures"]]
    if "likelihood_score" in patch or "impact_score" in patch or "control_effectiveness_score" in patch:
        racm_svc.recompute_scores_if_needed(merged)
    merged["updated_at"] = _now()
    await db.ca_risks.replace_one({"id": risk_id}, merged)
    return racm_svc.normalize_risk_racm(merged)


@router.delete("/risks/{risk_id}")
async def delete_risk(risk_id: str, request: Request, current=Depends(get_current_user)):
    r = await db.ca_risks.find_one({"id": risk_id}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Risk not found")
    await _assert_engagement_scope_for_doc(r, current=current, request=request, not_found_detail="Risk not found")
    await db.ca_risk_control_map.delete_many({"risk_id": risk_id})
    await db.ca_risks.delete_one({"id": risk_id})
    return {"deleted": True}


@router.post("/risks/{risk_id}/controls")
async def map_risk_control(risk_id: str, body: sch.RiskControlLink, request: Request, current=Depends(get_current_user)):
    r = await db.ca_risks.find_one({"id": risk_id}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Risk not found")
    await _assert_engagement_scope_for_doc(r, current=current, request=request, not_found_detail="Risk not found")
    ctrl = await db.controls.find_one({"id": body.control_id}, {"_id": 0, "id": 1, "code": 1, "name": 1})
    if not ctrl:
        raise HTTPException(404, "Control not found in controls engine library")
    links = list(r.get("linked_controls") or [])
    if body.control_id not in links:
        links.append(body.control_id)
    await db.ca_risks.update_one({"id": risk_id}, {"$set": {"linked_controls": links, "updated_at": _now()}})
    mid = str(uuid.uuid4())
    await db.ca_risk_control_map.insert_one(
        {
            "id": mid,
            "risk_id": risk_id,
            "control_id": body.control_id,
            "control_code": ctrl.get("code"),
            "control_name": ctrl.get("name"),
            "created_at": _now(),
        }
    )
    out = await db.ca_risks.find_one({"id": risk_id}, {"_id": 0})
    return racm_svc.normalize_risk_racm(out or r)


@router.post("/risks/{risk_id}/procedures")
async def add_procedure(risk_id: str, body: sch.RiskProcedureIn, request: Request, current=Depends(get_current_user)):
    r = await db.ca_risks.find_one({"id": risk_id}, {"_id": 0})
    if not r:
        raise HTTPException(404, "Risk not found")
    await _assert_engagement_scope_for_doc(r, current=current, request=request, not_found_detail="Risk not found")
    nr = racm_svc.normalize_risk_racm(r)
    procs = list(nr.get("racm_procedures") or [])
    row = {
        "id": body.id or str(uuid.uuid4()),
        "title": body.title,
        "description": (body.description or "").strip(),
        "source": body.source or "manual",
    }
    procs.append(row)
    titles = [p.get("title") for p in procs if p.get("title")]
    await db.ca_risks.update_one(
        {"id": risk_id}, {"$set": {"racm_procedures": procs, "audit_procedures": titles, "updated_at": _now()}}
    )
    out = await db.ca_risks.find_one({"id": risk_id}, {"_id": 0})
    return racm_svc.normalize_risk_racm(out or r)


@router.get("/audit-engagements/{engagement_id}/risk-heatmap")
async def risk_heatmap(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    cells: Dict[str, Dict[str, int]] = {}
    for r in await db.ca_risks.find({"engagement_id": engagement_id}, {"_id": 0}).to_list(length=None):
        proc = r.get("process_area") or "General"
        cat = r.get("risk_category") or "Other"
        cells.setdefault(proc, {}).setdefault(cat, 0)
        cells[proc][cat] += int(r.get("inherent_risk_score") or 0)
    return {
        "matrix": cells,
        "risk_categories": [
            "Financial Reporting Risk",
            "Fraud Risk",
            "Compliance Risk",
            "Operational Risk",
            "IT/ERP Risk",
            "Tax Risk",
        ],
    }


@router.get("/audit-engagements/{engagement_id}/risks/export.xlsx")
async def export_racm_xlsx(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "RACM"
    ws.append(
        [
            "risk_id",
            "title",
            "category",
            "process",
            "fs_area",
            "likelihood",
            "impact",
            "inherent",
            "residual",
            "rating",
            "controls",
            "procedures",
        ]
    )
    for r in await db.ca_risks.find({"engagement_id": engagement_id}, {"_id": 0}).to_list(length=None):
        nr = racm_svc.normalize_risk_racm(r)
        ws.append(
            [
                r.get("id"),
                r.get("risk_title"),
                r.get("risk_category"),
                r.get("process_area"),
                r.get("financial_statement_area"),
                r.get("likelihood_score"),
                r.get("impact_score"),
                r.get("inherent_risk_score"),
                r.get("residual_risk_score"),
                r.get("risk_rating"),
                ",".join(r.get("linked_controls") or []),
                racm_svc.procedure_titles_for_index(nr),
            ]
        )
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="rACM-{engagement_id}.xlsx"'},
    )


# ----- Financial statements -----
@router.post("/audit-engagements/{engagement_id}/trial-balance/upload")
async def upload_trial_balance(
    request: Request,
    engagement_id: str,
    file: UploadFile = File(...),
    current=Depends(get_current_user),
):
    await _engagement_or_404(engagement_id, current=current, request=request)
    raw = await file.read()
    try:
        if file.filename and file.filename.lower().endswith(".csv"):
            df = pd.read_csv(io.BytesIO(raw))
        else:
            df = pd.read_excel(io.BytesIO(raw))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Could not parse file: {e}") from e
    cols = {c.lower().strip(): c for c in df.columns}
    def col(*names: str) -> Optional[str]:
        for n in names:
            if n in df.columns:
                return n
            if n in cols:
                return cols[n]
        return None

    c_code = col("account_code", "gl_code", "code")
    c_name = col("account_name", "name", "description")
    c_dr = col("debit", "dr")
    c_cr = col("credit", "cr")
    c_od = col("opening_debit", "open_dr", "op_debit")
    c_oc = col("opening_credit", "open_cr", "op_credit")
    c_cd = col("closing_debit", "close_dr", "cl_debit")
    c_cc = col("closing_credit", "close_cr", "cl_credit")
    c_cls = col("classification", "classification_override", "fs_bucket", "mapped_bucket")
    if not c_code or not c_name:
        raise HTTPException(400, "CSV/XLSX must include account_code and account_name columns")
    tb_id = str(uuid.uuid4())
    lines: List[Dict[str, Any]] = []
    total_dr = total_cr = 0.0
    for _, row in df.iterrows():
        raw_code = row.get(c_code)
        if raw_code is None or (isinstance(raw_code, float) and pd.isna(raw_code)):
            continue
        code = str(raw_code).strip()
        if not code:
            continue
        raw_name = row.get(c_name)
        if raw_name is None or (isinstance(raw_name, float) and pd.isna(raw_name)):
            acct_name = ""
        else:
            acct_name = str(raw_name).strip() or "(no name)"
        dr = float(row.get(c_dr, 0) or 0) if c_dr else 0.0
        cr = float(row.get(c_cr, 0) or 0) if c_cr else 0.0
        total_dr += dr
        total_cr += cr
        rec: Dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "trial_balance_id": tb_id,
            "engagement_id": engagement_id,
            "account_code": code,
            "account_name": acct_name,
            "debit": dr,
            "credit": cr,
        }
        if c_od:
            try:
                rec["opening_debit"] = float(row.get(c_od, 0) or 0)
            except (TypeError, ValueError):
                rec["opening_debit"] = None
        if c_oc:
            try:
                rec["opening_credit"] = float(row.get(c_oc, 0) or 0)
            except (TypeError, ValueError):
                rec["opening_credit"] = None
        if c_cd:
            try:
                rec["closing_debit"] = float(row.get(c_cd, 0) or 0)
            except (TypeError, ValueError):
                rec["closing_debit"] = None
        if c_cc:
            try:
                rec["closing_credit"] = float(row.get(c_cc, 0) or 0)
            except (TypeError, ValueError):
                rec["closing_credit"] = None
        if c_cls and row.get(c_cls) is not None and not (isinstance(row.get(c_cls), float) and pd.isna(row.get(c_cls))):
            raw_cls = str(row.get(c_cls)).strip().lower()
            if raw_cls in ("assets", "liabilities", "equity", "revenue", "expenses"):
                rec["classification_override"] = raw_cls
        lines.append(rec)
    await db.ca_trial_balance_lines.delete_many({"engagement_id": engagement_id})
    await db.ca_trial_balance.delete_many({"engagement_id": engagement_id})
    meta = {
        "id": tb_id,
        "engagement_id": engagement_id,
        "filename": file.filename,
        "rows": len(lines),
        "total_debit": round(total_dr, 2),
        "total_credit": round(total_cr, 2),
        "balanced": abs(total_dr - total_cr) < 0.01,
        "uploaded_by": current["email"],
        "uploaded_at": _now(),
    }
    await db.ca_trial_balance.insert_one(dict(meta))
    err, warn = validate_trial_balance_upload(lines)
    if err:
        raise HTTPException(400, "; ".join(err))
    meta["validation_warnings"] = warn
    if lines:
        await db.ca_trial_balance_lines.insert_many(lines)
    return meta


@router.get("/audit-engagements/{engagement_id}/trial-balance")
async def get_trial_balance(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    meta = await db.ca_trial_balance.find_one({"engagement_id": engagement_id}, {"_id": 0}, sort=[("uploaded_at", -1)])
    lines = [l async for l in db.ca_trial_balance_lines.find({"engagement_id": engagement_id}, {"_id": 0}).limit(5000)]
    return {"meta": meta, "lines": lines}


async def _generate_fs_snapshot(engagement_id: str, body: sch.FinancialGenerateIn, current: Any) -> Dict[str, Any]:
    lines = [l async for l in db.ca_trial_balance_lines.find({"engagement_id": engagement_id}, {"_id": 0})]
    if not lines:
        raise HTTPException(400, "Upload trial balance first")
    tb_meta = await db.ca_trial_balance.find_one({"engagement_id": engagement_id}, {"_id": 0}, sort=[("uploaded_at", -1)])
    total_dr = float(tb_meta.get("total_debit") or 0) if tb_meta else sum(float(l.get("debit") or 0) for l in lines)
    total_cr = float(tb_meta.get("total_credit") or 0) if tb_meta else sum(float(l.get("credit") or 0) for l in lines)
    mat = await db.ca_materiality.find_one({"engagement_id": engagement_id}, {"_id": 0})
    final_m = float(mat.get("final_materiality") or 0) if mat else 0.0
    prev = await db.ca_fs_snapshots.find_one({"engagement_id": engagement_id}, {"_id": 0}, sort=[("generated_at", -1)])
    prev_by_code: Dict[str, float] = dict((prev or {}).get("account_balances") or {})
    prev_bs = {r["line"]: r["amount"] for r in (prev or {}).get("balance_sheet", []) if isinstance(r, dict) and "line" in r}

    mappings = fs_map.build_financial_statement_mappings(lines)
    bs_detail = fs_map.build_balance_sheet_lines(lines, mappings, prev_by_code, final_m)
    pl_detail = fs_map.build_profit_loss_lines(lines, mappings, prev_by_code, final_m)
    buckets_bs = {
        "assets": next((x["amount"] for x in bs_detail if x["bucket"] == "assets"), 0.0),
        "liabilities": next((x["amount"] for x in bs_detail if x["bucket"] == "liabilities"), 0.0),
        "equity": next((x["amount"] for x in bs_detail if x["bucket"] == "equity"), 0.0),
    }
    buckets_pl = {
        "revenue": next((x["amount"] for x in pl_detail if x["bucket"] == "revenue"), 0.0),
        "expenses": next((x["amount"] for x in pl_detail if x["bucket"] == "expenses"), 0.0),
    }
    pl_net_demo = float(buckets_pl["revenue"]) - float(buckets_pl["expenses"])
    cf_lines = fs_map.build_cash_flow_lines(buckets_bs, pl_net_demo)
    schedules = fs_map.build_financial_schedules(lines, mappings)
    variance_chart = fs_map.variance_chart_rows(bs_detail, pl_detail)

    issues: List[Dict[str, Any]] = []
    for ln in lines:
        for iss in analyze_trial_balance_line(ln, final_materiality=final_m):
            issues.append(iss)
        for iss in prior_period_movement_issues(ln, prev_by_code, final_materiality=final_m):
            issues.append(iss)
        for iss in opening_closing_snapshot_issues(ln):
            issues.append(iss)
    if prev_bs:
        for label, amt in [("Assets", buckets_bs["assets"]), ("Liabilities", buckets_bs["liabilities"]), ("Equity", buckets_bs["equity"])]:
            prev_amt = prev_bs.get(label) or prev_bs.get(label.title())
            if prev_amt is not None and final_m and abs(float(amt) - float(prev_amt)) >= final_m:
                issues.append(
                    {
                        "type": "material_movement_vs_prior",
                        "severity": "medium",
                        "message": f"{label} changed by {round(float(amt) - float(prev_amt), 2)} vs prior FS snapshot",
                        "line": {"account_code": "FS:" + label, "account_name": label, "debit": 0, "credit": 0},
                    }
                )
    validation = build_fs_validation_summary(buckets_bs, buckets_pl, total_dr, total_cr, issues)
    account_balances = {str(ln.get("account_code") or ""): fs_map.net_amount(ln) for ln in lines if ln.get("account_code")}
    snap: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "engagement_id": engagement_id,
        "balance_sheet": [{"line": k.title(), "amount": round(v, 2)} for k, v in buckets_bs.items()],
        "profit_loss": [{"line": k.title(), "amount": round(v, 2)} for k, v in buckets_pl.items()],
        "cash_flow": [{"line": x["line"], "amount": x["amount"], "id": x["id"], "section": x["section"]} for x in cf_lines],
        "balance_sheet_detail": bs_detail,
        "profit_loss_detail": pl_detail,
        "cash_flow_detail": cf_lines,
        "financial_statement_mappings": mappings,
        "financial_schedules": schedules,
        "variance_chart": variance_chart,
        "issues": issues,
        "validation": validation,
        "account_balances": account_balances,
        "generated_at": _now(),
        "profile": body.mapping_profile,
        "generated_by": current.get("email"),
    }
    await db.ca_fs_snapshots.insert_one(dict(snap))
    return snap


@router.post("/audit-engagements/{engagement_id}/financial-statements/generate")
async def generate_fs(request: Request, engagement_id: str, body: sch.FinancialGenerateIn, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    return await _generate_fs_snapshot(engagement_id, body, current)


@router.post("/audit-engagements/{engagement_id}/fs/generate")
async def generate_fs_short_path(request: Request, engagement_id: str, body: sch.FinancialGenerateIn, current=Depends(get_current_user)):
    """Alias for financial-statements/generate (FS audit engine)."""
    await _engagement_or_404(engagement_id, current=current, request=request)
    return await _generate_fs_snapshot(engagement_id, body, current)


@router.get("/audit-engagements/{engagement_id}/financial-statements/latest")
async def get_fs_latest(request: Request, engagement_id: str, current=Depends(get_current_user)):
    """Latest generated FS snapshot with validation summary and raised issues."""
    await _engagement_or_404(engagement_id, current=current, request=request)
    s = await db.ca_fs_snapshots.find_one({"engagement_id": engagement_id}, {"_id": 0}, sort=[("generated_at", -1)])
    if not s:
        return {"snapshot": None, "message": "Generate financial statements after uploading trial balance"}
    return {"snapshot": s}


@router.get("/audit-engagements/{engagement_id}/balance-sheet")
async def get_bs(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    s = await db.ca_fs_snapshots.find_one({"engagement_id": engagement_id}, {"_id": 0}, sort=[("generated_at", -1)])
    if not s:
        return {"snapshot_id": None, "generated_at": None, "summary": [], "lines": [], "variances": []}
    return {
        "snapshot_id": s.get("id"),
        "generated_at": s.get("generated_at"),
        "summary": s.get("balance_sheet") or [],
        "lines": s.get("balance_sheet_detail") or [],
        "variances": s.get("variance_chart") or [],
    }


@router.get("/audit-engagements/{engagement_id}/profit-loss")
async def get_pl(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    s = await db.ca_fs_snapshots.find_one({"engagement_id": engagement_id}, {"_id": 0}, sort=[("generated_at", -1)])
    if not s:
        return {"snapshot_id": None, "generated_at": None, "summary": [], "lines": [], "variances": []}
    return {
        "snapshot_id": s.get("id"),
        "generated_at": s.get("generated_at"),
        "summary": s.get("profit_loss") or [],
        "lines": s.get("profit_loss_detail") or [],
        "variances": s.get("variance_chart") or [],
    }


@router.get("/audit-engagements/{engagement_id}/cash-flow")
async def get_cf(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    s = await db.ca_fs_snapshots.find_one({"engagement_id": engagement_id}, {"_id": 0}, sort=[("generated_at", -1)])
    if not s:
        return {"snapshot_id": None, "generated_at": None, "summary": [], "lines": []}
    return {
        "snapshot_id": s.get("id"),
        "generated_at": s.get("generated_at"),
        "summary": s.get("cash_flow") or [],
        "lines": s.get("cash_flow_detail") or [],
    }


@router.get("/audit-engagements/{engagement_id}/fs/drilldown")
async def fs_drilldown(
    request: Request,
    engagement_id: str,
    account_code: str = Query(..., min_length=1),
    current=Depends(get_current_user),
):
    """Return demo ledger postings for a trial balance account (drill to journal)."""
    await _engagement_or_404(engagement_id, current=current, request=request)
    code = (account_code or "").strip()
    if not code:
        raise HTTPException(400, "account_code is required")
    ln = await db.ca_trial_balance_lines.find_one({"engagement_id": engagement_id, "account_code": code}, {"_id": 0})
    if not ln:
        raise HTTPException(404, "Account not on current trial balance")
    net = fs_map.net_amount(ln)
    txs = fs_map.demo_ledger_transactions_for_account(code, str(ln.get("account_name") or ""), net)
    return {
        "engagement_id": engagement_id,
        "account_code": code,
        "account_name": ln.get("account_name"),
        "trial_balance_line_id": ln.get("id"),
        "net_balance": round(net, 2),
        "transactions": txs,
    }


@router.get("/audit-engagements/{engagement_id}/audit-adjustments")
async def list_audit_adjustments(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    cur = db.ca_audit_adjustments.find({"engagement_id": engagement_id}, {"_id": 0}).sort("created_at", -1).limit(500)
    rows = await cur.to_list(length=500)
    return {"items": rows}


@router.post("/audit-engagements/{engagement_id}/audit-adjustments")
async def create_adjustment(request: Request, engagement_id: str, body: sch.AuditAdjustmentCreate, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    adj = {"id": str(uuid.uuid4()), "engagement_id": engagement_id, **body.model_dump(), "created_at": _now()}
    await db.ca_audit_adjustments.insert_one(dict(adj))
    return adj


@router.post("/audit-adjustments")
async def create_adjustment_root(request: Request, body: sch.AuditAdjustmentCreateRoot, current=Depends(get_current_user)):
    await _engagement_or_404(body.engagement_id, current=current, request=request)
    payload = body.model_dump()
    eid = payload.pop("engagement_id")
    adj = {"id": str(uuid.uuid4()), "engagement_id": eid, **payload, "created_at": _now()}
    await db.ca_audit_adjustments.insert_one(dict(adj))
    return adj


@router.put("/audit-adjustments/{adjustment_id}")
async def update_adjustment(adjustment_id: str, body: sch.AuditAdjustmentUpdate, request: Request, current=Depends(get_current_user)):
    a = await db.ca_audit_adjustments.find_one({"id": adjustment_id}, {"_id": 0})
    if not a:
        raise HTTPException(404, "Adjustment not found")
    await _assert_engagement_scope_for_doc(a, current=current, request=request, not_found_detail="Adjustment not found")
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    await db.ca_audit_adjustments.update_one({"id": adjustment_id}, {"$set": patch})
    return await db.ca_audit_adjustments.find_one({"id": adjustment_id}, {"_id": 0})


# ----- Schedule audit (statutory workbook per FS area) -----
def _validate_schedule_type(schedule_type: str) -> str:
    st = (schedule_type or "").strip().lower()
    if st not in ca_sched.SCHEDULE_TYPES:
        raise HTTPException(400, f"schedule_type must be one of: {', '.join(ca_sched.SCHEDULE_TYPES)}")
    return st


async def _ensure_schedule_document(engagement_id: str, schedule_type: str) -> Dict[str, Any]:
    doc = await db.ca_schedule_audit.find_one({"engagement_id": engagement_id, "schedule_type": schedule_type}, {"_id": 0})
    if not doc:
        payload = ca_sched.build_demo_payload(schedule_type)
        doc = {
            "id": str(uuid.uuid4()),
            "engagement_id": engagement_id,
            "schedule_type": schedule_type,
            "payload": payload,
            "audit_procedures": ca_sched.default_audit_procedures(schedule_type),
            "evidence": [],
            "conclusion": None,
            "exceptions": [],
            "updated_at": _now(),
        }
        await db.ca_schedule_audit.insert_one(dict(doc))
    else:
        sets: Dict[str, Any] = {}
        if not doc.get("audit_procedures"):
            sets["audit_procedures"] = ca_sched.default_audit_procedures(schedule_type)
        if doc.get("evidence") is None:
            sets["evidence"] = []
        if doc.get("exceptions") is None:
            sets["exceptions"] = []
        if sets:
            sets["updated_at"] = _now()
            await db.ca_schedule_audit.update_one(
                {"engagement_id": engagement_id, "schedule_type": schedule_type},
                {"$set": sets},
            )
            doc = await db.ca_schedule_audit.find_one({"engagement_id": engagement_id, "schedule_type": schedule_type}, {"_id": 0})
    return doc or {}


@router.get("/audit-engagements/{engagement_id}/schedules")
async def list_schedule_audit_modules(request: Request, engagement_id: str, current=Depends(get_current_user)):
    """Dashboard summary: each statutory schedule area with flags and sign-off state."""
    await _engagement_or_404(engagement_id, current=current, request=request)
    items: List[Dict[str, Any]] = []
    for st in ca_sched.SCHEDULE_TYPES:
        doc = await db.ca_schedule_audit.find_one({"engagement_id": engagement_id, "schedule_type": st}, {"_id": 0})
        if not doc:
            items.append(
                {
                    "schedule_type": st,
                    "initialized": False,
                    "exception_flags": {},
                    "exception_count": 0,
                    "evidence_count": 0,
                    "procedure_total": 0,
                    "procedure_completed": 0,
                    "conclusion_signed": False,
                }
            )
            continue
        aug = ca_sched.augment_schedule_for_api(doc)
        conc = aug.get("conclusion") or {}
        procs = aug.get("audit_procedures") or []
        done = sum(1 for p in procs if isinstance(p, dict) and p.get("status") == "completed")
        items.append(
            {
                "schedule_type": st,
                "initialized": True,
                "exception_flags": aug.get("exception_flags") or {},
                "exception_count": len(aug.get("exceptions") or []),
                "evidence_count": len(aug.get("evidence") or []),
                "procedure_total": len(procs),
                "procedure_completed": done,
                "conclusion_signed": bool(conc.get("signed_off")),
                "updated_at": aug.get("updated_at"),
            }
        )
    return {"engagement_id": engagement_id, "schedules": items}


@router.get("/audit-engagements/{engagement_id}/schedules/{schedule_type}")
async def get_schedule(request: Request, engagement_id: str, schedule_type: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    st = _validate_schedule_type(schedule_type)
    doc = await _ensure_schedule_document(engagement_id, st)
    return ca_sched.augment_schedule_for_api(doc)


# Typed schedule URLs are served by GET .../schedules/{schedule_type} for:
# assets | revenue | expenses | inventory | liabilities

@router.post("/audit-engagements/{engagement_id}/schedules/{schedule_type}/conclusion")
async def schedule_conclusion(
    request: Request,
    engagement_id: str,
    schedule_type: str,
    body: sch.ScheduleConclusionIn,
    current=Depends(get_current_user),
):
    await _engagement_or_404(engagement_id, current=current, request=request)
    st = _validate_schedule_type(schedule_type)
    await _ensure_schedule_document(engagement_id, st)
    row = body.model_dump()
    if row.get("signed_off") and not row.get("reviewer_signed_at"):
        row["reviewer_signed_at"] = _now()
    await db.ca_schedule_audit.update_one(
        {"engagement_id": engagement_id, "schedule_type": st},
        {"$set": {"conclusion": row, "updated_at": _now()}},
    )
    doc = await db.ca_schedule_audit.find_one({"engagement_id": engagement_id, "schedule_type": st}, {"_id": 0})
    return ca_sched.augment_schedule_for_api(doc or {})


@router.post("/audit-engagements/{engagement_id}/schedules/{schedule_type}/evidence")
async def schedule_attach_evidence(
    request: Request,
    engagement_id: str,
    schedule_type: str,
    body: sch.ScheduleEvidenceAttachIn,
    current=Depends(get_current_user),
):
    await _engagement_or_404(engagement_id, current=current, request=request)
    st = _validate_schedule_type(schedule_type)
    await _ensure_schedule_document(engagement_id, st)
    ev = {
        "id": str(uuid.uuid4()),
        "label": body.label,
        "reference": body.reference,
        "ref_type": body.ref_type,
        "uploaded_by": current.get("email"),
        "uploaded_at": _now(),
    }
    await db.ca_schedule_audit.update_one(
        {"engagement_id": engagement_id, "schedule_type": st},
        {"$push": {"evidence": ev}, "$set": {"updated_at": _now()}},
    )
    doc = await db.ca_schedule_audit.find_one({"engagement_id": engagement_id, "schedule_type": st}, {"_id": 0})
    return ca_sched.augment_schedule_for_api(doc or {})


@router.put("/audit-engagements/{engagement_id}/schedules/{schedule_type}/procedures/{procedure_id}")
async def schedule_procedure_status(
    request: Request,
    engagement_id: str,
    schedule_type: str,
    procedure_id: str,
    body: sch.ScheduleProcedureStatusIn,
    current=Depends(get_current_user),
):
    await _engagement_or_404(engagement_id, current=current, request=request)
    st = _validate_schedule_type(schedule_type)
    doc = await _ensure_schedule_document(engagement_id, st)
    procs = list(doc.get("audit_procedures") or [])
    found = False
    for i, p in enumerate(procs):
        if isinstance(p, dict) and p.get("id") == procedure_id:
            procs[i] = {**p, "status": body.status}
            found = True
            break
    if not found:
        raise HTTPException(404, "Procedure not found on this schedule")
    await db.ca_schedule_audit.update_one(
        {"engagement_id": engagement_id, "schedule_type": st},
        {"$set": {"audit_procedures": procs, "updated_at": _now()}},
    )
    doc2 = await db.ca_schedule_audit.find_one({"engagement_id": engagement_id, "schedule_type": st}, {"_id": 0})
    return ca_sched.augment_schedule_for_api(doc2 or {})


@router.post("/audit-engagements/{engagement_id}/schedules/{schedule_type}/exception")
async def schedule_exception(
    request: Request,
    engagement_id: str,
    schedule_type: str,
    body: sch.ScheduleExceptionIn,
    current=Depends(get_current_user),
):
    await _engagement_or_404(engagement_id, current=current, request=request)
    st = _validate_schedule_type(schedule_type)
    await _ensure_schedule_document(engagement_id, st)
    ex = {"id": str(uuid.uuid4()), **body.model_dump(), "created_at": _now()}
    await db.ca_schedule_audit.update_one(
        {"engagement_id": engagement_id, "schedule_type": st},
        {"$push": {"exceptions": ex}, "$set": {"updated_at": _now()}},
    )
    if body.create_case:
        fake_ex = {
            "id": str(uuid.uuid4()),
            "control_id": "CA-SCHEDULE",
            "control_code": "CA-SCHEDULE",
            "control_name": f"Schedule audit · {schedule_type}",
            "process": "Record-to-Report",
            "entity": "US-HQ",
            "severity": body.severity if body.severity in ("critical", "high", "medium", "low") else "medium",
            "status": "open",
            "materiality_score": 0.5,
            "anomaly_score": 0.4,
            "financial_exposure": float(body.amount or 0),
            "source_record_type": "schedule_audit",
            "source_record_id": ex["id"],
            "detected_at": _now(),
            "title": body.title,
            "summary": body.description,
            "engagement_id": engagement_id,
        }
        await db.exceptions.insert_one(dict(fake_ex))
        case = csvc.case_from_exception(fake_ex, current["email"], None)
        case["engagement_id"] = engagement_id
        await db.cases.insert_one(dict(case))
    doc = await db.ca_schedule_audit.find_one({"engagement_id": engagement_id, "schedule_type": st}, {"_id": 0})
    return ca_sched.augment_schedule_for_api(doc or {})


# ----- IFC -----
def _ifc_seed_rows() -> List[Dict[str, Any]]:
    return [
        {
            "id": str(uuid.uuid4()),
            "code": "IFC-REV-01",
            "name": "Revenue cutoff control",
            "control_type": "preventive",
            "process": "Order-to-Cash",
            "description": "System enforces shipment date for revenue recognition.",
            "objectives": [{"id": str(uuid.uuid4()), "statement": "Revenue is recognised only when performance obligations are satisfied."}],
            "activities": [{"id": str(uuid.uuid4()), "description": "System hard-stop on invoice without shipment", "frequency": "per invoice"}],
            "owners": [{"email": "rev.owner@entity.com", "name": "Revenue Controller", "role": "process_owner"}],
        },
        {
            "id": str(uuid.uuid4()),
            "code": "IFC-AP-02",
            "name": "Payment run maker-checker",
            "control_type": "detective",
            "process": "Procure-to-Pay",
            "description": "Dual approval for payment batches above threshold.",
            "objectives": [{"id": str(uuid.uuid4()), "statement": "Disbursements are authorised and accurate."}],
            "activities": [{"id": str(uuid.uuid4()), "description": "Second approver on high-value payment batches", "frequency": "daily payment run"}],
            "owners": [{"email": "ap.owner@entity.com", "name": "AP Manager", "role": "process_owner"}],
        },
        {
            "id": str(uuid.uuid4()),
            "code": "IFC-GL-03",
            "name": "Period-end journal review",
            "control_type": "IT-dependent",
            "process": "Record-to-Report",
            "description": "Workflow routes material journals to FC review queue.",
            "objectives": [{"id": str(uuid.uuid4()), "statement": "Material misstatements in JE are prevented or detected."}],
            "activities": [{"id": str(uuid.uuid4()), "description": "FC sign-off on flagged journals", "frequency": "month-end"}],
            "owners": [{"email": "gl.owner@entity.com", "name": "Financial Controller", "role": "control_owner"}],
        },
    ]


@router.get("/control-library")
async def control_library(
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    items = [i async for i in db.ca_control_library.find({}, {"_id": 0}).limit(500)]
    if not items:
        seed = _ifc_seed_rows()
        await db.ca_control_library.insert_many(seed)
        items = seed
    enriched = [ifc_svc.enrich_library_item(dict(i)) for i in items]
    return {"entity_code": eff, "items": enriched}


@router.post("/control-library")
async def add_control_library_item(body: sch.ControlLibraryItemIn, current=Depends(get_current_user)):
    await assert_super_admin_when_entity_scope_enforced(db, current=current)
    raw = body.model_dump()
    doc = {"id": str(uuid.uuid4()), **ifc_svc.normalize_library_write(raw)}
    doc = ifc_svc.enrich_library_item(doc)
    await db.ca_control_library.insert_one(dict(doc))
    return doc


@router.post("/audit-engagements/{engagement_id}/control-tests")
async def create_control_test(request: Request, engagement_id: str, body: sch.ControlTestCreate, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    lib_key = body.control_library_id or body.control_id
    proc: Optional[str] = None
    if lib_key:
        lib = await db.ca_control_library.find_one({"$or": [{"id": lib_key}, {"code": lib_key}]}, {"_id": 0})
        if lib:
            proc = lib.get("process")
    doc = {
        "id": str(uuid.uuid4()),
        "engagement_id": engagement_id,
        **body.model_dump(),
        "process": proc,
        "result": "pending",
        "effectiveness_score": None,
        "created_at": _now(),
    }
    await db.ca_control_tests.insert_one(dict(doc))
    return doc


@router.get("/audit-engagements/{engagement_id}/control-tests")
async def list_control_tests(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    return [t async for t in db.ca_control_tests.find({"engagement_id": engagement_id}, {"_id": 0})]


@router.get("/audit-engagements/{engagement_id}/ifc-heatmap")
async def ifc_heatmap(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    tests = [t async for t in db.ca_control_tests.find({"engagement_id": engagement_id}, {"_id": 0})]
    lib_raw = await db.ca_control_library.find({}, {"_id": 0}).to_list(length=2000)
    return ifc_svc.build_ifc_heatmap(tests, lib_raw)


@router.get("/audit-engagements/{engagement_id}/ifc-dashboard")
async def ifc_dashboard(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    tests = [t async for t in db.ca_control_tests.find({"engagement_id": engagement_id}, {"_id": 0})]
    defs = [d async for d in db.ca_control_deficiencies.find({"engagement_id": engagement_id}, {"_id": 0}).sort("created_at", -1).limit(200)]
    certs = [c async for c in db.ca_control_certifications.find({"engagement_id": engagement_id}, {"_id": 0}).sort("created_at", -1).limit(100)]
    lib_raw = await db.ca_control_library.find({}, {"_id": 0}).to_list(length=500)
    lib_items = [ifc_svc.enrich_library_item(dict(i)) for i in lib_raw]
    heatmap = ifc_svc.build_ifc_heatmap(tests, lib_raw)
    eff_counts = {"effective": 0, "partially_effective": 0, "ineffective": 0, "pending": 0}
    for t in tests:
        e = ifc_svc.effectiveness_from_test_row(t) or "pending"
        if e not in eff_counts:
            e = "pending"
        eff_counts[e] = eff_counts.get(e, 0) + 1
    return {
        "engagement_id": engagement_id,
        "control_tests": tests,
        "deficiencies": defs,
        "certifications": certs,
        "control_library_sample": lib_items[:12],
        "heatmap": heatmap,
        "effectiveness_summary": eff_counts,
    }


@router.get("/control-tests/{test_id}")
async def get_control_test(test_id: str, request: Request, current=Depends(get_current_user)):
    t = await db.ca_control_tests.find_one({"id": test_id}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Control test not found")
    await _assert_engagement_scope_for_doc(t, current=current, request=request, not_found_detail="Control test not found")
    return t


@router.put("/control-tests/{test_id}/result")
async def set_control_test_result(test_id: str, body: sch.ControlTestResultIn, request: Request, current=Depends(get_current_user)):
    t = await db.ca_control_tests.find_one({"id": test_id}, {"_id": 0})
    if not t:
        raise HTTPException(404, "Control test not found")
    await _assert_engagement_scope_for_doc(t, current=current, request=request, not_found_detail="Control test not found")
    dump = body.model_dump(exclude_unset=True)
    patch: Dict[str, Any] = {"updated_at": _now()}
    eff = dump.get("effectiveness_score")
    res = dump.get("result")
    if res == "pending" or res == "not_tested":
        patch["effectiveness_score"] = None
        patch["result"] = res
    elif eff:
        patch["effectiveness_score"] = eff
        patch["result"] = eff
    elif res == "deficient":
        patch["effectiveness_score"] = "ineffective"
        patch["result"] = "ineffective"
    elif res in ("effective", "partially_effective", "ineffective"):
        patch["effectiveness_score"] = res
        patch["result"] = res
    elif res is not None:
        patch["result"] = res
    if "evidence_refs" in dump:
        patch["evidence_refs"] = dump["evidence_refs"]
    if "notes" in dump:
        patch["notes"] = dump["notes"]
    await db.ca_control_tests.update_one({"id": test_id}, {"$set": patch})
    return await db.ca_control_tests.find_one({"id": test_id}, {"_id": 0})


@router.get("/audit-engagements/{engagement_id}/control-deficiencies")
async def list_control_deficiencies(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    cur = db.ca_control_deficiencies.find({"engagement_id": engagement_id}, {"_id": 0}).sort("created_at", -1).limit(500)
    return {"items": await cur.to_list(length=500)}


@router.post("/control-deficiencies")
async def create_deficiency(body: sch.ControlDeficiencyCreate, request: Request, current=Depends(get_current_user)):
    await _engagement_or_404(body.engagement_id, current=current, request=request)
    doc = {
        "id": str(uuid.uuid4()),
        **body.model_dump(),
        "management_response": None,
        "closure_notes": None,
        "case_id": None,
        "created_at": _now(),
    }
    await db.ca_control_deficiencies.insert_one(dict(doc))
    if body.create_case:
        fake_ex = {
            "id": str(uuid.uuid4()),
            "control_id": body.control_test_id,
            "control_code": "IFC-TEST",
            "control_name": "IFC control test deficiency",
            "process": "Record-to-Report",
            "entity": "US-HQ",
            "severity": body.severity,
            "status": "open",
            "materiality_score": 0.6,
            "anomaly_score": 0.5,
            "financial_exposure": 0.0,
            "source_record_type": "ifc_deficiency",
            "source_record_id": doc["id"],
            "detected_at": _now(),
            "title": "Control deficiency",
            "summary": body.description,
            "engagement_id": body.engagement_id,
        }
        await db.exceptions.insert_one(dict(fake_ex))
        case = csvc.case_from_exception(fake_ex, current["email"], None)
        case["engagement_id"] = body.engagement_id
        await db.cases.insert_one(dict(case))
        await db.ca_control_deficiencies.update_one({"id": doc["id"]}, {"$set": {"case_id": case.get("id")}})
    return await db.ca_control_deficiencies.find_one({"id": doc["id"]}, {"_id": 0})


@router.put("/control-deficiencies/{deficiency_id}")
async def update_deficiency(deficiency_id: str, body: sch.ControlDeficiencyUpdate, request: Request, current=Depends(get_current_user)):
    d = await db.ca_control_deficiencies.find_one({"id": deficiency_id}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Deficiency not found")
    await _assert_engagement_scope_for_doc(d, current=current, request=request, not_found_detail="Deficiency not found")
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if patch:
        patch["updated_at"] = _now()
        await db.ca_control_deficiencies.update_one({"id": deficiency_id}, {"$set": patch})
    return await db.ca_control_deficiencies.find_one({"id": deficiency_id}, {"_id": 0})


@router.post("/control-deficiencies/{deficiency_id}/management-response")
async def mgmt_response(deficiency_id: str, body: sch.ManagementResponseIn, request: Request, current=Depends(get_current_user)):
    d = await db.ca_control_deficiencies.find_one({"id": deficiency_id}, {"_id": 0})
    if not d:
        raise HTTPException(404, "Deficiency not found")
    await _assert_engagement_scope_for_doc(d, current=current, request=request, not_found_detail="Deficiency not found")
    await db.ca_control_deficiencies.update_one(
        {"id": deficiency_id},
        {"$set": {"management_response": {**body.model_dump(), "at": _now()}, "updated_at": _now()}},
    )
    return await db.ca_control_deficiencies.find_one({"id": deficiency_id}, {"_id": 0})


@router.post("/control-certifications")
async def control_cert(request: Request, body: sch.ControlCertificationIn, current=Depends(get_current_user)):
    await _engagement_or_404(body.engagement_id, current=current, request=request)
    doc = {"id": str(uuid.uuid4()), **body.model_dump(), "created_at": _now()}
    await db.ca_control_certifications.insert_one(dict(doc))
    return doc


# ----- Working papers -----
@router.post("/audit-engagements/{engagement_id}/working-papers/folders")
async def seed_wp_folders(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    if await db.ca_wp_folders.count_documents({"engagement_id": engagement_id}) == 0:
        rows = [{**f, "engagement_id": engagement_id} for f in default_wp_folders()]
        await db.ca_wp_folders.insert_many(rows)
    return [f async for f in db.ca_wp_folders.find({"engagement_id": engagement_id}, {"_id": 0})]


@router.get("/audit-engagements/{engagement_id}/working-papers")
async def list_wp(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    folders = [f async for f in db.ca_wp_folders.find({"engagement_id": engagement_id}, {"_id": 0})]
    if not folders:
        if await db.ca_wp_folders.count_documents({"engagement_id": engagement_id}) == 0:
            rows = [{**f, "engagement_id": engagement_id} for f in default_wp_folders()]
            await db.ca_wp_folders.insert_many(rows)
        folders = [f async for f in db.ca_wp_folders.find({"engagement_id": engagement_id}, {"_id": 0})]
    papers = [p async for p in db.ca_working_papers.find({"engagement_id": engagement_id}, {"_id": 0})]
    return {"folders": folders, "working_papers": papers}


@router.get("/audit-engagements/{engagement_id}/wp-workbench")
async def wp_workbench(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    folders = [f async for f in db.ca_wp_folders.find({"engagement_id": engagement_id}, {"_id": 0})]
    if not folders:
        if await db.ca_wp_folders.count_documents({"engagement_id": engagement_id}) == 0:
            rows = [{**f, "engagement_id": engagement_id} for f in default_wp_folders()]
            await db.ca_wp_folders.insert_many(rows)
        folders = [f async for f in db.ca_wp_folders.find({"engagement_id": engagement_id}, {"_id": 0})]
    papers = [p async for p in db.ca_working_papers.find({"engagement_id": engagement_id}, {"_id": 0})]
    plans = [p async for p in db.ca_sampling_plans.find({"engagement_id": engagement_id}, {"_id": 0}).sort("created_at", -1).limit(100)]
    vouches = [v async for v in db.ca_vouching_items.find({"engagement_id": engagement_id}, {"_id": 0}).sort("created_at", -1).limit(500)]
    return {"folders": folders, "working_papers": papers, "sampling_plans": plans, "vouching_items": vouches}


@router.get("/audit-engagements/{engagement_id}/sampling-plans")
async def list_sampling_plans(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    cur = db.ca_sampling_plans.find({"engagement_id": engagement_id}, {"_id": 0}).sort("created_at", -1).limit(200)
    return {"items": await cur.to_list(length=200)}


@router.get("/audit-engagements/{engagement_id}/vouching-items")
async def list_vouching_items(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    cur = db.ca_vouching_items.find({"engagement_id": engagement_id}, {"_id": 0}).sort("created_at", -1).limit(500)
    return {"items": await cur.to_list(length=500)}


@router.post("/working-papers")
async def create_wp(request: Request, body: sch.WorkingPaperCreate, current=Depends(get_current_user)):
    await _engagement_or_404(body.engagement_id, current=current, request=request)
    dump = body.model_dump()
    refs = [r for r in dump.pop("references", []) or []]
    ref = dump.get("reference") or await wp_svc.next_working_paper_reference(db, body.engagement_id, body.folder_id)
    doc = {
        "id": str(uuid.uuid4()),
        **dump,
        "reference": ref,
        "references": refs,
        "prepared_by": None,
        "reviewed_by": None,
        "approved_by": None,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.ca_working_papers.insert_one(dict(doc))
    return doc


@router.get("/working-papers/{working_paper_id}")
async def get_wp(working_paper_id: str, request: Request, current=Depends(get_current_user)):
    p = await db.ca_working_papers.find_one({"id": working_paper_id}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Working paper not found")
    await _assert_engagement_scope_for_doc(p, current=current, request=request, not_found_detail="Working paper not found")
    notes = [n async for n in db.ca_wp_review_notes.find({"working_paper_id": working_paper_id}, {"_id": 0})]
    signs = [s async for s in db.ca_wp_signoffs.find({"working_paper_id": working_paper_id}, {"_id": 0})]
    ev = [e async for e in db.ca_audit_evidence.find({"working_paper_id": working_paper_id}, {"_id": 0}).sort("created_at", -1).limit(200)]
    return {**p, "review_notes": notes, "sign_offs": signs, "audit_evidence": ev}


@router.put("/working-papers/{working_paper_id}")
async def update_wp(working_paper_id: str, body: sch.WorkingPaperUpdate, request: Request, current=Depends(get_current_user)):
    p = await db.ca_working_papers.find_one({"id": working_paper_id}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Working paper not found")
    await _assert_engagement_scope_for_doc(p, current=current, request=request, not_found_detail="Working paper not found")
    dump = body.model_dump(exclude_unset=True)
    refs = dump.pop("references", "__unset__")
    patch = {k: v for k, v in dump.items() if v is not None}
    if refs != "__unset__":
        patch["references"] = [dict(r) for r in (refs or [])]
    patch["updated_at"] = _now()
    await db.ca_working_papers.update_one({"id": working_paper_id}, {"$set": patch})
    return await db.ca_working_papers.find_one({"id": working_paper_id}, {"_id": 0})


@router.post("/working-papers/{working_paper_id}/evidence")
async def attach_wp_evidence(working_paper_id: str, body: sch.AuditEvidenceIn, request: Request, current=Depends(get_current_user)):
    wp = await db.ca_working_papers.find_one({"id": working_paper_id}, {"_id": 0})
    if not wp:
        raise HTTPException(404, "Working paper not found")
    await _assert_engagement_scope_for_doc(wp, current=current, request=request, not_found_detail="Working paper not found")
    eid = wp.get("engagement_id")
    doc = {
        "id": str(uuid.uuid4()),
        "working_paper_id": working_paper_id,
        "engagement_id": eid,
        "label": body.label,
        "reference": body.reference,
        "ref_type": body.ref_type,
        "uploaded_by": current.get("email"),
        "created_at": _now(),
    }
    await db.ca_audit_evidence.insert_one(dict(doc))
    await db.ca_working_papers.update_one({"id": working_paper_id}, {"$set": {"updated_at": _now()}})
    return doc


@router.get("/working-papers/{working_paper_id}/evidence")
async def list_wp_evidence(working_paper_id: str, request: Request, current=Depends(get_current_user)):
    wp = await db.ca_working_papers.find_one({"id": working_paper_id}, {"_id": 0})
    if not wp:
        raise HTTPException(404, "Working paper not found")
    await _assert_engagement_scope_for_doc(wp, current=current, request=request, not_found_detail="Working paper not found")
    cur = db.ca_audit_evidence.find({"working_paper_id": working_paper_id}, {"_id": 0}).sort("created_at", -1).limit(200)
    return {"items": await cur.to_list(length=200)}


@router.post("/sampling-plans")
async def create_sampling(request: Request, body: sch.SamplingPlanCreate, current=Depends(get_current_user)):
    await _engagement_or_404(body.engagement_id, current=current, request=request)
    doc = {"id": str(uuid.uuid4()), **body.model_dump(), "created_at": _now()}
    await db.ca_sampling_plans.insert_one(dict(doc))
    return doc


@router.get("/sampling-plans/{sampling_plan_id}/samples")
async def list_plan_samples(sampling_plan_id: str, request: Request, current=Depends(get_current_user)):
    sp = await db.ca_sampling_plans.find_one({"id": sampling_plan_id}, {"_id": 0})
    if not sp:
        raise HTTPException(404, "Sampling plan not found")
    await _assert_engagement_scope_for_doc(sp, current=current, request=request, not_found_detail="Sampling plan not found")
    cur = db.ca_sample_transactions.find({"sampling_plan_id": sampling_plan_id}, {"_id": 0}).sort("idx", 1).limit(5000)
    return {"items": await cur.to_list(length=5000)}


@router.post("/sampling-plans/{sampling_plan_id}/generate")
async def generate_samples(sampling_plan_id: str, request: Request, current=Depends(get_current_user)):
    sp = await db.ca_sampling_plans.find_one({"id": sampling_plan_id}, {"_id": 0})
    if not sp:
        raise HTTPException(404, "Sampling plan not found")
    await _assert_engagement_scope_for_doc(sp, current=current, request=request, not_found_detail="Sampling plan not found")
    await db.ca_sample_transactions.delete_many({"sampling_plan_id": sampling_plan_id})
    samples = wp_svc.sample_rows_for_plan(dict(sp))
    if samples:
        await db.ca_sample_transactions.insert_many(samples)
    await db.ca_sampling_plans.update_one(
        {"id": sampling_plan_id},
        {"$set": {"generated_at": _now(), "last_sample_count": len(samples)}},
    )
    return {"samples": samples, "plan_id": sampling_plan_id}


@router.post("/vouching-items")
async def create_vouch(request: Request, body: sch.VouchingItemCreate, current=Depends(get_current_user)):
    await _engagement_or_404(body.engagement_id, current=current, request=request)
    doc = {"id": str(uuid.uuid4()), **body.model_dump(), "created_at": _now()}
    await db.ca_vouching_items.insert_one(dict(doc))
    return doc


@router.put("/vouching-items/{vouching_item_id}")
async def update_vouch(vouching_item_id: str, body: sch.VouchingItemUpdate, request: Request, current=Depends(get_current_user)):
    v0 = await db.ca_vouching_items.find_one({"id": vouching_item_id}, {"_id": 0})
    if not v0:
        raise HTTPException(404, "Vouching item not found")
    await _assert_engagement_scope_for_doc(v0, current=current, request=request, not_found_detail="Vouching item not found")
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if patch:
        patch["updated_at"] = _now()
        await db.ca_vouching_items.update_one({"id": vouching_item_id}, {"$set": patch})
    return await db.ca_vouching_items.find_one({"id": vouching_item_id}, {"_id": 0})


@router.post("/working-papers/{working_paper_id}/review-notes")
async def wp_review_note(working_paper_id: str, body: sch.ReviewNoteIn, request: Request, current=Depends(get_current_user)):
    wp = await db.ca_working_papers.find_one({"id": working_paper_id}, {"_id": 0})
    if not wp:
        raise HTTPException(404, "Working paper not found")
    await _assert_engagement_scope_for_doc(wp, current=current, request=request, not_found_detail="Working paper not found")
    doc = {"id": str(uuid.uuid4()), "working_paper_id": working_paper_id, **body.model_dump(), "created_at": _now()}
    await db.ca_wp_review_notes.insert_one(dict(doc))
    await db.ca_working_papers.update_one({"id": working_paper_id}, {"$set": {"updated_at": _now()}})
    return doc


@router.post("/working-papers/{working_paper_id}/sign-off")
async def wp_signoff(working_paper_id: str, body: sch.SignOffIn, request: Request, current=Depends(get_current_user)):
    wp = await db.ca_working_papers.find_one({"id": working_paper_id}, {"_id": 0})
    if not wp:
        raise HTTPException(404, "Working paper not found")
    await _assert_engagement_scope_for_doc(wp, current=current, request=request, not_found_detail="Working paper not found")
    doc = {"id": str(uuid.uuid4()), "working_paper_id": working_paper_id, **body.model_dump(), "signed_at": _now()}
    await db.ca_wp_signoffs.insert_one(dict(doc))
    wp_patch: Dict[str, Any] = {"updated_at": _now()}
    if body.role == "preparer":
        wp_patch["prepared_by"] = body.signer_email
    elif body.role == "reviewer":
        wp_patch["reviewed_by"] = body.signer_email
    elif body.role == "partner":
        wp_patch["approved_by"] = body.signer_email
    await db.ca_working_papers.update_one({"id": working_paper_id}, {"$set": wp_patch})
    return await db.ca_working_papers.find_one({"id": working_paper_id}, {"_id": 0})


# ----- India compliance (library + checklists) -----
@router.get("/compliance/library")
async def compliance_library(
    entity_code: Optional[str] = Query(None, description="Legal entity key; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    laws = ind_ce.compliance_laws_catalog()
    return {
        "entity_code": eff,
        "laws": laws,
        "modules": [
            {"code": "CA2013", "label": "Companies Act 2013 checklist"},
            {"code": "44AB", "label": "Tax Audit u/s 44AB (Form 3CD)"},
            {"code": "GST", "label": "GST reconciliation"},
            {"code": "TDS", "label": "TDS/TCS reconciliation"},
            {"code": "CARO", "label": "CARO 2020 reporting"},
        ],
    }


@router.post("/audit-engagements/{engagement_id}/compliance/checklist")
async def create_compliance_checklist(request: Request, engagement_id: str, body: sch.ComplianceChecklistCreate, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    laws = body.law_codes or ["CA2013", "IT1961", "GST", "TDS", "CARO", "44AB"]
    reqs = compliance_rows_for_laws(laws)
    now = _now()
    doc = {"id": str(uuid.uuid4()), "engagement_id": engagement_id, "requirements": reqs, "created_at": now, "updated_at": now}
    await db.ca_compliance_results.replace_one({"engagement_id": engagement_id}, dict(doc), upsert=True)
    return doc


@router.get("/audit-engagements/{engagement_id}/compliance/export")
async def export_compliance_checklist(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    doc = await db.ca_compliance_results.find_one({"engagement_id": engagement_id}, {"_id": 0})
    reqs = (doc or {}).get("requirements") or []
    csv_body = ind_ce.compliance_requirements_to_csv_rows(reqs)
    filename = f"compliance-checklist-{engagement_id}.csv"
    return StreamingResponse(
        iter([csv_body]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/audit-engagements/{engagement_id}/compliance/findings")
async def create_compliance_finding(request: Request, engagement_id: str, body: sch.ComplianceFindingIn, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    doc = {
        "id": str(uuid.uuid4()),
        "engagement_id": engagement_id,
        "requirement_id": body.requirement_id,
        "law_code": body.law_code,
        "title": body.title,
        "severity": body.severity,
        "notes": body.notes,
        "created_by": current.get("email"),
        "created_at": _now(),
    }
    await db.ca_compliance_findings.insert_one(dict(doc))
    return doc


@router.get("/audit-engagements/{engagement_id}/compliance/findings")
async def list_compliance_findings(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    cur = db.ca_compliance_findings.find({"engagement_id": engagement_id}, {"_id": 0}).sort("created_at", -1).limit(500)
    return {"items": await cur.to_list(length=500)}


@router.post("/audit-engagements/{engagement_id}/compliance/result")
async def compliance_update_result(request: Request, engagement_id: str, body: sch.ComplianceResultUpdate, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    doc = await db.ca_compliance_results.find_one({"engagement_id": engagement_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Compliance checklist not found — create checklist first")
    reqs = doc.get("requirements") or []
    updated = False
    for r in reqs:
        if r.get("id") == body.requirement_id:
            r["status"] = body.status
            if body.evidence_uri:
                r["evidence_uri"] = body.evidence_uri
            if body.notes:
                r["notes"] = body.notes
            updated = True
            if body.status == "non-compliant":
                fake_ex = {
                    "id": str(uuid.uuid4()),
                    "control_id": "CA-COMP",
                    "control_code": "CA-COMP",
                    "control_name": "Regulatory compliance",
                    "process": "Tax",
                    "entity": "IN-SVC",
                    "severity": "high",
                    "status": "open",
                    "materiality_score": 0.7,
                    "anomaly_score": 0.5,
                    "financial_exposure": 0.0,
                    "source_record_type": "compliance",
                    "source_record_id": body.requirement_id,
                    "detected_at": _now(),
                    "title": f"Non-compliance · {r.get('title')}",
                    "summary": body.notes or "Non-compliant statutory requirement",
                    "engagement_id": engagement_id,
                }
                await db.exceptions.insert_one(dict(fake_ex))
                case = csvc.case_from_exception(fake_ex, current["email"], None)
                case["engagement_id"] = engagement_id
                await db.cases.insert_one(dict(case))
            break
    if not updated:
        raise HTTPException(404, "Requirement not found")
    await db.ca_compliance_results.update_one({"engagement_id": engagement_id}, {"$set": {"requirements": reqs, "updated_at": _now()}})
    return {"requirements": reqs}


@router.get("/audit-engagements/{engagement_id}/compliance/status")
async def compliance_status(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    doc = await db.ca_compliance_results.find_one({"engagement_id": engagement_id}, {"_id": 0})
    findings_n = await db.ca_compliance_findings.count_documents({"engagement_id": engagement_id})
    gst_cur = db.ca_gst_rec.find({"engagement_id": engagement_id}, {"_id": 0}).sort("at", -1).limit(1)
    tds_cur = db.ca_tds_rec.find({"engagement_id": engagement_id}, {"_id": 0}).sort("at", -1).limit(1)
    gst_latest = await gst_cur.to_list(1)
    tds_latest = await tds_cur.to_list(1)
    if not doc:
        return {
            "requirements": [],
            "summary": {"total": 0, "compliant": 0, "non_compliant": 0, "pending_evidence": 0, "not_applicable": 0},
            "findings_count": findings_n,
            "gst_latest": gst_latest[0] if gst_latest else None,
            "tds_latest": tds_latest[0] if tds_latest else None,
        }
    reqs = doc.get("requirements") or []
    summary = {
        "total": len(reqs),
        "compliant": sum(1 for r in reqs if r.get("status") == "compliant"),
        "non_compliant": sum(1 for r in reqs if r.get("status") == "non-compliant"),
        "pending_evidence": sum(1 for r in reqs if r.get("status") == "pending evidence"),
        "not_applicable": sum(1 for r in reqs if r.get("status") == "not applicable"),
    }
    return {
        "requirements": reqs,
        "summary": summary,
        "findings_count": findings_n,
        "gst_latest": gst_latest[0] if gst_latest else None,
        "tds_latest": tds_latest[0] if tds_latest else None,
    }


def _gst_doc(engagement_id: str, body: sch.GstReconciliationIn) -> Dict[str, Any]:
    raw = body.model_dump()
    checks = ind_ce.compute_gst_checks(raw)
    return {"id": str(uuid.uuid4()), "engagement_id": engagement_id, "checks": checks, "raw": raw, "at": _now()}


@router.post("/audit-engagements/{engagement_id}/gst/reconciliation")
async def gst_rec(request: Request, engagement_id: str, body: sch.GstReconciliationIn, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    doc = _gst_doc(engagement_id, body)
    await db.ca_gst_rec.insert_one(dict(doc))
    return doc


@router.post("/gst/reconciliation")
async def gst_reconciliation_root(request: Request, body: sch.GstReconciliationWithEngagement, current=Depends(get_current_user)):
    """Top-level alias: same as POST /audit-engagements/{id}/gst/reconciliation (engagement_id in body)."""
    await _engagement_or_404(body.engagement_id, current=current, request=request)
    inner = sch.GstReconciliationIn(**body.model_dump(exclude={"engagement_id"}))
    doc = _gst_doc(body.engagement_id, inner)
    await db.ca_gst_rec.insert_one(dict(doc))
    return doc


@router.get("/audit-engagements/{engagement_id}/gst/reconciliation")
async def list_gst_reconciliations(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    cur = db.ca_gst_rec.find({"engagement_id": engagement_id}, {"_id": 0}).sort("at", -1).limit(50)
    return {"items": await cur.to_list(length=50)}


def _tds_doc(engagement_id: str, body: sch.TdsReconciliationIn) -> Dict[str, Any]:
    raw = body.model_dump()
    checks = ind_ce.compute_tds_checks(raw)
    return {"id": str(uuid.uuid4()), "engagement_id": engagement_id, "checks": checks, "raw": raw, "at": _now()}


@router.post("/audit-engagements/{engagement_id}/tds/reconciliation")
async def tds_rec(request: Request, engagement_id: str, body: sch.TdsReconciliationIn, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    doc = _tds_doc(engagement_id, body)
    await db.ca_tds_rec.insert_one(dict(doc))
    return doc


@router.post("/tds/reconciliation")
async def tds_reconciliation_root(request: Request, body: sch.TdsReconciliationWithEngagement, current=Depends(get_current_user)):
    await _engagement_or_404(body.engagement_id, current=current, request=request)
    inner = sch.TdsReconciliationIn(**body.model_dump(exclude={"engagement_id"}))
    doc = _tds_doc(body.engagement_id, inner)
    await db.ca_tds_rec.insert_one(dict(doc))
    return doc


@router.get("/audit-engagements/{engagement_id}/tds/reconciliation")
async def list_tds_reconciliations(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    cur = db.ca_tds_rec.find({"engagement_id": engagement_id}, {"_id": 0}).sort("at", -1).limit(50)
    return {"items": await cur.to_list(length=50)}


@router.post("/audit-engagements/{engagement_id}/caro/checklist")
async def caro_checklist(request: Request, engagement_id: str, body: sch.CaroChecklistIn, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    clauses = body.clause_ids or ["3(i)", "3(ii)", "3(iii)"]
    doc = {
        "engagement_id": engagement_id,
        "caro_clauses": [{"id": c, "status": "pending evidence", "evidence_uri": None, "notes": None} for c in clauses],
        "at": _now(),
    }
    await db.ca_caro_state.update_one({"engagement_id": engagement_id}, {"$set": doc}, upsert=True)
    return doc


@router.post("/caro/checklist")
async def caro_checklist_root(
    request: Request, body: sch.CaroChecklistWithEngagement, current=Depends(get_current_user)
):
    return await caro_checklist(
        request, body.engagement_id, sch.CaroChecklistIn(clause_ids=body.clause_ids), current
    )


@router.get("/audit-engagements/{engagement_id}/caro/state")
async def get_caro_state(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    st = await db.ca_caro_state.find_one({"engagement_id": engagement_id}, {"_id": 0})
    return st or {"engagement_id": engagement_id, "caro_clauses": []}


@router.post("/audit-engagements/{engagement_id}/caro/clause")
async def update_caro_clause(request: Request, engagement_id: str, body: sch.CaroClauseUpdate, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    st = await db.ca_caro_state.find_one({"engagement_id": engagement_id}, {"_id": 0})
    if not st:
        raise HTTPException(404, "CARO checklist not found — create checklist first")
    clauses = list(st.get("caro_clauses") or [])
    for c in clauses:
        if c.get("id") == body.clause_id:
            c["status"] = body.status
            if body.evidence_uri is not None:
                c["evidence_uri"] = body.evidence_uri
            if body.notes is not None:
                c["notes"] = body.notes
            break
    else:
        raise HTTPException(404, "Clause not found")
    await db.ca_caro_state.update_one({"engagement_id": engagement_id}, {"$set": {"caro_clauses": clauses, "at": _now()}})
    return {"caro_clauses": clauses}


@router.post("/audit-engagements/{engagement_id}/tax-audit-44ab/checklist")
async def tax44_checklist(request: Request, engagement_id: str, body: sch.TaxAudit44abIn, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    clauses = body.clause_ids or ["10A", "10B"]
    doc = {
        "engagement_id": engagement_id,
        "clauses": [{"id": c, "status": "pending evidence", "evidence_uri": None, "notes": None} for c in clauses],
        "at": _now(),
    }
    await db.ca_tax44_state.update_one({"engagement_id": engagement_id}, {"$set": doc}, upsert=True)
    return doc


@router.get("/audit-engagements/{engagement_id}/tax-audit-44ab/state")
async def get_tax44_state(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    st = await db.ca_tax44_state.find_one({"engagement_id": engagement_id}, {"_id": 0})
    return st or {"engagement_id": engagement_id, "clauses": []}


@router.post("/audit-engagements/{engagement_id}/tax-audit-44ab/clause")
async def update_tax44_clause(request: Request, engagement_id: str, body: sch.Tax44ClauseUpdate, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    st = await db.ca_tax44_state.find_one({"engagement_id": engagement_id}, {"_id": 0})
    if not st:
        raise HTTPException(404, "44AB checklist not found — create checklist first")
    clauses = list(st.get("clauses") or [])
    for c in clauses:
        if c.get("id") == body.clause_id:
            c["status"] = body.status
            if body.evidence_uri is not None:
                c["evidence_uri"] = body.evidence_uri
            if body.notes is not None:
                c["notes"] = body.notes
            break
    else:
        raise HTTPException(404, "Clause not found")
    await db.ca_tax44_state.update_one({"engagement_id": engagement_id}, {"$set": {"clauses": clauses, "at": _now()}})
    return {"clauses": clauses}


@router.get("/audit-engagements/{engagement_id}/compliance-calendar")
async def compliance_calendar(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    base = datetime.now(timezone.utc)
    events = [
        {"title": "CARO sign-off", "due": iso(base + timedelta(days=14))},
        {"title": "Tax audit filing", "due": iso(base + timedelta(days=30))},
        {"title": "GST annual return", "due": iso(base + timedelta(days=45))},
    ]
    filings = ind_ce.default_filing_due_dates()
    return {"events": events, "filings": filings}


# ----- Reporting -----
@router.post("/audit-engagements/{engagement_id}/observations")
async def create_observation(request: Request, engagement_id: str, body: sch.AuditObservationCreate, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    doc = {"id": str(uuid.uuid4()), "engagement_id": engagement_id, **body.model_dump(), "resolved": False, "created_at": _now()}
    await db.ca_audit_observations.insert_one(dict(doc))
    return doc


@router.put("/audit-engagements/{engagement_id}/observations/{observation_id}")
async def update_observation(
    request: Request,
    engagement_id: str, observation_id: str, body: sch.AuditObservationUpdate, current=Depends(get_current_user)
):
    await _engagement_or_404(engagement_id, current=current, request=request)
    patch = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if not patch:
        row = await db.ca_audit_observations.find_one({"id": observation_id, "engagement_id": engagement_id}, {"_id": 0})
        if not row:
            raise HTTPException(404, "Observation not found")
        return row
    patch["updated_at"] = _now()
    res = await db.ca_audit_observations.update_one(
        {"id": observation_id, "engagement_id": engagement_id}, {"$set": patch}
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Observation not found")
    return await db.ca_audit_observations.find_one({"id": observation_id}, {"_id": 0})


@router.get("/audit-engagements/{engagement_id}/observations")
async def list_observations(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    return [o async for o in db.ca_audit_observations.find({"engagement_id": engagement_id}, {"_id": 0})]


@router.post("/audit-engagements/{engagement_id}/audit-findings")
async def create_audit_finding(request: Request, engagement_id: str, body: sch.AuditFindingIn, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    doc = {
        "id": str(uuid.uuid4()),
        "engagement_id": engagement_id,
        **body.model_dump(),
        "created_at": _now(),
        "created_by": current.get("email"),
    }
    await db.ca_audit_findings.insert_one(dict(doc))
    return doc


@router.get("/audit-engagements/{engagement_id}/audit-findings")
async def list_audit_findings(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    cur = db.ca_audit_findings.find({"engagement_id": engagement_id}, {"_id": 0}).sort("created_at", -1).limit(200)
    return {"items": await cur.to_list(length=200)}


@router.post("/audit-engagements/{engagement_id}/opinion/generate")
async def gen_opinion(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    eng = await db.audit_engagements.find_one({"engagement_id": engagement_id}, {"_id": 0})
    obs = [o async for o in db.ca_audit_observations.find({"engagement_id": engagement_id}, {"_id": 0})]
    signals = await rpt_eng.gather_opinion_signals(db, engagement_id)
    rec = rpt_eng.recommend_opinion(obs, signals)
    doc = {
        "id": str(uuid.uuid4()),
        "engagement_id": engagement_id,
        **rec,
        "generated_at": _now(),
        "inputs_snapshot": {"entity": (eng or {}).get("entity_name"), "signals": rec.get("signals_summary"), "counts": rec.get("counts")},
    }
    await db.ca_audit_opinions.insert_one(dict(doc))
    return doc


@router.get("/audit-engagements/{engagement_id}/opinion")
async def get_opinion(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    cur = db.ca_audit_opinions.find({"engagement_id": engagement_id}, {"_id": 0}).sort("generated_at", -1).limit(1)
    docs = await cur.to_list(1)
    return docs[0] if docs else None


@router.post("/audit-engagements/{engagement_id}/caro/generate")
async def gen_caro(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    st = await db.ca_caro_state.find_one({"engagement_id": engagement_id}, {"_id": 0}) or {}
    clauses = st.get("caro_clauses") or [{"id": "3(i)", "status": "pending evidence"}]
    responses = [
        {
            "clause_id": c["id"],
            "response": "Based on audit procedures performed, no material misstatement noted (draft narrative).",
            "status": c.get("status"),
        }
        for c in clauses
    ]
    await db.ca_caro_responses.replace_one(
        {"engagement_id": engagement_id},
        {"engagement_id": engagement_id, "responses": responses, "at": _now()},
        upsert=True,
    )
    return {"responses": responses}


@router.get("/audit-engagements/{engagement_id}/caro/responses")
async def get_caro_responses(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    row = await db.ca_caro_responses.find_one({"engagement_id": engagement_id}, {"_id": 0})
    return row or {"engagement_id": engagement_id, "responses": []}


@router.post("/audit-engagements/{engagement_id}/report/generate")
async def gen_report(request: Request, engagement_id: str, current=Depends(get_current_user)):
    eng = await _engagement_or_404(engagement_id, current=current, request=request)
    opinion = await db.ca_audit_opinions.find_one({"engagement_id": engagement_id}, {"_id": 0}, sort=[("generated_at", -1)])
    obs = [o async for o in db.ca_audit_observations.find({"engagement_id": engagement_id}, {"_id": 0})]
    caro = await db.ca_caro_responses.find_one({"engagement_id": engagement_id}, {"_id": 0})
    signals = await rpt_eng.gather_opinion_signals(db, engagement_id)
    sections = rpt_eng.build_report_sections(eng, opinion, obs, caro, signals)
    now = _now()
    doc = {
        "id": str(uuid.uuid4()),
        "engagement_id": engagement_id,
        "sections": sections,
        "approval_status": "draft",
        "status": "draft",
        "created_at": now,
        "updated_at": now,
    }
    await db.ca_final_reports.insert_one(dict(doc))
    return doc


@router.get("/audit-engagements/{engagement_id}/report")
async def get_report(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    cur = db.ca_final_reports.find({"engagement_id": engagement_id}, {"_id": 0}).sort("created_at", -1).limit(1)
    docs = await cur.to_list(1)
    return docs[0] if docs else None


@router.patch("/audit-engagements/{engagement_id}/report/status")
async def patch_report_status(request: Request, engagement_id: str, body: sch.FinalReportStatusIn, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    rep = await db.ca_final_reports.find_one({"engagement_id": engagement_id}, {"_id": 0}, sort=[("created_at", -1)])
    if not rep:
        raise HTTPException(404, "No report — generate a draft first")
    st = body.status
    await db.ca_final_reports.update_one(
        {"id": rep["id"]},
        {"$set": {"approval_status": st, "status": st, "updated_at": _now()}},
    )
    return await db.ca_final_reports.find_one({"id": rep["id"]}, {"_id": 0})


@router.get("/audit-engagements/{engagement_id}/report/export")
async def export_report(
    request: Request,
    engagement_id: str,
    format: str = Query("pdf", description="pdf | docx | xlsx | observations-xlsx"),
    current=Depends(get_current_user),
):
    await _engagement_or_404(engagement_id, current=current, request=request)
    obs = [o async for o in db.ca_audit_observations.find({"engagement_id": engagement_id}, {"_id": 0})]
    rep = await db.ca_final_reports.find_one({"engagement_id": engagement_id}, {"_id": 0}, sort=[("created_at", -1)])
    sections = (rep or {}).get("sections") or {}

    if format == "observations-xlsx":
        data = rpt_eng.observations_to_xlsx_bytes(obs, engagement_id)
        name = f"observation-tracker-{engagement_id}.xlsx"
        return StreamingResponse(iter([data]), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="{name}"'})

    if not rep:
        raise HTTPException(404, "No report — generate a draft first")

    if format == "pdf":
        data = rpt_eng.report_sections_to_pdf_bytes(sections, engagement_id)
        name = f"audit-report-{engagement_id}.pdf"
        return StreamingResponse(iter([data]), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}"'})

    if format == "docx":
        data = rpt_eng.report_sections_to_docx_bytes(sections, engagement_id)
        name = f"audit-report-{engagement_id}.docx"
        return StreamingResponse(
            iter([data]),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    if format == "xlsx":
        from openpyxl import Workbook

        buf = io.BytesIO()
        wb = Workbook()
        ws = wb.active
        ws.title = "Sections"
        ws.append(["section", "content"])
        for k, v in sections.items():
            if isinstance(v, list):
                ws.append([k, "\n".join(str(x) for x in v)])
            else:
                ws.append([k, str(v)])
        wb.save(buf)
        raw = buf.getvalue()
        name = f"audit-report-sections-{engagement_id}.xlsx"
        return StreamingResponse(
            iter([raw]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    raise HTTPException(400, "Invalid format — use pdf, docx, xlsx, or observations-xlsx")


@router.post("/audit-engagements/{engagement_id}/management-letter/generate")
async def gen_mgmt_letter(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    obs = [o async for o in db.ca_audit_observations.find({"engagement_id": engagement_id}, {"_id": 0})]
    text = "Management letter (demo): address open observations and remediation timelines.\n" + "\n".join(f"- {o['title']}" for o in obs[:10])
    doc = {"id": str(uuid.uuid4()), "engagement_id": engagement_id, "text": text, "created_at": _now()}
    await db.ca_management_letters.insert_one(dict(doc))
    return doc


@router.post("/audit-engagements/{engagement_id}/management-representation")
async def mgmt_repr(request: Request, engagement_id: str, body: sch.ManagementRepresentationIn, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    doc = {"id": str(uuid.uuid4()), "engagement_id": engagement_id, **body.model_dump(), "at": _now()}
    await db.ca_mgmt_repr.insert_one(dict(doc))
    return doc


# ----- Aggregates (command center) -----
async def _cc_tiles_async(engagement_id: str) -> Dict[str, Any]:
    return {
        "risks": await db.ca_risks.count_documents({"engagement_id": engagement_id}),
        "open_cases": await db.cases.count_documents({"engagement_id": engagement_id, "status": {"$ne": "closed"}}),
        "wp": await db.ca_working_papers.count_documents({"engagement_id": engagement_id}),
        "compliance_reqs": len((await db.ca_compliance_results.find_one({"engagement_id": engagement_id}, {"_id": 0}) or {}).get("requirements") or []),
    }


@router.get("/audit-engagements/{engagement_id}/ca-command-center")
async def ca_command_center(request: Request, engagement_id: str, current=Depends(get_current_user)):
    eng = await _engagement_or_404(engagement_id, current=current, request=request)
    summary = await _cc_tiles_async(engagement_id)
    return {"engagement": eng, "tiles": summary}


@router.get("/audit-engagements/{engagement_id}/ca-dashboard")
async def ca_dashboard(request: Request, engagement_id: str, current=Depends(get_current_user)):
    """CA-grade consolidated dashboard: tiles, assurance scores, integration map, CFO advisory copy."""
    eng = await _engagement_or_404(engagement_id, current=current, request=request)
    scores = await _compute_continuous_assurance(engagement_id, eng)
    tiles = await _cc_tiles_async(engagement_id)
    integration = await eng_int.build_integration_map(db, engagement_id)
    risks = [r async for r in db.ca_risks.find({"engagement_id": engagement_id}, {"_id": 0}).limit(50)]
    cases = [c async for c in db.cases.find({"engagement_id": engagement_id, "status": {"$ne": "closed"}}, {"_id": 0}).limit(50)]
    defs = [d async for d in db.ca_control_deficiencies.find({"engagement_id": engagement_id}, {"_id": 0}).limit(50)]
    obs = [o async for o in db.ca_audit_observations.find({"engagement_id": engagement_id}, {"_id": 0}).limit(50)]
    comp_doc = await db.ca_compliance_results.find_one({"engagement_id": engagement_id}, {"_id": 0})
    reqs = (comp_doc or {}).get("requirements") or []
    mat = await db.ca_materiality.find_one({"engagement_id": engagement_id}, {"_id": 0})
    advisory = exec_adv.build_advisory_narratives(eng, risks, cases, defs, obs, reqs, mat)
    eenc = quote(engagement_id, safe="")
    workflow_steps = [
        {"phase": "Planning", "path": f"/app/audit-planning/engagements/{eenc}", "note": "Engagement hub · team · milestones"},
        {"phase": "Materiality", "path": f"/app/audit-planning/engagements/{eenc}?tab=materiality", "note": "Benchmarks & thresholds"},
        {"phase": "Risk & controls", "path": f"/app/audit-planning/engagements/{eenc}?tab=racm", "note": "RACM · IFC tests"},
        {"phase": "Financial audit", "path": f"/app/audit-planning/engagements/{eenc}/fs-audit", "note": "FS engine"},
        {"phase": "Compliance", "path": f"/app/audit-planning/engagements/{eenc}/india-compliance", "note": "India statutory"},
        {"phase": "Working papers", "path": f"/app/audit-planning/engagements/{eenc}/working-papers", "note": "WP · sampling · vouching"},
        {"phase": "Reporting", "path": f"/app/audit-planning/engagements/{eenc}/report-studio", "note": "Opinion & report"},
        {"phase": "CFO review", "path": "/app/executive-review", "note": "Executive summary & committee pack"},
    ]
    return {
        "engagement": eng,
        "tiles": tiles,
        "scores": scores,
        "integration": integration,
        "advisory": advisory,
        "workflow_steps": workflow_steps,
    }


@router.get("/audit-engagements/{engagement_id}/advisory-insights")
async def advisory_insights(request: Request, engagement_id: str, current=Depends(get_current_user)):
    eng = await _engagement_or_404(engagement_id, current=current, request=request)
    risks = [r async for r in db.ca_risks.find({"engagement_id": engagement_id}, {"_id": 0}).limit(80)]
    cases = [c async for c in db.cases.find({"engagement_id": engagement_id, "status": {"$ne": "closed"}}, {"_id": 0}).limit(80)]
    defs = [d async for d in db.ca_control_deficiencies.find({"engagement_id": engagement_id}, {"_id": 0}).limit(80)]
    obs = [o async for o in db.ca_audit_observations.find({"engagement_id": engagement_id}, {"_id": 0}).limit(80)]
    comp_doc = await db.ca_compliance_results.find_one({"engagement_id": engagement_id}, {"_id": 0})
    reqs = (comp_doc or {}).get("requirements") or []
    mat = await db.ca_materiality.find_one({"engagement_id": engagement_id}, {"_id": 0})
    return exec_adv.build_advisory_narratives(eng, risks, cases, defs, obs, reqs, mat)


@router.get("/audit-engagements/{engagement_id}/executive-summary")
async def executive_summary(request: Request, engagement_id: str, current=Depends(get_current_user)):
    eng = await _engagement_or_404(engagement_id, current=current, request=request)
    scores = await _compute_continuous_assurance(engagement_id, eng)
    integration = await eng_int.build_integration_map(db, engagement_id)
    risks = [r async for r in db.ca_risks.find({"engagement_id": engagement_id}, {"_id": 0}).limit(40)]
    cases = [c async for c in db.cases.find({"engagement_id": engagement_id, "status": {"$ne": "closed"}}, {"_id": 0}).limit(40)]
    defs = [d async for d in db.ca_control_deficiencies.find({"engagement_id": engagement_id}, {"_id": 0}).limit(40)]
    obs = [o async for o in db.ca_audit_observations.find({"engagement_id": engagement_id}, {"_id": 0}).limit(40)]
    comp_doc = await db.ca_compliance_results.find_one({"engagement_id": engagement_id}, {"_id": 0})
    reqs = (comp_doc or {}).get("requirements") or []
    mat = await db.ca_materiality.find_one({"engagement_id": engagement_id}, {"_id": 0})
    adv = exec_adv.build_advisory_narratives(eng, risks, cases, defs, obs, reqs, mat)
    return {
        "engagement_id": engagement_id,
        "headline": f"{eng.get('entity_name')} · FY {eng.get('financial_year')}",
        "scores": scores,
        "score_descriptions": {
            "audit_readiness_score": "Weighted view of risk, controls, compliance, evidence, and FS risk.",
            "control_effectiveness_score": "Derived from RACM control effectiveness ratings.",
            "compliance_score": "Share of compliant India checklist lines (or neutral default).",
            "evidence_completeness_score": "Heuristic from working paper volume / sign-off coverage.",
            "fraud_risk_score": "Inversely related to high-severity exceptions vs materiality.",
            "financial_statement_risk_score": "FS validation and compliance pressure.",
            "continuous_assurance_score": "Overall index for committee dashboards.",
        },
        "integration_summary": {"counts": integration.get("counts"), "narrative": integration.get("narrative")},
        "advisory_preview": {
            "lead_risk": (adv.get("key_risks_summary") or [None])[0],
            "cfo_finding": (adv.get("findings_cfo_language") or [None])[0],
        },
    }


@router.get("/audit-engagements/{engagement_id}/audit-committee-pack")
async def audit_committee_pack(request: Request, engagement_id: str, current=Depends(get_current_user)):
    eng = await _engagement_or_404(engagement_id, current=current, request=request)
    rep = await db.ca_final_reports.find_one({"engagement_id": engagement_id}, {"_id": 0}, sort=[("created_at", -1)])
    risks = [r async for r in db.ca_risks.find({"engagement_id": engagement_id, "risk_rating": {"$in": ["high", "critical"]}}, {"_id": 0}).limit(20)]
    cases = [c async for c in db.cases.find({"engagement_id": engagement_id}, {"_id": 0}).limit(20)]
    scores = await _compute_continuous_assurance(engagement_id, eng)
    comp = await db.ca_compliance_results.find_one({"engagement_id": engagement_id}, {"_id": 0})
    reqs = (comp or {}).get("requirements") or []
    comp_stats = {
        "total": len(reqs),
        "compliant": sum(1 for r in reqs if r.get("status") == "compliant"),
        "non_compliant": sum(1 for r in reqs if r.get("status") == "non-compliant"),
        "pending_evidence": sum(1 for r in reqs if r.get("status") == "pending evidence"),
    }
    obs = [o async for o in db.ca_audit_observations.find({"engagement_id": engagement_id}, {"_id": 0}).limit(30)]
    defs = [d async for d in db.ca_control_deficiencies.find({"engagement_id": engagement_id}, {"_id": 0}).limit(20)]
    mat = await db.ca_materiality.find_one({"engagement_id": engagement_id}, {"_id": 0})
    open_cases_only = [c for c in cases if c.get("status") != "closed"]
    adv = exec_adv.build_advisory_narratives(eng, risks, open_cases_only, defs, obs, reqs, mat)
    return {
        "engagement": eng,
        "top_risks": risks,
        "open_cases": cases,
        "latest_report": rep,
        "continuous_assurance": scores,
        "compliance_snapshot": comp_stats,
        "advisory": {"key_risks_summary": adv.get("key_risks_summary", [])[:5], "control_improvements": adv.get("control_improvements", [])[:5]},
        "materiality_snapshot": {"final_materiality": (mat or {}).get("final_materiality"), "performance": (mat or {}).get("performance_materiality")},
    }


@router.get("/audit-engagements/{engagement_id}/continuous-assurance-score")
async def continuous_assurance_score(request: Request, engagement_id: str, current=Depends(get_current_user)):
    eng = await _engagement_or_404(engagement_id, current=current, request=request)
    scores = await _compute_continuous_assurance(engagement_id, eng)
    return {
        **scores,
        "components": {
            "audit_readiness_score": scores.get("audit_readiness_score"),
            "control_effectiveness_score": scores.get("control_effectiveness_score"),
            "compliance_score": scores.get("compliance_score"),
            "evidence_completeness_score": scores.get("evidence_completeness_score"),
            "fraud_risk_score": scores.get("fraud_risk_score"),
            "financial_statement_risk_score": scores.get("financial_statement_risk_score"),
        },
    }


@router.get("/audit-engagements/{engagement_id}/management-action-summary")
async def mgmt_actions(request: Request, engagement_id: str, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    cases = [c async for c in db.cases.find({"engagement_id": engagement_id, "status": {"$ne": "closed"}}, {"_id": 0}).limit(100)]
    defs = [d async for d in db.ca_control_deficiencies.find({"engagement_id": engagement_id}, {"_id": 0}).limit(100)]
    return {"open_cases": cases, "deficiencies": defs}
