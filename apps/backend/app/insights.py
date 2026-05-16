"""AI-driven insight engine.

Produces {insights, recommendations, action_items} per section (CFO, Controller,
Audit, Compliance, Risk intelligence, My Cases, All Cases, Evidence Explorer). Uses:
  - Deterministic aggregation of the same data the UI shows
  - Gemini 3 Flash via emergentintegrations for narrative + prioritisation
  - In-memory TTL cache (10 min) keyed on section+user+master-filter dimensions (Phase 8)
  - Heuristic fallback when the LLM key is exhausted so the UI never breaks.
"""
from __future__ import annotations
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

try:
    # Optional dependency: allow app import without emergent runtime.
    from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    LlmChat = None  # type: ignore
    UserMessage = None  # type: ignore

from app.analytics import _reconciliation_scope, _scope_exceptions
from app.services.case_service import merge_cases_master_filters


_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL_SEC = 600  # 10 min


SECTIONS = {
    "cfo": "CFO Cockpit",
    "controller": "Controller Dashboard",
    "audit": "Audit Workspace",
    "compliance": "Compliance Dashboard",
    "risk": "Risk Intelligence Hub",
    "my-cases": "My Cases",
    "cases": "All Cases",
    "evidence": "Evidence Explorer",
}


SYSTEM_PROMPT = (
    "You are the One Touch Audit AI insight engine. Given a compact JSON snapshot of a "
    "section's data, output THREE arrays — insights, recommendations, action_items — as a "
    "single JSON object. No prose, no markdown, no code fence. Rules:\n"
    "- insights: 3-5 objective statements describing what the data shows. Each item has "
    "  {title, detail, severity ('info'|'warning'|'critical'), metric (optional string)}.\n"
    "- recommendations: 3-5 concrete next actions tailored to the persona. Each item has "
    "  {title, detail, impact ('low'|'medium'|'high')}.\n"
    "- action_items: 2-4 specific, owner-assignable tasks referencing real ids/codes from "
    "  the snapshot when possible. Each item has {title, owner_hint, priority ('P1'|'P2'|'P3'), "
    "  related_id (optional string), related_type (optional string)}.\n"
    "- Always cite real control codes, case ids, or vendor/customer names from the snapshot. "
    "Never invent numbers. If data is empty, say so in insights and suggest next-step data to seed."
)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _cases_scope_merge(base: Dict[str, Any], scope: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Align case queries with ``GET /cases`` / dashboard my-cases master filters (Phase 9)."""
    scope = scope or {}
    return merge_cases_master_filters(
        dict(base),
        entity_code=scope.get("entity_code"),
        period_ym=scope.get("period_ym"),
        department_id=scope.get("department_id"),
        cost_center_id=scope.get("cost_center_id"),
    )


async def _snapshot_cfo(db, scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Compact snapshot for CFO view (Phase 8 — optional master scope)."""
    scope = scope or {}
    open_q = _scope_exceptions(
        {"status": {"$ne": "closed"}},
        entity_code=scope.get("entity_code"),
        period_ym=scope.get("period_ym"),
        department_id=scope.get("department_id"),
        cost_center_id=scope.get("cost_center_id"),
    )
    open_ex = await db.exceptions.count_documents(open_q)
    crit_q = _scope_exceptions(
        {"severity": {"$in": ["critical", "high"]}, "status": {"$ne": "closed"}},
        entity_code=scope.get("entity_code"),
        period_ym=scope.get("period_ym"),
        department_id=scope.get("department_id"),
        cost_center_id=scope.get("cost_center_id"),
    )
    crit = [e async for e in db.exceptions.find(
        crit_q,
        {"_id": 0, "id": 1, "control_code": 1, "severity": 1, "title": 1,
         "financial_exposure": 1, "entity": 1, "process": 1, "anomaly_score": 1},
    ).sort("financial_exposure", -1).limit(10)]
    exposure = sum(e["financial_exposure"] for e in crit)
    by_process: Dict[str, Dict[str, float]] = {}
    async for e in db.exceptions.find(open_q, {"_id": 0, "process": 1, "financial_exposure": 1}):
        bp = by_process.setdefault(e["process"], {"count": 0, "exposure": 0.0})
        bp["count"] += 1
        bp["exposure"] += e.get("financial_exposure", 0.0)
    closed_q = _cases_scope_merge({"status": "closed"}, scope)
    open_cq = _cases_scope_merge({"status": {"$ne": "closed"}}, scope)
    closed_cases = await db.cases.count_documents(closed_q)
    open_cases = await db.cases.count_documents(open_cq)
    overdue = 0
    now = datetime.now(timezone.utc)
    async for c in db.cases.find(open_cq, {"_id": 0, "due_date": 1}):
        try:
            if datetime.fromisoformat(c["due_date"]) < now:
                overdue += 1
        except Exception:
            pass
    return {
        "total_open_exceptions": open_ex,
        "high_critical_exposure_usd": round(exposure, 2),
        "top_10_critical": crit,
        "by_process": {k: {"count": v["count"], "exposure": round(v["exposure"], 2)}
                       for k, v in by_process.items()},
        "open_cases": open_cases,
        "closed_cases": closed_cases,
        "overdue_cases": overdue,
    }


async def _snapshot_controller(db, scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    scope = scope or {}
    manual_je = [e async for e in db.exceptions.find(
        _scope_exceptions(
            {"control_code": "C-GL-001", "status": {"$ne": "closed"}},
            entity_code=scope.get("entity_code"),
            period_ym=scope.get("period_ym"),
            department_id=scope.get("department_id"),
            cost_center_id=scope.get("cost_center_id"),
        ),
        {"_id": 0, "id": 1, "title": 1, "financial_exposure": 1, "entity": 1}).sort("financial_exposure", -1).limit(5)]
    backdated = await db.exceptions.count_documents(_scope_exceptions(
        {"control_code": "C-GL-002", "status": {"$ne": "closed"}},
        entity_code=scope.get("entity_code"),
        period_ym=scope.get("period_ym"),
        department_id=scope.get("department_id"),
        cost_center_id=scope.get("cost_center_id"),
    ))
    ap_exc = await db.exceptions.count_documents(_scope_exceptions(
        {"process": "Procure-to-Pay", "status": {"$ne": "closed"}},
        entity_code=scope.get("entity_code"),
        period_ym=scope.get("period_ym"),
        department_id=scope.get("department_id"),
        cost_center_id=scope.get("cost_center_id"),
    ))
    from app.services import reconciliation_metrics as _rm

    recon_over, recon_total = await _rm.count_overdue_reconciliations(
        db,
        entity_code=scope.get("entity_code"),
        period_ym=scope.get("period_ym"),
    )
    fx = [e async for e in db.exceptions.find(
        _scope_exceptions(
            {"control_code": "C-TR-003", "status": {"$ne": "closed"}},
            entity_code=scope.get("entity_code"),
            period_ym=scope.get("period_ym"),
            department_id=scope.get("department_id"),
            cost_center_id=scope.get("cost_center_id"),
        ),
        {"_id": 0, "title": 1, "financial_exposure": 1}).limit(5)]
    return {
        "manual_je_breaches_top5": manual_je,
        "backdated_journal_count": backdated,
        "ap_exception_count": ap_exc,
        "reconciliations_overdue": recon_over,
        "reconciliations_total": recon_total,
        "fx_deviations_top5": fx,
    }


async def _snapshot_audit(db, scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    scope = scope or {}
    controls = [c async for c in db.controls.find({}, {"_id": 0, "code": 1, "name": 1, "process": 1,
                                                       "criticality": 1, "last_run_pass": 1,
                                                       "last_run_exceptions": 1}).sort("code", 1)]
    failing = [c for c in controls if (c.get("last_run_exceptions") or 0) > 0]
    failing.sort(key=lambda c: -(c.get("last_run_exceptions") or 0))
    run_q: Dict[str, Any] = {}
    if scope.get("period_ym"):
        run_q["run_ts"] = {"$regex": f"^{scope['period_ym']}"}
    if scope.get("entity_code"):
        run_q["entities"] = scope["entity_code"]
    runs = [r async for r in db.test_runs.find(run_q if run_q else {}, {"_id": 0}).sort("run_ts", -1).limit(10)]
    return {
        "controls_total": len(controls),
        "controls_failing": len(failing),
        "top_failing_controls": failing[:8],
        "recent_test_runs": runs,
    }


async def _snapshot_compliance(db, scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    scope = scope or {}
    sod = [e async for e in db.exceptions.find(
        _scope_exceptions(
            {"control_code": "C-ACC-002"},
            entity_code=scope.get("entity_code"),
            period_ym=scope.get("period_ym"),
            department_id=scope.get("department_id"),
            cost_center_id=scope.get("cost_center_id"),
        ),
        {"_id": 0, "title": 1, "source_record_id": 1}).limit(10)]
    terminated = [e async for e in db.exceptions.find(
        _scope_exceptions(
            {"control_code": "C-ACC-001"},
            entity_code=scope.get("entity_code"),
            period_ym=scope.get("period_ym"),
            department_id=scope.get("department_id"),
            cost_center_id=scope.get("cost_center_id"),
        ),
        {"_id": 0, "title": 1, "source_record_id": 1}).limit(10)]
    tax_open = await db.exceptions.count_documents(_scope_exceptions(
        {"control_code": {"$in": ["C-TX-001", "C-TX-002"]}, "status": {"$ne": "closed"}},
        entity_code=scope.get("entity_code"),
        period_ym=scope.get("period_ym"),
        department_id=scope.get("department_id"),
        cost_center_id=scope.get("cost_center_id"),
    ))
    wht_short = [e async for e in db.exceptions.find(
        _scope_exceptions(
            {"control_code": "C-TX-002"},
            entity_code=scope.get("entity_code"),
            period_ym=scope.get("period_ym"),
            department_id=scope.get("department_id"),
            cost_center_id=scope.get("cost_center_id"),
        ),
        {"_id": 0, "title": 1, "financial_exposure": 1}).limit(5)]
    return {
        "sod_conflicts": sod,
        "terminated_user_activity": terminated,
        "tax_open_exceptions": tax_open,
        "wht_shortfall_samples": wht_short,
    }


async def _snapshot_my_cases(
    db, user_email: str, scope: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    scope = scope or {}
    cq = _cases_scope_merge({"owner_email": user_email}, scope)
    cases = [c async for c in db.cases.find(cq, {"_id": 0}).sort("due_date", 1)]
    now = datetime.now(timezone.utc)
    overdue = []
    critical = []
    for c in cases:
        try:
            if c["status"] != "closed" and datetime.fromisoformat(c["due_date"]) < now:
                overdue.append({"id": c["id"], "title": c["title"], "priority": c["priority"],
                                "due_date": c["due_date"], "exposure": c["financial_exposure"]})
        except Exception:
            pass
        if c["severity"] == "critical" and c["status"] != "closed":
            critical.append({"id": c["id"], "title": c["title"], "priority": c["priority"],
                             "exposure": c["financial_exposure"]})
    return {
        "owner": user_email,
        "total_cases": len(cases),
        "open_cases": sum(1 for c in cases if c["status"] != "closed"),
        "overdue_cases": overdue[:10],
        "critical_open": critical[:10],
    }


async def _snapshot_all_cases(db, scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    scope = scope or {}
    open_cq = _cases_scope_merge({"status": {"$ne": "closed"}}, scope)
    top = [c async for c in db.cases.find(open_cq, {"_id": 0}).sort("financial_exposure", -1).limit(15)]
    by_owner: Dict[str, int] = {}
    async for c in db.cases.find(open_cq, {"_id": 0, "owner_email": 1}):
        by_owner[c["owner_email"]] = by_owner.get(c["owner_email"], 0) + 1
    by_priority: Dict[str, int] = {}
    async for c in db.cases.find(open_cq, {"_id": 0, "priority": 1}):
        by_priority[c.get("priority", "P3")] = by_priority.get(c.get("priority", "P3"), 0) + 1
    return {
        "top_exposure_cases": [{"id": c["id"], "title": c["title"], "priority": c["priority"],
                                "exposure": c["financial_exposure"], "owner": c["owner_email"],
                                "entity": c["entity"]} for c in top],
        "open_by_owner": by_owner,
        "open_by_priority": by_priority,
    }


async def _snapshot_evidence(db, scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Evidence Explorer summary: recent exceptions + their source coverage (optional master scope)."""
    scope = scope or {}
    ex_open = _scope_exceptions(
        {"status": {"$ne": "closed"}},
        entity_code=scope.get("entity_code"),
        period_ym=scope.get("period_ym"),
        department_id=scope.get("department_id"),
        cost_center_id=scope.get("cost_center_id"),
    )
    ex_any = _scope_exceptions(
        None,
        entity_code=scope.get("entity_code"),
        period_ym=scope.get("period_ym"),
        department_id=scope.get("department_id"),
        cost_center_id=scope.get("cost_center_id"),
    )
    recent = [e async for e in db.exceptions.find(
        ex_open,
        {"_id": 0, "id": 1, "control_code": 1, "title": 1, "source_record_type": 1,
         "financial_exposure": 1, "anomaly_score": 1}).sort("detected_at", -1).limit(12)]
    src_types: Dict[str, int] = {}
    q_cov = ex_any if ex_any else {}
    async for e in db.exceptions.find(q_cov, {"_id": 0, "source_record_type": 1}):
        src_types[e.get("source_record_type", "unknown")] = src_types.get(e.get("source_record_type", "unknown"), 0) + 1
    policy_count = await db.policies.count_documents({})
    return {
        "recent_exceptions": recent,
        "source_type_coverage": src_types,
        "policy_count": policy_count,
    }


async def _snapshot_risk(db, scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Phase 39 — Same signals as Risk intelligence UI: CFO cockpit slice + master risk scores (scoped)."""
    scope = scope or {}
    from app.analytics import cfo_cockpit
    from app.services import master_data_service as mds

    cockpit = await cfo_cockpit(
        db,
        entity_code=scope.get("entity_code"),
        period_ym=scope.get("period_ym"),
        department_id=scope.get("department_id"),
        cost_center_id=scope.get("cost_center_id"),
    )
    k = cockpit.get("kpis") or {}
    top = (cockpit.get("top_risks") or [])[:10]
    top_compact = [
        {
            "id": r.get("id"),
            "control_code": r.get("control_code"),
            "title": r.get("title"),
            "severity": r.get("severity"),
            "financial_exposure": r.get("financial_exposure"),
            "process": r.get("process"),
            "entity": r.get("entity"),
        }
        for r in top
    ]
    heat = cockpit.get("heatmap") or []
    by_process: Dict[str, Dict[str, Any]] = {}
    for row in heat:
        p = row.get("process")
        if not p:
            continue
        cur = by_process.setdefault(p, {"min_readiness": 100.0, "_entities": []})
        rd = row.get("readiness")
        if isinstance(rd, (int, float)):
            cur["min_readiness"] = min(float(cur["min_readiness"]), float(rd))
        ent = row.get("entity")
        if ent and ent not in cur["_entities"]:
            cur["_entities"].append(ent)
    heat_summary = {
        p: {"min_readiness": v["min_readiness"], "entity_count": len(v["_entities"])}
        for p, v in by_process.items()
    }
    scores = await mds.list_risk_scores(db, scope.get("entity_code"), 15)
    score_compact = [
        {key: r.get(key) for key in ("id", "entity_code", "object_type", "object_id", "score", "band", "drivers")}
        for r in scores
    ]
    return {
        "filters_applied": cockpit.get("filters_applied"),
        "kpis": {
            "audit_readiness_pct": k.get("audit_readiness_pct"),
            "unresolved_high_risk_exposure": k.get("unresolved_high_risk_exposure"),
            "high_critical_open_cases": k.get("high_critical_open_cases"),
            "remediation_sla_pct": k.get("remediation_sla_pct"),
        },
        "top_risks": top_compact,
        "readiness_by_process": heat_summary,
        "finance_risk_scores": score_compact,
    }


SNAPSHOT_FN = {
    "cfo": _snapshot_cfo,
    "controller": _snapshot_controller,
    "audit": _snapshot_audit,
    "compliance": _snapshot_compliance,
    "risk": _snapshot_risk,
    "cases": _snapshot_all_cases,
    "evidence": _snapshot_evidence,
}


async def _gather_snapshot(
    db, section: str, user_email: str, scope: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if section == "my-cases":
        return await _snapshot_my_cases(db, user_email, scope)
    fn = SNAPSHOT_FN.get(section)
    if not fn:
        return {}
    return await fn(db, scope)


def _heuristic_output(section: str, snap: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic fallback used when the LLM is unavailable."""
    insights: List[Dict[str, Any]] = []
    recs: List[Dict[str, Any]] = []
    actions: List[Dict[str, Any]] = []

    if section == "cfo":
        ex = snap.get("high_critical_exposure_usd", 0)
        oc = snap.get("overdue_cases", 0)
        insights.append({"title": f"${ex:,.0f} high/critical exposure across {snap.get('total_open_exceptions', 0)} open exceptions",
                         "detail": "Aggregated from open critical + high severity findings.",
                         "severity": "critical" if ex > 1_000_000 else "warning",
                         "metric": f"${ex:,.0f}"})
        insights.append({"title": f"{oc} overdue cases currently breaching SLA",
                         "detail": "Past-due items erode audit readiness score.",
                         "severity": "critical" if oc > 5 else "warning"})
        bp = snap.get("by_process", {})
        if bp:
            worst = sorted(bp.items(), key=lambda kv: -kv[1]["exposure"])[0]
            insights.append({"title": f"{worst[0]} leads process exposure",
                             "detail": f"{worst[1]['count']} open findings, ${worst[1]['exposure']:,.0f} at risk.",
                             "severity": "warning"})
        recs.append({"title": "Escalate top-3 critical cases", "detail": "Cap SLA breaches at <5.", "impact": "high"})
        recs.append({"title": "Review heatmap gaps before close", "detail": "Any process scoring <70 needs owner sign-off.", "impact": "medium"})
        for c in snap.get("top_10_critical", [])[:3]:
            actions.append({"title": f"Resolve {c['control_code']} — {c['title'][:60]}",
                            "owner_hint": "controller@onetouch.ai",
                            "priority": "P1",
                            "related_id": c["id"], "related_type": "exception"})

    elif section == "controller":
        insights.append({"title": f"{snap.get('backdated_journal_count', 0)} backdated journals still open",
                         "detail": "Period-close risk if unresolved by cutoff.",
                         "severity": "critical" if snap.get("backdated_journal_count", 0) > 0 else "info"})
        insights.append({"title": f"{snap.get('reconciliations_overdue', 0)} / {snap.get('reconciliations_total', 0)} reconciliations overdue",
                         "detail": "Treasury and Record-to-Report dependencies flagged.",
                         "severity": "warning"})
        recs.append({"title": "Clear backdated JEs before cutoff",
                     "detail": "Require secondary approval on all C-GL-002 findings.", "impact": "high"})
        for je in snap.get("manual_je_breaches_top5", [])[:3]:
            actions.append({"title": f"Sign off manual JE {je.get('title', '')[:70]}",
                            "owner_hint": "gl.lead@onetouch.ai", "priority": "P1",
                            "related_id": je["id"], "related_type": "exception"})

    elif section == "audit":
        insights.append({"title": f"{snap.get('controls_failing', 0)} of {snap.get('controls_total', 0)} controls failing",
                         "detail": "Failure = >0 open exceptions from latest test run.",
                         "severity": "warning"})
        for c in snap.get("top_failing_controls", [])[:3]:
            actions.append({"title": f"Root-cause {c['code']} — {c.get('name', '')}",
                            "owner_hint": "auditor@onetouch.ai", "priority": "P2",
                            "related_id": c["code"], "related_type": "control"})
        recs.append({"title": "Drive top-5 failing controls to zero",
                     "detail": "Prioritise critical-criticality controls first.", "impact": "high"})

    elif section == "compliance":
        sod = len(snap.get("sod_conflicts", []))
        term = len(snap.get("terminated_user_activity", []))
        insights.append({"title": f"{sod} SoD conflicts + {term} terminated-user events",
                         "detail": "Immediate RBAC review recommended.",
                         "severity": "critical" if (sod + term) > 0 else "info"})
        insights.append({"title": f"{snap.get('tax_open_exceptions', 0)} tax exceptions (incl. WHT shortfall) open",
                         "detail": "Statutory filing exposure.",
                         "severity": "warning"})
        recs.append({"title": "Revoke terminated-user access within 24h",
                     "detail": "Aligns to ITGC Access Policy v5.0 §6.2.", "impact": "high"})

    elif section == "risk":
        kp = snap.get("kpis") or {}
        ar = kp.get("audit_readiness_pct")
        if ar is not None:
            insights.append({
                "title": f"Audit readiness index at {ar}%",
                "detail": "CFO cockpit KPIs under current reporting scope.",
                "severity": "success" if ar >= 80 else "warning" if ar >= 60 else "critical",
                "metric": f"{ar}%",
            })
        exp = kp.get("unresolved_high_risk_exposure")
        if isinstance(exp, (int, float)):
            insights.append({
                "title": f"${float(exp):,.0f} unresolved high / critical exposure",
                "detail": "Exception-weighted financial exposure in scope.",
                "severity": "critical" if exp > 500_000 else "warning",
            })
        scores = snap.get("finance_risk_scores") or []
        if scores:
            bands = [s.get("band") for s in scores if s.get("band")]
            crit_bands = sum(1 for b in bands if str(b).lower() in ("red", "critical", "crimson"))
            insights.append({
                "title": f"{len(scores)} master risk score rows · {crit_bands} elevated bands",
                "detail": "Composite finance_risk_scores for entities/objects in scope.",
                "severity": "critical" if crit_bands else "info",
            })
        by_proc = snap.get("readiness_by_process") or {}
        if by_proc:
            worst = sorted(by_proc.items(), key=lambda kv: kv[1].get("min_readiness", 100.0))[:1]
            if worst:
                p, meta = worst[0]
                mr = meta.get("min_readiness")
                insights.append({
                    "title": f"{p} weakest process readiness ({mr}%)" if mr is not None else f"{p} process readiness tracked",
                    "detail": f"Across {meta.get('entity_count', 0)} entities in heatmap.",
                    "severity": "critical" if isinstance(mr, (int, float)) and mr < 60 else "warning",
                })
        recs.append({
            "title": "Align committee pack with heatmap weak cells",
            "detail": "Prioritise processes under 70% readiness before sign-off.",
            "impact": "high",
        })
        recs.append({
            "title": "Reconcile master risk bands with open exceptions",
            "detail": "Drivers on finance_risk_scores should map to top unresolved risks.",
            "impact": "medium",
        })
        for r in snap.get("top_risks", [])[:4]:
            if r.get("id") and r.get("control_code"):
                actions.append({
                    "title": f"Triage {r['control_code']} — {(r.get('title') or '')[:56]}",
                    "owner_hint": "risk.owner@onetouch.ai",
                    "priority": "P1" if r.get("severity") == "critical" else "P2",
                    "related_id": r["id"],
                    "related_type": "exception",
                })

    elif section == "my-cases":
        overdue = snap.get("overdue_cases", [])
        insights.append({"title": f"{snap.get('open_cases', 0)} open cases · {len(overdue)} overdue",
                         "detail": f"Owner: {snap.get('owner', '')}.",
                         "severity": "critical" if overdue else "info"})
        for c in overdue[:3]:
            actions.append({"title": f"Close overdue {c['priority']} — {c['title'][:60]}",
                            "owner_hint": snap.get("owner"),
                            "priority": c["priority"],
                            "related_id": c["id"], "related_type": "case"})
        recs.append({"title": "Clear overdue queue this week", "detail": "Prioritise P1 first.", "impact": "high"})

    elif section == "cases":
        top = snap.get("top_exposure_cases", [])
        insights.append({
            "title": f"Top exposure case: ${top[0]['exposure']:,.0f}" if top else "No open cases",
            "detail": top[0]["title"] if top else "",
            "severity": "critical" if top else "info",
        })
        owners = snap.get("open_by_owner", {})
        if owners:
            peak = max(owners.items(), key=lambda kv: kv[1])
            insights.append({"title": f"{peak[0]} holds {peak[1]} open cases",
                             "detail": "Consider load-balancing across owners.",
                             "severity": "warning" if peak[1] > 5 else "info"})
        recs.append({"title": "Rebalance top-loaded queue", "detail": "Move P3 items off saturated owners.", "impact": "medium"})

    elif section == "evidence":
        recent = snap.get("recent_exceptions", [])
        insights.append({"title": f"{len(recent)} latest unresolved exceptions with full lineage",
                         "detail": "Each links to source record + policy + case.",
                         "severity": "info"})
        cov = snap.get("source_type_coverage", {})
        if cov:
            insights.append({"title": f"{len(cov)} source record types covered",
                             "detail": ", ".join([f"{k}:{v}" for k, v in list(cov.items())[:6]]),
                             "severity": "info"})
        recs.append({"title": "Walk top-5 recent exceptions end-to-end",
                     "detail": "Validate evidence chain before sign-off.", "impact": "medium"})

    if not insights:
        insights.append({"title": "No data available yet", "detail": "Seed or run controls first.", "severity": "info"})
    if not recs:
        recs.append({"title": "Run 'Run All Controls' to generate signals",
                     "detail": "Dashboards populate after the first run.", "impact": "medium"})

    return {"insights": insights, "recommendations": recs, "action_items": actions,
            "source": "heuristic", "generated_at": _iso(datetime.now(timezone.utc))}


def _strip_code_fence(text: str) -> str:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    return t.strip()


async def _llm_output(section: str, snap: Dict[str, Any], user_role: str) -> Optional[Dict[str, Any]]:
    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not api_key:
        return None
    if LlmChat is None or UserMessage is None:
        return None
    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"insight-{section}-{int(time.time())}",
            system_message=SYSTEM_PROMPT,
        ).with_model("gemini", "gemini-3-flash-preview")
        prompt = (
            f"SECTION: {SECTIONS.get(section, section)}\n"
            f"PERSONA: {user_role}\n"
            f"DATA SNAPSHOT (JSON):\n{json.dumps(snap, default=str)[:6000]}\n\n"
            "Return ONLY valid JSON with keys: insights, recommendations, action_items. No prose."
        )
        response = await chat.send_message(UserMessage(text=prompt))
        raw = _strip_code_fence(str(response))
        parsed = json.loads(raw)
        # Sanitise minimum fields
        for key in ("insights", "recommendations", "action_items"):
            if not isinstance(parsed.get(key), list):
                parsed[key] = []
        parsed["source"] = "gemini-3-flash-preview"
        parsed["generated_at"] = _iso(datetime.now(timezone.utc))
        return parsed
    except Exception:
        return None


async def get_insights(
    db,
    section: str,
    user_email: str,
    user_role: str,
    force_refresh: bool = False,
    scope: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if section not in SECTIONS:
        return {"error": f"Unknown section: {section}"}

    scope = {k: v for k, v in (scope or {}).items() if v}
    sk = ":".join(
        scope.get(k, "") or ""
        for k in ("entity_code", "period_ym", "department_id", "cost_center_id")
    )
    cache_key = f"{section}::{user_email}::{sk}"
    if not force_refresh:
        cached = _CACHE.get(cache_key)
        if cached and (time.time() - cached["_ts"]) < _CACHE_TTL_SEC:
            return {**cached["data"], "cached": True, "cache_age_sec": int(time.time() - cached["_ts"])}

    snap = await _gather_snapshot(db, section, user_email, scope=scope or None)
    llm = await _llm_output(section, snap, user_role)
    out = llm if llm else _heuristic_output(section, snap)
    out["section"] = section
    out["section_label"] = SECTIONS[section]
    out["snapshot_size"] = len(json.dumps(snap, default=str))
    if scope:
        out["filters_applied"] = dict(scope)
    _CACHE[cache_key] = {"data": out, "_ts": time.time()}
    return {**out, "cached": False, "cache_age_sec": 0}


def clear_cache() -> None:
    _CACHE.clear()
