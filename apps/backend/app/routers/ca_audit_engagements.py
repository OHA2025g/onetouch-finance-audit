"""Audit engagement CRUD, milestones, team, planning notes, engagement summary."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.requests import Request

from app.auth import get_current_user
from app.core.entity_scope import entity_scope_enforced
from app.deps import audit_log, db, iso
from app.schemas import ca_audit as sch
from app.services.rbac_service import assert_engagement_entity_scope, enforce_entity_scope
from app.routers import ca_audit_modules as cam
from app.services import ca_executive_review_service as ca_exec_rev

router = APIRouter(tags=["ca-audit"])

_ACTIVE_STATUSES = frozenset({"draft", "planned", "in-progress", "in_progress"})
_TERMINAL_STATUSES = frozenset({"completed", "archived"})


async def _engagement_or_404(
    engagement_id: str,
    *,
    current: dict,
    request: Optional[Request] = None,
) -> Dict[str, Any]:
    """Load engagement and apply the same entity query + engagement RBAC as ``ca_audit_modules``."""
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


def _now() -> str:
    return iso(datetime.now(timezone.utc))


def _normalize_status(st: Optional[str]) -> str:
    if st == "in_progress":
        return "in-progress"
    return st or "draft"


def _normalize_engagement_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(doc)
    out["status"] = _normalize_status(out.get("status"))
    return out


def _parse_iso_dt(value: Optional[str]) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        s = value.strip().replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


@router.post("/audit-engagements")
async def create_engagement(body: sch.AuditEngagementCreate, current=Depends(get_current_user)):
    exists = await db.audit_engagements.find_one({"engagement_id": body.engagement_id}, {"_id": 0, "id": 1})
    if exists:
        raise HTTPException(409, "engagement_id already exists")
    req_code = (body.entity_code or "").strip() or None
    req_name = (body.entity_name or "").strip() or None
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=req_code or req_name or None)
    entity_code_stored = eff if eff else (req_code or None)
    doc_id = str(uuid.uuid4())
    milestones: List[Dict[str, Any]] = []
    team_members: List[Dict[str, Any]] = []
    for email in body.assigned_team:
        team_members.append(
            {
                "id": str(uuid.uuid4()),
                "user_email": email,
                "role": "staff",
                "allocation_pct": 100.0,
                "added_at": _now(),
            }
        )
    if body.objectives:
        detailed_objectives = [
            {"id": o.id or str(uuid.uuid4()), "title": o.title, "description": o.description or ""} for o in body.objectives
        ]
    else:
        detailed_objectives = [
            {"id": str(uuid.uuid4()), "title": t, "description": ""} for t in (body.audit_objectives or [])
        ]
    detailed_scopes = [s.model_dump() | {"id": s.id or str(uuid.uuid4())} for s in (body.scopes or [])]
    doc: Dict[str, Any] = {
        "id": doc_id,
        "engagement_id": body.engagement_id,
        "entity_code": entity_code_stored,
        "entity_name": body.entity_name,
        "financial_year": body.financial_year,
        "audit_type": body.audit_type,
        "audit_scope": body.audit_scope,
        "audit_objectives": body.audit_objectives
        or ([o.title for o in body.objectives] if body.objectives else []),
        "start_date": body.start_date,
        "end_date": body.end_date,
        "audit_partner": body.audit_partner,
        "audit_manager": body.audit_manager,
        "assigned_team": body.assigned_team,
        "status": body.status,
        "risk_level": body.risk_level,
        "created_by": current["email"],
        "created_at": _now(),
        "updated_at": _now(),
        "milestones": milestones,
        "team_members": team_members,
        "planning_notes": [],
        "detailed_scopes": detailed_scopes,
        "detailed_objectives": detailed_objectives,
        "timeline": body.timeline.model_dump() if body.timeline else {},
    }
    await db.audit_engagements.insert_one(dict(doc))
    await audit_log(current["email"], "create_engagement", "audit_engagement", body.engagement_id, {})
    return _normalize_engagement_doc(doc)


@router.get("/audit-engagements")
async def list_engagements(
    status: Optional[str] = None,
    audit_type: Optional[str] = None,
    limit: int = 200,
    entity_code: Optional[str] = Query(None, description="Optional legal entity hint; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    q: Dict[str, Any] = {}
    if status:
        if status in ("in-progress", "in_progress"):
            q["status"] = {"$in": ["in-progress", "in_progress"]}
        else:
            q["status"] = status
    if audit_type:
        q["audit_type"] = audit_type
    if await entity_scope_enforced(db) and current.get("role") != "Super Admin":
        user = await db.users.find_one({"id": current.get("user_id")}, {"_id": 0, "entity": 1})
        ue = (user or {}).get("entity")
        if ue:
            q["entity_code"] = ue
    rows = [d async for d in db.audit_engagements.find(q, {"_id": 0}).sort("updated_at", -1).limit(limit)]
    return [_normalize_engagement_doc(d) for d in rows]


@router.get("/audit-engagements/planning-metrics", response_model=sch.AuditEngagementPlanningMetrics)
async def planning_metrics(
    entity_code: Optional[str] = Query(None, description="Optional legal entity hint; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    """Aggregates for Audit Planning dashboard (must stay above `/{engagement_id}` routes)."""
    await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=14)
    eng_q: Dict[str, Any] = {}
    if await entity_scope_enforced(db) and current.get("role") != "Super Admin":
        user = await db.users.find_one({"id": current.get("user_id")}, {"_id": 0, "entity": 1})
        ue = (user or {}).get("entity")
        if ue:
            eng_q["entity_code"] = ue
    engagements = [d async for d in db.audit_engagements.find(eng_q, {"_id": 0})]
    active = 0
    high_risk: List[sch.PlanningMetricsEngagementBrief] = []
    overdue: List[sch.PlanningMetricsEngagementBrief] = []
    upcoming: List[sch.PlanningMetricsMilestone] = []

    for raw in engagements:
        e = _normalize_engagement_doc(raw)
        st = e.get("status") or "draft"
        if st in _ACTIVE_STATUSES:
            active += 1
        rl = (e.get("risk_level") or "").lower()
        if rl in ("high", "critical"):
            high_risk.append(
                sch.PlanningMetricsEngagementBrief(
                    engagement_id=e["engagement_id"],
                    entity_name=e.get("entity_name") or "",
                    end_date=e.get("end_date") or "",
                    status=st,
                    risk_level=e.get("risk_level") or "",
                )
            )
        end_dt = _parse_iso_dt(e.get("end_date"))
        if end_dt and end_dt < now and st not in _TERMINAL_STATUSES:
            overdue.append(
                sch.PlanningMetricsEngagementBrief(
                    engagement_id=e["engagement_id"],
                    entity_name=e.get("entity_name") or "",
                    end_date=e.get("end_date") or "",
                    status=st,
                    risk_level=e.get("risk_level") or "",
                )
            )
        for ms in e.get("milestones") or []:
            if not isinstance(ms, dict):
                continue
            if ms.get("status") == "done":
                continue
            due = _parse_iso_dt(ms.get("due_date"))
            if due and now <= due <= horizon:
                upcoming.append(
                    sch.PlanningMetricsMilestone(
                        engagement_id=e["engagement_id"],
                        entity_name=e.get("entity_name") or "",
                        milestone_id=ms.get("id") or "",
                        title=ms.get("title") or "",
                        due_date=ms.get("due_date") or "",
                        status=ms.get("status") or "pending",
                    )
                )

    upcoming.sort(key=lambda m: m.due_date)
    return sch.AuditEngagementPlanningMetrics(
        active_audit_count=active,
        upcoming_milestone_count=len(upcoming),
        overdue_engagement_count=len(overdue),
        high_risk_engagement_count=len(high_risk),
        upcoming_milestones=upcoming[:12],
        overdue_engagements=overdue[:20],
        high_risk_engagements=high_risk[:20],
    )


@router.get("/audit-engagements/executive-review-cross-org")
async def executive_review_cross_org(
    limit: int = Query(6, ge=1, le=20),
    pool: int = Query(40, ge=6, le=80),
    entity_code: Optional[str] = Query(None, description="Optional legal entity hint; enforced when RBAC entity scope is on."),
    current=Depends(get_current_user),
):
    """Portfolio slice for CFO hub: lowest continuous assurance & critical-case pressure first."""
    await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    eng_q: Dict[str, Any] = {}
    if await entity_scope_enforced(db) and current.get("role") != "Super Admin":
        user = await db.users.find_one({"id": current.get("user_id")}, {"_id": 0, "entity": 1})
        ue = (user or {}).get("entity")
        if ue:
            eng_q["entity_code"] = ue
    rows = [d async for d in db.audit_engagements.find(eng_q, {"_id": 0}).sort("updated_at", -1).limit(pool)]
    return await ca_exec_rev.cross_org_executive_summary(db, rows, cam._compute_continuous_assurance, limit)


@router.get("/audit-engagements/{engagement_id}")
async def get_engagement(request: Request, engagement_id: str, current=Depends(get_current_user)):
    return _normalize_engagement_doc(await _engagement_or_404(engagement_id, current=current, request=request))


@router.put("/audit-engagements/{engagement_id}")
async def update_engagement(request: Request, engagement_id: str, body: sch.AuditEngagementUpdate, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    data = body.model_dump(exclude_none=True)
    patch: Dict[str, Any] = {"updated_at": _now()}
    reserved = {"scopes", "objectives", "timeline", "entity_code"}
    for k, v in data.items():
        if k in reserved:
            continue
        patch[k] = v
    if "entity_code" in data and data.get("entity_code") is not None:
        ec_in = (str(data["entity_code"])).strip() or None
        patch["entity_code"] = await enforce_entity_scope(db, current=current, requested_entity_code=ec_in)
    if "timeline" in data:
        tl = data["timeline"]
        patch["timeline"] = tl if isinstance(tl, dict) else (tl.model_dump() if hasattr(tl, "model_dump") else tl)
    if "scopes" in data and data["scopes"] is not None:
        patch["detailed_scopes"] = []
        for s in data["scopes"]:
            row = dict(s) if isinstance(s, dict) else s.model_dump()
            row["id"] = row.get("id") or str(uuid.uuid4())
            patch["detailed_scopes"].append(row)
    if "objectives" in data and data["objectives"] is not None:
        det: List[Dict[str, Any]] = []
        titles: List[str] = []
        for o in data["objectives"]:
            od = dict(o) if isinstance(o, dict) else o.model_dump()
            oid = od.get("id") or str(uuid.uuid4())
            det.append({"id": oid, "title": od.get("title") or "", "description": od.get("description") or ""})
            if od.get("title"):
                titles.append(od["title"])
        patch["detailed_objectives"] = det
        patch["audit_objectives"] = titles
    elif "audit_objectives" in data and data["audit_objectives"] is not None:
        patch["detailed_objectives"] = [
            {"id": str(uuid.uuid4()), "title": t, "description": ""} for t in (data["audit_objectives"] or [])
        ]
    await db.audit_engagements.update_one({"engagement_id": engagement_id}, {"$set": patch})
    await audit_log(current["email"], "update_engagement", "audit_engagement", engagement_id, {"fields": list(patch.keys())})
    doc = await db.audit_engagements.find_one({"engagement_id": engagement_id}, {"_id": 0})
    return _normalize_engagement_doc(doc or {})


@router.delete("/audit-engagements/{engagement_id}")
async def delete_engagement(request: Request, engagement_id: str, current=Depends(get_current_user)):
    eng = await _engagement_or_404(engagement_id, current=current, request=request)
    eid = engagement_id
    await db.audit_engagements.delete_one({"engagement_id": eid})
    for coll in (
        "ca_materiality",
        "ca_risks",
        "ca_risk_control_map",
        "ca_trial_balance",
        "ca_trial_balance_lines",
        "ca_fs_snapshots",
        "ca_audit_adjustments",
        "ca_schedule_audit",
        "ca_control_tests",
        "ca_control_deficiencies",
        "ca_control_certifications",
        "ca_working_papers",
        "ca_audit_evidence",
        "ca_wp_folders",
        "ca_wp_review_notes",
        "ca_wp_signoffs",
        "ca_sampling_plans",
        "ca_sample_transactions",
        "ca_vouching_items",
        "ca_compliance_results",
        "ca_compliance_findings",
        "ca_gst_rec",
        "ca_tds_rec",
        "ca_caro_state",
        "ca_tax44_state",
        "ca_caro_responses",
        "ca_audit_observations",
        "ca_audit_findings",
        "ca_audit_opinions",
        "ca_final_reports",
        "ca_management_letters",
        "ca_mgmt_repr",
        "ca_assurance_snapshots",
    ):
        try:
            await db[coll].delete_many({"engagement_id": eid})
        except Exception:
            pass
    await db.cases.update_many({"engagement_id": eid}, {"$unset": {"engagement_id": ""}})
    await db.exceptions.update_many({"engagement_id": eid}, {"$unset": {"engagement_id": ""}})
    await audit_log(current["email"], "delete_engagement", "audit_engagement", eid, {"mongo_id": eng.get("id")})
    return {"deleted": True, "engagement_id": eid}


@router.post("/audit-engagements/{engagement_id}/milestones")
async def add_milestone(request: Request, engagement_id: str, body: sch.AuditMilestoneIn, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    ms = {
        "id": str(uuid.uuid4()),
        "title": body.title,
        "due_date": body.due_date,
        "status": body.status,
        "owner_email": body.owner_email,
        "created_at": _now(),
    }
    await db.audit_engagements.update_one({"engagement_id": engagement_id}, {"$push": {"milestones": ms}, "$set": {"updated_at": _now()}})
    return ms


@router.post("/audit-engagements/{engagement_id}/team")
async def add_team_member(request: Request, engagement_id: str, body: sch.AuditTeamMemberIn, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    row = {
        "id": str(uuid.uuid4()),
        "user_email": body.user_email,
        "role": body.role,
        "allocation_pct": body.allocation_pct or 100.0,
        "added_at": _now(),
    }
    await db.audit_engagements.update_one(
        {"engagement_id": engagement_id},
        {"$push": {"team_members": row}, "$addToSet": {"assigned_team": body.user_email}, "$set": {"updated_at": _now()}},
    )
    return row


@router.post("/audit-engagements/{engagement_id}/planning-notes")
async def add_planning_note(request: Request, engagement_id: str, body: sch.AuditPlanningNoteIn, current=Depends(get_current_user)):
    await _engagement_or_404(engagement_id, current=current, request=request)
    note = {
        "id": str(uuid.uuid4()),
        "note": body.note,
        "visibility": body.visibility,
        "author_email": current["email"],
        "created_at": _now(),
    }
    await db.audit_engagements.update_one(
        {"engagement_id": engagement_id},
        {"$push": {"planning_notes": note}, "$set": {"updated_at": _now()}},
    )
    return note


@router.get("/audit-engagements/{engagement_id}/summary")
async def engagement_summary(request: Request, engagement_id: str, current=Depends(get_current_user)):
    eng = _normalize_engagement_doc(await _engagement_or_404(engagement_id, current=current, request=request))
    mat = await db.ca_materiality.find_one({"engagement_id": engagement_id}, {"_id": 0})
    risks = [r async for r in db.ca_risks.find({"engagement_id": engagement_id}, {"_id": 0})]
    cases = await db.cases.count_documents({"engagement_id": engagement_id})
    open_cases = await db.cases.count_documents({"engagement_id": engagement_id, "status": {"$ne": "closed"}})
    exceptions = [e async for e in db.exceptions.find({"engagement_id": engagement_id}, {"_id": 0}).limit(500)]
    controls_linked = {cid for r in risks for cid in (r.get("linked_controls") or [])}
    return {
        "engagement": eng,
        "materiality": mat,
        "risk_count": len(risks),
        "high_risks": [r for r in risks if r.get("risk_rating") in ("high", "critical")],
        "cases_total": cases,
        "cases_open": open_cases,
        "exceptions_count": len(exceptions),
        "linked_controls": sorted(controls_linked),
        "milestones": eng.get("milestones") or [],
        "team_members": eng.get("team_members") or [],
    }
