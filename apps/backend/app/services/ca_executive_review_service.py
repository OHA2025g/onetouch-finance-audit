"""Executive Review KPIs: assurance history, issue funnel, SLA, evidence readiness, compliance drill-down."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.utils.timeutil import iso_utc

_COMMITTEE_ASSURANCE_FLOOR_DEFAULT = 75.0
_SLA_DAYS = {"critical": 3, "high": 7, "medium": 14, "low": 30}


def _parse_iso_dt(value: Optional[str]) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        s = value.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _age_bucket_days(ref_iso: Optional[str], now: datetime) -> str:
    dt = _parse_iso_dt(ref_iso)
    if not dt:
        return "unknown"
    days = max(0, int((now - dt).total_seconds() / 86400))
    if days <= 30:
        return "d0_30"
    if days <= 60:
        return "d31_60"
    return "d61_plus"


def _empty_aging() -> Dict[str, int]:
    return {"d0_30": 0, "d31_60": 0, "d61_plus": 0, "unknown": 0}


def _inc_aging(bucket: Dict[str, int], key: str) -> None:
    bucket[key] = bucket.get(key, 0) + 1


def _severity_bucket(sev: Optional[str]) -> str:
    s = (sev or "medium").lower().strip()
    if s in ("critical", "high"):
        return "high_critical"
    if s == "low":
        return "low"
    return "medium"


async def maybe_record_assurance_snapshot(db, engagement_id: str, scores: Dict[str, Any]) -> None:
    """Persist one snapshot when score changes or prior snapshot is older than 6 hours."""
    now = datetime.now(timezone.utc)
    now_iso = iso_utc(now)
    slim = {
        k: scores[k]
        for k in scores
        if isinstance(k, str) and (k.endswith("_score") or k == "continuous_assurance_score")
    }
    last = await db.ca_assurance_snapshots.find_one({"engagement_id": engagement_id}, sort=[("captured_at", -1)])
    if last:
        last_sig = (last.get("scores") or {}).get("continuous_assurance_score")
        if last_sig == slim.get("continuous_assurance_score"):
            cap = _parse_iso_dt(last.get("captured_at"))
            if cap and (now - cap) < timedelta(hours=6):
                return
    await db.ca_assurance_snapshots.insert_one(
        {
            "id": str(uuid.uuid4()),
            "engagement_id": engagement_id,
            "captured_at": now_iso,
            "scores": slim,
            "trigger": "dashboard",
        }
    )
    while True:
        n = await db.ca_assurance_snapshots.count_documents({"engagement_id": engagement_id})
        if n <= 50:
            break
        oldest = await db.ca_assurance_snapshots.find_one({"engagement_id": engagement_id}, sort=[("captured_at", 1)])
        if not oldest:
            break
        await db.ca_assurance_snapshots.delete_one({"id": oldest.get("id")})


async def append_assurance_snapshot(db, engagement_id: str, scores: Dict[str, Any], *, trigger: str = "api") -> None:
    """Always insert one snapshot row (still prunes to last 50 per engagement). Used by POST when ``force`` is true."""
    now = datetime.now(timezone.utc)
    now_iso = iso_utc(now)
    slim = {
        k: scores[k]
        for k in scores
        if isinstance(k, str) and (k.endswith("_score") or k == "continuous_assurance_score")
    }
    await db.ca_assurance_snapshots.insert_one(
        {
            "id": str(uuid.uuid4()),
            "engagement_id": engagement_id,
            "captured_at": now_iso,
            "scores": slim,
            "trigger": trigger,
        }
    )
    while True:
        n = await db.ca_assurance_snapshots.count_documents({"engagement_id": engagement_id})
        if n <= 50:
            break
        oldest = await db.ca_assurance_snapshots.find_one({"engagement_id": engagement_id}, sort=[("captured_at", 1)])
        if not oldest:
            break
        await db.ca_assurance_snapshots.delete_one({"id": oldest.get("id")})


async def load_assurance_history(db, engagement_id: str, limit: int = 24) -> List[Dict[str, Any]]:
    cur = db.ca_assurance_snapshots.find({"engagement_id": engagement_id}, {"_id": 0}).sort("captured_at", -1).limit(limit)
    rows = [r async for r in cur]
    rows.reverse()
    return rows


def compute_issue_funnel(
    *,
    risks: List[Dict[str, Any]],
    cases: List[Dict[str, Any]],
    deficiencies: List[Dict[str, Any]],
    observations: List[Dict[str, Any]],
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)

    def funnel_block(items: List[Dict[str, Any]], date_key_candidates: Tuple[str, ...], severity_fn) -> Dict[str, Any]:
        by_sev = {"high_critical": 0, "medium": 0, "low": 0}
        aging = _empty_aging()
        for it in items:
            sk = severity_fn(it)
            if sk == "high_critical":
                by_sev["high_critical"] += 1
            elif sk == "low":
                by_sev["low"] += 1
            else:
                by_sev["medium"] += 1
            ref = None
            for k in date_key_candidates:
                ref = it.get(k)
                if ref:
                    break
            _inc_aging(aging, _age_bucket_days(ref if isinstance(ref, str) else None, now))
        return {"total": len(items), "by_severity": by_sev, "aging": aging}

    high_risks = [r for r in risks if (r.get("risk_rating") or "").lower() in ("high", "critical")]
    open_cases = [c for c in cases if (c.get("status") or "").lower() != "closed"]
    open_obs = [o for o in observations if not o.get("resolved")]

    def case_sev(c: Dict[str, Any]) -> str:
        return _severity_bucket(c.get("severity"))

    def risk_sev(r: Dict[str, Any]) -> str:
        rr = (r.get("risk_rating") or "").lower()
        return "high_critical" if rr in ("high", "critical") else "medium"

    def def_sev(d: Dict[str, Any]) -> str:
        return _severity_bucket(d.get("severity"))

    def obs_sev(o: Dict[str, Any]) -> str:
        return _severity_bucket(o.get("severity"))

    return {
        "risks_high_critical": funnel_block(high_risks, ("updated_at", "created_at"), risk_sev),
        "open_cases": funnel_block(open_cases, ("opened_at", "due_date"), case_sev),
        "control_deficiencies": funnel_block(deficiencies, ("created_at", "updated_at"), def_sev),
        "open_observations": funnel_block(open_obs, ("created_at",), obs_sev),
    }


def compute_remediation_sla(cases: List[Dict[str, Any]], *, now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    closed = [c for c in cases if (c.get("status") or "").lower() == "closed"]
    within = 0
    measured = 0
    for c in closed:
        op = _parse_iso_dt(c.get("opened_at"))
        cl = _parse_iso_dt(c.get("closed_at")) or _parse_iso_dt(c.get("updated_at"))
        if not op or not cl:
            continue
        sev = (c.get("severity") or "medium").lower()
        sla = float(_SLA_DAYS.get(sev, 14))
        measured += 1
        if (cl - op).total_seconds() <= sla * 86400:
            within += 1
    pct_within = round(100.0 * within / measured, 1) if measured else None

    open_cases = [c for c in cases if (c.get("status") or "").lower() != "closed"]
    overdue = 0
    max_exp = 0.0
    for c in open_cases:
        due = _parse_iso_dt(c.get("due_date"))
        if due and due < now:
            overdue += 1
        try:
            exp = float(c.get("financial_exposure") or c.get("exposure_usd") or 0)
            if exp > max_exp:
                max_exp = exp
        except (TypeError, ValueError):
            pass
    return {
        "closed_measured": measured,
        "closed_within_sla": within,
        "pct_closed_within_sla": pct_within,
        "sla_days_by_severity": _SLA_DAYS,
        "open_overdue_count": overdue,
        "largest_open_exposure_usd": round(max_exp, 2),
    }


async def compute_evidence_readiness(db, engagement_id: str) -> Dict[str, Any]:
    wp_ids = [r["id"] async for r in db.ca_working_papers.find({"engagement_id": engagement_id}, {"id": 1})]
    total = len(wp_ids)
    if not total:
        definition = (
            "Working paper readiness = share of engagement WPs with at least one sign-off row on file. "
            "Seed working papers from engagement hub to populate this metric."
        )
        return {
            "working_papers_total": 0,
            "working_papers_with_signoff": 0,
            "readiness_pct": None,
            "unsigned_count": 0,
            "definition": definition,
        }
    signed_ids = set()
    wp_set = set(wp_ids)
    async for s in db.ca_wp_signoffs.find({"working_paper_id": {"$in": wp_ids}}, {"working_paper_id": 1}):
        wid = s.get("working_paper_id")
        if wid and wid in wp_set:
            signed_ids.add(wid)
    with_so = len(signed_ids)
    pct = round(100.0 * with_so / total, 1)
    definition = (
        "Working paper readiness = percentage of engagement working papers that have at least one recorded sign-off "
        "(preparer / reviewer / partner)."
    )
    return {
        "working_papers_total": total,
        "working_papers_with_signoff": with_so,
        "readiness_pct": pct,
        "unsigned_count": max(0, total - with_so),
        "definition": definition,
    }


def extend_compliance_snapshot(
    reqs: List[Dict[str, Any]],
    history: List[Dict[str, Any]],
) -> Dict[str, Any]:
    by_law: Dict[str, Dict[str, int]] = {}
    themes_non_compliant: Dict[str, int] = {}
    for r in reqs:
        law = str(r.get("law_code") or "OTHER")
        st = (r.get("status") or "").lower()
        if law not in by_law:
            by_law[law] = {"compliant": 0, "non_compliant": 0, "pending_evidence": 0, "other": 0}
        if "compliant" == st or st == "compliant":
            by_law[law]["compliant"] += 1
        elif "non" in st:
            by_law[law]["non_compliant"] += 1
            key = f"{law}: {(r.get('section') or '')[:24]}"
            themes_non_compliant[key] = themes_non_compliant.get(key, 0) + 1
        elif "pending" in st:
            by_law[law]["pending_evidence"] += 1
        else:
            by_law[law]["other"] += 1

    top_nc = sorted(themes_non_compliant.items(), key=lambda x: -x[1])[:8]
    trend = None
    if len(history) >= 2:
        a = (history[-2].get("scores") or {}).get("compliance_score")
        b = (history[-1].get("scores") or {}).get("compliance_score")
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            trend = {"prior": a, "latest": b, "delta": round(float(b) - float(a), 1)}
    pending_total = sum(by_law[l]["pending_evidence"] for l in by_law)
    return {
        "by_law": by_law,
        "top_non_compliant_themes": [{"theme": k, "count": v} for k, v in top_nc],
        "pending_evidence_backlog": pending_total,
        "compliance_score_trend": trend,
    }


def materiality_bridge(mat: Optional[Dict[str, Any]], exceptions: List[Dict[str, Any]], observations: List[Dict[str, Any]]) -> Dict[str, Any]:
    fm = float(mat.get("final_materiality") or 0) if mat else 0.0
    open_exc = [e for e in exceptions if (e.get("status") or "").lower() != "closed"]
    agg = 0.0
    for e in open_exc:
        try:
            agg += float(e.get("financial_exposure") or 0)
        except (TypeError, ValueError):
            continue
    obs_open = len([o for o in observations if not o.get("resolved")])
    ratio_pct = round(100.0 * agg / fm, 2) if fm > 0 else None
    narrative = (
        f"Aggregate open exception exposure ({agg:,.0f}) vs planning materiality ({fm:,.0f})."
        if fm > 0
        else "Set planning materiality to contextualise open exception exposure."
    )
    return {
        "planning_materiality": fm,
        "aggregated_open_exception_exposure": round(agg, 2),
        "ratio_pct_of_materiality": ratio_pct,
        "open_observation_count": obs_open,
        "narrative": narrative,
    }


def reporting_status_row(rep: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not rep:
        return {
            "latest_report_status": None,
            "opinion_phase": "not_started",
            "caro_placeholder": "CARO / Key Audit Matters — link observations in Report Studio when drafting.",
            "kam_placeholder": "KAM drafts appear once material themes are logged as observations.",
        }
    return {
        "latest_report_status": rep.get("status"),
        "opinion_phase": rep.get("phase") or rep.get("status") or "drafting",
        "caro_placeholder": "CARO clauses optional — align with India compliance module outputs.",
        "kam_placeholder": "Promote material observations to KAM narratives in Report Studio.",
        "created_at": rep.get("created_at"),
    }


async def agenda_readiness(
    db,
    engagement_id: str,
    *,
    critical_open_cases: int,
) -> Dict[str, Any]:
    letters = await db.ca_management_letters.count_documents({"engagement_id": engagement_id})
    pack_touch = await db.ca_final_reports.count_documents({"engagement_id": engagement_id})
    return {
        "management_letter_generated": letters > 0,
        "committee_pack_touched": pack_touch > 0,
        "open_critical_items_cleared": critical_open_cases == 0,
        "critical_open_cases": critical_open_cases,
        "minutes_followups_stub": [],
        "checklist": [
            {"id": "letter", "label": "Management letter drafted", "done": letters > 0},
            {"id": "pack", "label": "Committee pack / report artefact started", "done": pack_touch > 0},
            {"id": "critical", "label": "Zero open critical cases", "done": critical_open_cases == 0},
        ],
    }


async def build_executive_review_kpis(
    db,
    engagement_id: str,
    eng: Dict[str, Any],
    scores: Dict[str, Any],
) -> Dict[str, Any]:
    """Aggregate Tier A/B/C blocks for ca-dashboard / Executive Review UI."""
    await maybe_record_assurance_snapshot(db, engagement_id, scores)
    history = await load_assurance_history(db, engagement_id, limit=24)

    risks = [r async for r in db.ca_risks.find({"engagement_id": engagement_id}, {"_id": 0}).limit(300)]
    cases = [c async for c in db.cases.find({"engagement_id": engagement_id}, {"_id": 0}).limit(400)]
    defs = [d async for d in db.ca_control_deficiencies.find({"engagement_id": engagement_id}, {"_id": 0}).limit(200)]
    observations = [o async for o in db.ca_audit_observations.find({"engagement_id": engagement_id}, {"_id": 0}).limit(200)]
    exceptions = [e async for e in db.exceptions.find({"engagement_id": engagement_id}, {"_id": 0}).limit(500)]
    mat = await db.ca_materiality.find_one({"engagement_id": engagement_id}, {"_id": 0})
    rep = await db.ca_final_reports.find_one({"engagement_id": engagement_id}, {"_id": 0}, sort=[("created_at", -1)])
    comp = await db.ca_compliance_results.find_one({"engagement_id": engagement_id}, {"_id": 0})
    reqs = (comp or {}).get("requirements") or []

    funnel = compute_issue_funnel(risks=risks, cases=cases, deficiencies=defs, observations=observations)
    sla = compute_remediation_sla(cases)
    evidence = await compute_evidence_readiness(db, engagement_id)
    compliance_x = extend_compliance_snapshot(reqs, history)
    mat_bridge = materiality_bridge(mat, exceptions, observations)
    reporting = reporting_status_row(rep)
    crit_cases = sum(1 for c in cases if (c.get("status") or "").lower() != "closed" and (c.get("severity") or "").lower() == "critical")
    agenda = await agenda_readiness(db, engagement_id, critical_open_cases=crit_cases)

    overall = float(scores.get("continuous_assurance_score") or 0)
    floor = float(_COMMITTEE_ASSURANCE_FLOOR_DEFAULT)
    direction = "flat"
    if len(history) >= 2:
        prev = float((history[-2].get("scores") or {}).get("continuous_assurance_score") or overall)
        if overall > prev + 0.5:
            direction = "up"
        elif overall < prev - 0.5:
            direction = "down"

    spark_keys = [
        "continuous_assurance_score",
        "audit_readiness_score",
        "control_effectiveness_score",
        "compliance_score",
        "evidence_completeness_score",
        "fraud_risk_score",
        "financial_statement_risk_score",
    ]
    sparklines = {
        k: [{"at": h.get("captured_at"), "value": (h.get("scores") or {}).get(k)} for h in history if (h.get("scores") or {}).get(k) is not None]
        for k in spark_keys
    }

    radar_components = {
        "audit_readiness_score": scores.get("audit_readiness_score"),
        "control_effectiveness_score": scores.get("control_effectiveness_score"),
        "compliance_score": scores.get("compliance_score"),
        "evidence_completeness_score": scores.get("evidence_completeness_score"),
        "fraud_risk_score": scores.get("fraud_risk_score"),
        "financial_statement_risk_score": scores.get("financial_statement_risk_score"),
    }

    risk_preview = [
        {
            "id": r.get("id"),
            "title": r.get("risk_title") or r.get("title") or "Risk",
            "risk_rating": r.get("risk_rating"),
            "process_area": r.get("process_area"),
        }
        for r in risks[:24]
    ]

    committee_threshold = {"continuous_assurance_floor": floor, "below_floor": overall < floor}
    assurance_trend_block = {"direction": direction, "latest": overall, "history_points": len(history)}

    tier_a = {
        "committee_threshold": committee_threshold,
        "assurance_trend": assurance_trend_block,
        "assurance_history": history,
        "sparkline_series": sparklines,
        "radar_components": radar_components,
    }
    tier_b = {
        "issue_funnel": funnel,
        "remediation_sla": sla,
        "evidence_readiness": evidence,
        "compliance_extended": compliance_x,
        "materiality_bridge": mat_bridge,
    }
    tier_c = {
        "reporting_status": reporting,
        "agenda_readiness": agenda,
        "risk_register_preview": risk_preview,
    }

    return {
        "committee_threshold": committee_threshold,
        "assurance_trend": assurance_trend_block,
        "assurance_history": history,
        "sparkline_series": sparklines,
        "radar_components": radar_components,
        "issue_funnel": funnel,
        "remediation_sla": sla,
        "evidence_readiness": evidence,
        "compliance_extended": compliance_x,
        "materiality_bridge": mat_bridge,
        "reporting_status": reporting,
        "agenda_readiness": agenda,
        "risk_register_preview": risk_preview,
        "tier_a": tier_a,
        "tier_b": tier_b,
        "tier_c": tier_c,
    }


async def cross_org_executive_summary(db, engagement_docs: List[Dict[str, Any]], compute_scores_fn, limit: int = 6) -> List[Dict[str, Any]]:
    """Lightweight rows for CFO hub comparison."""
    out: List[Dict[str, Any]] = []
    for eng in engagement_docs:
        eid = eng.get("engagement_id")
        if not eid:
            continue
        scores = await compute_scores_fn(str(eid), eng)
        oc = await db.cases.count_documents(
            {
                "engagement_id": eid,
                "status": {"$nin": ["closed", "Closed"]},
                "severity": {"$regex": "^critical$", "$options": "i"},
            }
        )
        out.append(
            {
                "engagement_id": eid,
                "entity_name": eng.get("entity_name"),
                "financial_year": eng.get("financial_year"),
                "continuous_assurance_score": scores.get("continuous_assurance_score"),
                "open_critical_cases": oc,
                "status": eng.get("status"),
            }
        )
    # Lowest assurance first (committee attention), tie-break by more open critical cases.
    out.sort(
        key=lambda r: (
            float(r.get("continuous_assurance_score") or 0),
            -int(r.get("open_critical_cases") or 0),
        )
    )
    return out[:limit]
