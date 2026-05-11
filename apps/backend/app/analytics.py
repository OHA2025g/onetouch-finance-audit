"""Dashboards: aggregated KPI data per persona + audit readiness scoring + evidence graph."""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.utils.timeutil import iso_utc


SEVERITY_WEIGHT = {"critical": 1.0, "high": 0.7, "medium": 0.4, "low": 0.2}


def _dedupe_top_risks(rows: List[Dict[str, Any]], *, limit: int = 10) -> List[Dict[str, Any]]:
    """CFO cockpit should show one row per underlying finding, not one per raw Mongo document.

    ``run_control`` deletes prior rows only when ``status == "open"``. Exceptions moved to
    ``in_progress`` / case workflow persist, and later runs insert fresh ``open`` rows for the same
    customer/source — producing identical titles and exposures in ``top_risks``. We keep the
    highest severity×exposure row per (control_code, source_record_type, source_record_id).
    """
    rows = sorted(
        rows,
        key=lambda e: -(float(e.get("financial_exposure") or 0) * SEVERITY_WEIGHT.get(e.get("severity"), 0.3)),
    )
    seen: set[tuple] = set()
    out: List[Dict[str, Any]] = []
    for e in rows:
        key = (
            e.get("control_code") or "",
            e.get("source_record_type") or "",
            e.get("source_record_id") or "",
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
        if len(out) >= limit:
            break
    return out


def _exception_dept_cc_clause(
    department_id: Optional[str],
    cost_center_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Match optional org fields on exceptions (forward-compatible with richer docs)."""
    ors: List[Dict[str, Any]] = []
    if department_id:
        ors.extend([{"department_id": department_id}, {"dept_id": department_id}])
    if cost_center_id:
        ors.extend([{"cost_center_id": cost_center_id}, {"cc_id": cost_center_id}])
    if not ors:
        return None
    return {"$or": ors}


def _doc_dept_cc_clause(
    department_id: Optional[str],
    cost_center_id: Optional[str],
) -> Dict[str, Any]:
    """Match optional org fields on transactional docs once denormalized (Slice 9)."""
    q: Dict[str, Any] = {}
    if department_id:
        q["department_id"] = department_id
    if cost_center_id:
        q["cost_center_id"] = cost_center_id
    return q


def _scope_exceptions(
    base: Optional[Dict[str, Any]] = None,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Merge dashboard exception filters (AND). Omit empty ``base`` so we never AND a bare ``{}``."""
    parts: List[Dict[str, Any]] = []
    if base:
        parts.append(dict(base))
    if entity_code:
        parts.append({"entity": entity_code})
    if period_ym:
        parts.append({"detected_at": {"$regex": f"^{period_ym}"}})
    dc = _exception_dept_cc_clause(department_id, cost_center_id)
    if dc:
        parts.append(dc)
    if not parts:
        return {}
    if len(parts) == 1:
        return parts[0]
    return {"$and": parts}


def _reconciliation_scope(
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
) -> Dict[str, Any]:
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    if period_ym:
        q["period"] = period_ym
    return q


def _case_base(entity_code: Optional[str]) -> Dict[str, Any]:
    if not entity_code:
        return {}
    return {"entity": entity_code}


async def backfill_test_run_entities(db, *, limit: int = 5000) -> Dict[str, Any]:
    """Phase 8 — populate ``entities`` on legacy ``test_runs`` from distinct exception entities per control."""
    scanned = 0
    updated = 0
    cur = db.test_runs.find(
        {"$or": [{"entities": {"$exists": False}}, {"entities": None}]},
        {"_id": 1, "control_id": 1},
    ).limit(limit)
    async for run in cur:
        scanned += 1
        cid = run.get("control_id")
        if not cid:
            await db.test_runs.update_one({"_id": run["_id"]}, {"$set": {"entities": []}})
            updated += 1
            continue
        ents_set: set[str] = set()
        async for ex in db.exceptions.find({"control_id": cid}, {"_id": 0, "entity": 1}).limit(800):
            if ex.get("entity"):
                ents_set.add(str(ex["entity"]))
        ents = sorted(ents_set)
        await db.test_runs.update_one({"_id": run["_id"]}, {"$set": {"entities": ents}})
        updated += 1
    return {"scanned": scanned, "updated": updated}


async def _counts_by(db, collection: str, field: str) -> Dict[str, int]:
    out: Dict[str, int] = defaultdict(int)
    async for d in db[collection].find({}, {"_id": 0, field: 1}):
        out[d.get(field, "unknown")] += 1
    return dict(out)


async def compute_readiness(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Readiness per (entity, process) = weighted score 0–100.

    Optional filters align with Phase 4 dashboard query params (entity / period / org slice).
    """
    out: List[Dict[str, Any]] = []
    entities = [e async for e in db.entities.find({}, {"_id": 0})]
    if entity_code:
        entities = [e for e in entities if e.get("code") == entity_code]
    processes = sorted({c["process"] async for c in db.controls.find({}, {"_id": 0, "process": 1})})

    for ent in entities:
        for proc in processes:
            ex_q = _scope_exceptions(
                {"process": proc, "entity": ent["code"], "status": {"$ne": "closed"}},
                period_ym=period_ym,
                department_id=department_id,
                cost_center_id=cost_center_id,
            )
            open_exs = [e async for e in db.exceptions.find(ex_q, {"_id": 0})]
            open_high = sum(1 for e in open_exs if e["severity"] in ("critical", "high"))
            exposure = sum(e["financial_exposure"] for e in open_exs)
            passed = await db.controls.count_documents({"process": proc, "last_run_pass": True})
            ran = await db.controls.count_documents({"process": proc, "last_run_pass": {"$ne": None}})
            pass_rate = (passed / ran) if ran else 0.6
            recon_component = 1.0
            if proc in ("Treasury", "Record-to-Report"):
                rq_over: Dict[str, Any] = {"entity": ent["code"], "status": "overdue"}
                rq_tot: Dict[str, Any] = {"entity": ent["code"]}
                if period_ym:
                    rq_over["period"] = period_ym
                    rq_tot["period"] = period_ym
                overdue = await db.reconciliations.count_documents(rq_over)
                total = await db.reconciliations.count_documents(rq_tot)
                recon_component = 1.0 - (overdue / total) if total else 0.8
            ct: Dict[str, Any] = {"process": proc, "entity": ent["code"]}
            ce: Dict[str, Any] = {"process": proc, "entity": ent["code"], "closed_at": {"$ne": None}}
            if period_ym:
                ct["opened_at"] = {"$regex": f"^{period_ym}"}
                ce["opened_at"] = {"$regex": f"^{period_ym}"}
            cases_total = await db.cases.count_documents(ct)
            cases_w_evidence = await db.cases.count_documents(ce)
            evidence_component = (cases_w_evidence / cases_total) if cases_total else 0.85
            issue_penalty = min(1.0, open_high / 10.0)
            issue_component = 1.0 - issue_penalty

            control_component = pass_rate
            score = 100 * (0.40 * control_component + 0.25 * recon_component + 0.20 * evidence_component + 0.15 * issue_component)
            out.append({
                "entity": ent["code"],
                "process": proc,
                "readiness": round(score, 1),
                "control_component": round(control_component, 3),
                "recon_component": round(recon_component, 3),
                "evidence_component": round(evidence_component, 3),
                "issue_component": round(issue_component, 3),
                "open_high": open_high,
                "exposure": round(exposure, 2),
            })
    return out


async def cfo_cockpit(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
) -> Dict[str, Any]:
    """CFO dashboard; optional filters match Phase 4 ``/dashboard/cfo`` query params."""
    readiness_rows = await compute_readiness(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    overall_readiness = round(
        sum(r["readiness"] for r in readiness_rows) / max(1, len(readiness_rows)), 1
    )
    cb = _case_base(entity_code)
    high_q = _scope_exceptions(
        {"severity": {"$in": ["critical", "high"]}, "status": {"$ne": "closed"}},
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    high_crit_exposure = 0.0
    async for e in db.exceptions.find(high_q, {"_id": 0}):
        high_crit_exposure += e["financial_exposure"]
    oc_q: Dict[str, Any] = {"status": {"$ne": "closed"}, **cb}
    open_cases = await db.cases.count_documents(oc_q)
    high_crit_cases = await db.cases.count_documents({**oc_q, "severity": {"$in": ["critical", "high"]}})
    closed_cases = await db.cases.count_documents({"status": "closed", **cb})
    total_cases = open_cases + closed_cases

    per_control: Dict[str, int] = defaultdict(int)
    scope_any = any((entity_code, period_ym, department_id, cost_center_id))
    if scope_any:
        pq = _scope_exceptions(
            None,
            entity_code=entity_code,
            period_ym=period_ym,
            department_id=department_id,
            cost_center_id=cost_center_id,
        )
        async for ex in db.exceptions.find(pq, {"_id": 0, "control_code": 1}):
            per_control[ex["control_code"]] += 1
    else:
        async for ex in db.exceptions.find({}, {"_id": 0, "control_code": 1}):
            per_control[ex["control_code"]] += 1
    total_findings = sum(per_control.values()) or 1
    repeat = sum(v for v in per_control.values() if v > 1)
    repeat_rate = 100.0 * repeat / total_findings

    total_ex_q = _scope_exceptions(
        None,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    total_ex = await db.exceptions.count_documents(total_ex_q if total_ex_q else {})
    ev_q = _scope_exceptions(
        {"status": "closed"},
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    evidenced = await db.exceptions.count_documents(ev_q)
    evidence_pct = 100.0 * evidenced / total_ex if total_ex else 80.0

    sla_total = 0
    sla_met = 0
    sla_case_q: Dict[str, Any] = {"status": "closed", "closed_at": {"$ne": None}, **cb}
    if period_ym:
        sla_case_q["opened_at"] = {"$regex": f"^{period_ym}"}
    async for ca in db.cases.find(sla_case_q, {"_id": 0}):
        try:
            opened = datetime.fromisoformat(ca["opened_at"])
            closed = datetime.fromisoformat(ca["closed_at"])
            sla_total += 1
            if (closed - opened).days <= 7:
                sla_met += 1
        except Exception:
            pass
    sla_pct = 100.0 * sla_met / sla_total if sla_total else 92.5

    top_failing = sorted(per_control.items(), key=lambda kv: -kv[1])[:6]
    top_failing_out = []
    for code, count in top_failing:
        c = await db.controls.find_one({"code": code}, {"_id": 0})
        if c:
            top_failing_out.append({
                "code": code,
                "name": c["name"],
                "process": c["process"],
                "exceptions": count,
                "criticality": c["criticality"],
            })

    tr_q = _scope_exceptions(
        {"status": {"$ne": "closed"}},
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    top_risks: List[Dict[str, Any]] = []
    async for e in db.exceptions.find(tr_q, {"_id": 0}):
        top_risks.append(e)
    top_risks = _dedupe_top_risks(top_risks, limit=10)

    filters_applied = {k: v for k, v in {
        "entity_code": entity_code,
        "period_ym": period_ym,
        "department_id": department_id,
        "cost_center_id": cost_center_id,
    }.items() if v}

    return {
        "kpis": {
            "audit_readiness_pct": overall_readiness,
            "unresolved_high_risk_exposure": round(high_crit_exposure, 2),
            "high_critical_open_cases": high_crit_cases,
            "open_cases": open_cases,
            "repeat_finding_rate_pct": round(repeat_rate, 1),
            "evidence_completeness_pct": round(evidence_pct, 1),
            "remediation_sla_pct": round(sla_pct, 1),
            "total_cases": total_cases,
        },
        "top_failing_controls": top_failing_out,
        "top_risks": top_risks,
        "heatmap": readiness_rows,
        "trends": await _readiness_trend(
            db,
            entity_code=entity_code,
            period_ym=period_ym,
            department_id=department_id,
            cost_center_id=cost_center_id,
        ),
        "filters_applied": filters_applied,
    }


async def _readiness_trend(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Build a synthetic 8-week trend from current readiness (slightly decaying going back)."""
    readiness = await compute_readiness(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    avg = sum(r["readiness"] for r in readiness) / max(1, len(readiness))
    now = datetime.now(timezone.utc)
    trend = []
    for w in range(8, 0, -1):
        dt = now - timedelta(weeks=w)
        # Generate plausible trend from a slight dip 5w ago rising to today
        jitter = (abs(w - 5) - 3) * 2.0
        trend.append({
            "week": dt.strftime("%Y-W%U"),
            "readiness": round(max(55, min(98, avg + jitter)), 1),
            "control_fail_count": max(0, int(20 + (w - 4) * 2)),
            "exposure": round(1000000 + (w - 4) * 50000, 2),
        })
    return trend


async def controller_dashboard(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Controller dashboard; optional filters match Phase 4 ``/dashboard/controller`` query params."""
    close_blockers = await db.exceptions.count_documents(
        _scope_exceptions(
            {"process": {"$in": ["Record-to-Report", "Treasury"]}, "status": {"$ne": "closed"}},
            entity_code=entity_code,
            period_ym=period_ym,
            department_id=department_id,
            cost_center_id=cost_center_id,
        )
    )
    manual_je_breaches = await db.exceptions.count_documents(
        _scope_exceptions(
            {"control_code": "C-GL-001", "status": {"$ne": "closed"}},
            entity_code=entity_code,
            period_ym=period_ym,
            department_id=department_id,
            cost_center_id=cost_center_id,
        )
    )
    backdated = await db.exceptions.count_documents(
        _scope_exceptions(
            {"control_code": "C-GL-002", "status": {"$ne": "closed"}},
            entity_code=entity_code,
            period_ym=period_ym,
            department_id=department_id,
            cost_center_id=cost_center_id,
        )
    )
    ap_queue = await db.exceptions.count_documents(
        _scope_exceptions(
            {"process": "Procure-to-Pay", "status": {"$ne": "closed"}},
            entity_code=entity_code,
            period_ym=period_ym,
            department_id=department_id,
            cost_center_id=cost_center_id,
        )
    )
    rscope = _reconciliation_scope(entity_code, period_ym)
    recon_total = await db.reconciliations.count_documents(rscope if rscope else {})
    recon_overdue = await db.reconciliations.count_documents({**rscope, "status": "overdue"} if rscope else {"status": "overdue"})
    recons = [
        r async for r in db.reconciliations.find(rscope if rscope else {}, {"_id": 0}).sort("due_date", -1).limit(50)
    ]
    ap_q = _scope_exceptions(
        {"process": "Procure-to-Pay", "status": {"$ne": "closed"}},
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    ap_exceptions = [e async for e in db.exceptions.find(ap_q, {"_id": 0}).sort("financial_exposure", -1).limit(20)]

    filters_applied = {k: v for k, v in {
        "entity_code": entity_code,
        "period_ym": period_ym,
        "department_id": department_id,
        "cost_center_id": cost_center_id,
    }.items() if v}

    return {
        "kpis": {
            "close_blockers": close_blockers,
            "manual_je_breaches": manual_je_breaches,
            "backdated_journals": backdated,
            "ap_exception_count": ap_queue,
            "reconciliations_overdue": recon_overdue,
            "reconciliations_total": recon_total,
        },
        "reconciliations": recons,
        "ap_exceptions": ap_exceptions,
        "filters_applied": filters_applied,
    }


async def compliance_dashboard(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Compliance dashboard; optional filters match Phase 5 ``/dashboard/compliance`` query params."""
    sod_q = _scope_exceptions(
        {"control_code": "C-ACC-002"},
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    sod_conflicts = [e async for e in db.exceptions.find(sod_q, {"_id": 0})]
    acc_q = _scope_exceptions(
        {"control_code": "C-ACC-001"},
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    access_violations = [e async for e in db.exceptions.find(acc_q, {"_id": 0})]
    tax_issues = await db.exceptions.count_documents(
        _scope_exceptions(
            {"control_code": "C-TX-001", "status": {"$ne": "closed"}},
            entity_code=entity_code,
            period_ym=period_ym,
            department_id=department_id,
            cost_center_id=cost_center_id,
        )
    )
    now = datetime.now(timezone.utc)
    buckets = {"0-7d": 0, "8-14d": 0, "15-30d": 0, ">30d": 0}
    aging_q = _scope_exceptions(
        {"status": {"$ne": "closed"}},
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    async for e in db.exceptions.find(aging_q, {"_id": 0}):
        try:
            d = datetime.fromisoformat(e["detected_at"])
            age = (now - d).days
        except Exception:
            age = 0
        if age <= 7:
            buckets["0-7d"] += 1
        elif age <= 14:
            buckets["8-14d"] += 1
        elif age <= 30:
            buckets["15-30d"] += 1
        else:
            buckets[">30d"] += 1

    filters_applied = {k: v for k, v in {
        "entity_code": entity_code,
        "period_ym": period_ym,
        "department_id": department_id,
        "cost_center_id": cost_center_id,
    }.items() if v}

    return {
        "kpis": {
            "sod_conflicts": len(sod_conflicts),
            "terminated_user_activity": len(access_violations),
            "tax_mismatch_open": tax_issues,
            "policy_breach_total": sum(buckets.values()),
        },
        "sod_conflicts": sod_conflicts,
        "access_violations": access_violations,
        "exception_aging": [{"bucket": k, "count": v} for k, v in buckets.items()],
        "filters_applied": filters_applied,
    }


async def working_capital_dashboard(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Slice 5 — Working capital dashboard (AR/AP ageing + stress signals).

    - AR uses Phase 2 `ar_invoices`.
    - AP uses Phase 1 `invoices`.
    - department_id / cost_center_id are currently applied only to exception-derived metrics.
    """
    now = datetime.now(timezone.utc)

    def _ent_scope(q: Dict[str, Any]) -> Dict[str, Any]:
        if entity_code:
            q["entity"] = entity_code
        return q

    def _period_scope(q: Dict[str, Any], field: str) -> Dict[str, Any]:
        if period_ym:
            q[field] = {"$regex": f"^{period_ym}"}
        return q

    # ---- AR ageing (open) ----
    ar_q: Dict[str, Any] = _ent_scope({"status": {"$in": ["open", "overdue"]}, **_doc_dept_cc_clause(department_id, cost_center_id)})
    _period_scope(ar_q, "invoice_date")
    ar_docs = [d async for d in db.ar_invoices.find(ar_q, {"_id": 0}).limit(5000)]

    ar_buckets = {"0_30": 0.0, "31_60": 0.0, "61_90": 0.0, "90_plus": 0.0}
    ar_open_total = 0.0
    ar_overdue_total = 0.0
    ar_overdue_count = 0
    top_overdue_ar: List[Dict[str, Any]] = []

    for inv in ar_docs:
        amt = float(inv.get("amount") or 0.0)
        ar_open_total += amt
        age_days = 0
        try:
            due = inv.get("due_date")
            if due:
                dd = datetime.fromisoformat(due)
                age_days = max(0, (now - dd).days)
        except Exception:
            age_days = 0

        if age_days <= 30:
            ar_buckets["0_30"] += amt
        elif age_days <= 60:
            ar_buckets["31_60"] += amt
        elif age_days <= 90:
            ar_buckets["61_90"] += amt
        else:
            ar_buckets["90_plus"] += amt

        if age_days >= 1:
            ar_overdue_total += amt
            ar_overdue_count += 1
            top_overdue_ar.append(inv)

    top_overdue_ar.sort(key=lambda d: -(float(d.get("amount") or 0.0)))
    top_overdue_ar = top_overdue_ar[:20]

    # ---- AP ageing (open) ----
    ap_q: Dict[str, Any] = _ent_scope({"status": {"$in": ["open", "overdue"]}, **_doc_dept_cc_clause(department_id, cost_center_id)})
    _period_scope(ap_q, "invoice_date")
    ap_docs = [d async for d in db.invoices.find(ap_q, {"_id": 0}).limit(5000)]

    ap_buckets = {"0_30": 0.0, "31_60": 0.0, "61_90": 0.0, "90_plus": 0.0}
    ap_open_total = 0.0
    ap_overdue_total = 0.0
    ap_overdue_count = 0
    top_overdue_ap: List[Dict[str, Any]] = []

    for inv in ap_docs:
        amt = float(inv.get("amount") or 0.0)
        ap_open_total += amt
        age_days = 0
        try:
            due = inv.get("due_date")
            if due:
                dd = datetime.fromisoformat(due)
                age_days = max(0, (now - dd).days)
        except Exception:
            age_days = 0

        if age_days <= 30:
            ap_buckets["0_30"] += amt
        elif age_days <= 60:
            ap_buckets["31_60"] += amt
        elif age_days <= 90:
            ap_buckets["61_90"] += amt
        else:
            ap_buckets["90_plus"] += amt

        if age_days >= 1:
            ap_overdue_total += amt
            ap_overdue_count += 1
            top_overdue_ap.append(inv)

    top_overdue_ap.sort(key=lambda d: -(float(d.get("amount") or 0.0)))
    top_overdue_ap = top_overdue_ap[:20]

    # ---- Close-quality: open exceptions impacting WC ----
    wc_ex_q = _scope_exceptions(
        {"process": {"$in": ["Order-to-Cash", "Procure-to-Pay"]}, "status": {"$ne": "closed"}},
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    wc_ex_open = await db.exceptions.count_documents(wc_ex_q)

    filters_applied = {k: v for k, v in {
        "entity_code": entity_code,
        "period_ym": period_ym,
        "department_id": department_id,
        "cost_center_id": cost_center_id,
    }.items() if v}

    return {
        "kpis": {
            "ar_open_amount": round(ar_open_total, 2),
            "ar_overdue_amount": round(ar_overdue_total, 2),
            "ar_overdue_count": ar_overdue_count,
            "ap_open_amount": round(ap_open_total, 2),
            "ap_overdue_amount": round(ap_overdue_total, 2),
            "ap_overdue_count": ap_overdue_count,
            "wc_exception_open": wc_ex_open,
        },
        "ar_aging": [{"bucket": k, "amount": round(v, 2)} for k, v in ar_buckets.items()],
        "ap_aging": [{"bucket": k, "amount": round(v, 2)} for k, v in ap_buckets.items()],
        "top_overdue_ar": top_overdue_ar,
        "top_overdue_ap": top_overdue_ap,
        "filters_applied": filters_applied,
    }


async def treasury_dashboard(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Slice 6 — Treasury dashboard (bank activity, off-hours wires, FX deviations).

    Data sources:
    - `bank_transactions`, `bank_accounts` (Phase 2)
    - Treasury-related exceptions are derived from controls C-TR-002 / C-TR-003 (Phase 2)
    """
    now = datetime.now(timezone.utc)

    bt_q: Dict[str, Any] = {**_doc_dept_cc_clause(department_id, cost_center_id)}
    if entity_code:
        bt_q["entity"] = entity_code
    if period_ym:
        bt_q["txn_ts"] = {"$regex": f"^{period_ym}"}

    txns = [t async for t in db.bank_transactions.find(bt_q, {"_id": 0}).sort("txn_ts", -1).limit(200)]
    total_out = sum(float(t.get("amount") or 0.0) for t in txns if t.get("direction") == "outbound")
    total_in = sum(float(t.get("amount") or 0.0) for t in txns if t.get("direction") == "inbound")

    # Simple cash runway proxy: net movement this period
    net = round(total_in - total_out, 2)

    # Treasury exceptions
    tr_ex_q = _scope_exceptions(
        {"process": "Treasury", "status": {"$ne": "closed"}},
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    tr_ex = [e async for e in db.exceptions.find(tr_ex_q, {"_id": 0}).sort("financial_exposure", -1).limit(50)]

    off_hours = [e for e in tr_ex if e.get("control_code") == "C-TR-002"]
    fx_dev = [e for e in tr_ex if e.get("control_code") == "C-TR-003"]

    # Bank accounts summary
    ba_q: Dict[str, Any] = {**_doc_dept_cc_clause(department_id, cost_center_id)}
    if entity_code:
        ba_q["entity"] = entity_code
    accounts = [a async for a in db.bank_accounts.find(ba_q, {"_id": 0}).sort("currency", 1)]

    filters_applied = {k: v for k, v in {
        "entity_code": entity_code,
        "period_ym": period_ym,
        "department_id": department_id,
        "cost_center_id": cost_center_id,
    }.items() if v}

    return {
        "kpis": {
            "bank_txn_count": len(txns),
            "cash_inflow": round(total_in, 2),
            "cash_outflow": round(total_out, 2),
            "net_cash_movement": net,
            "off_hours_wires_open": len(off_hours),
            "fx_deviation_open": len(fx_dev),
            "treasury_exceptions_open": len(tr_ex),
        },
        "bank_accounts": accounts,
        "recent_bank_transactions": txns,
        "off_hours_wires": off_hours[:20],
        "fx_deviations": fx_dev[:20],
        "filters_applied": filters_applied,
        "as_of": iso_utc(now),
    }


async def fpa_dashboard(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Slice 7 — FP&A snapshot (budget vs actual via CapEx + spend proxy via journals).

    Current data sources:
    - CapEx portfolio: `capex_projects` (Phase 2) with `budget_amount` and `actual_amount`
    - Spend proxy: `journals.total_amount` scoped by posting_date prefix for period_ym
    """
    now = datetime.now(timezone.utc)

    cpx_q: Dict[str, Any] = {**_doc_dept_cc_clause(department_id, cost_center_id)}
    if entity_code:
        cpx_q["entity"] = entity_code
    projects = [p async for p in db.capex_projects.find(cpx_q, {"_id": 0}).sort("actual_amount", -1).limit(200)]

    total_budget = sum(float(p.get("budget_amount") or 0.0) for p in projects)
    total_actual = sum(float(p.get("actual_amount") or 0.0) for p in projects)
    total_variance = total_actual - total_budget
    over_budget = [p for p in projects if float(p.get("actual_amount") or 0.0) > float(p.get("budget_amount") or 0.0)]
    over_budget.sort(key=lambda p: -(float(p.get("actual_amount") or 0.0) - float(p.get("budget_amount") or 0.0)))
    top_over = over_budget[:12]

    # Journal-based spend proxy (manual + automated) — purely informational until we have a full chart of accounts.
    j_q: Dict[str, Any] = {**_doc_dept_cc_clause(department_id, cost_center_id)}
    if entity_code:
        j_q["entity"] = entity_code
    if period_ym:
        j_q["posting_date"] = {"$regex": f"^{period_ym}"}
    journals = [j async for j in db.journals.find(j_q, {"_id": 0}).sort("posting_date", -1).limit(500)]
    je_total = sum(float(j.get("total_amount") or 0.0) for j in journals)
    manual_total = sum(float(j.get("total_amount") or 0.0) for j in journals if j.get("is_manual"))

    # Exceptions: highlight over-budget control + close-related manual JE risk as planning guardrails
    ex_q = _scope_exceptions(
        {"control_code": {"$in": ["C-FA-003", "C-GL-001"]}, "status": {"$ne": "closed"}},
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    exs = [e async for e in db.exceptions.find(ex_q, {"_id": 0}).sort("financial_exposure", -1).limit(50)]

    filters_applied = {k: v for k, v in {
        "entity_code": entity_code,
        "period_ym": period_ym,
        "department_id": department_id,
        "cost_center_id": cost_center_id,
    }.items() if v}

    return {
        "kpis": {
            "capex_total_budget": round(total_budget, 2),
            "capex_total_actual": round(total_actual, 2),
            "capex_total_variance": round(total_variance, 2),
            "capex_over_budget_count": len(over_budget),
            "journal_spend_total": round(je_total, 2),
            "manual_journal_total": round(manual_total, 2),
            "planning_exceptions_open": len(exs),
        },
        "capex_projects": projects,
        "top_over_budget_projects": top_over,
        "recent_journals": journals[:50],
        "planning_exceptions": exs,
        "filters_applied": filters_applied,
        "as_of": iso_utc(now),
        "note": "Spend is a journal-based proxy until chart-of-accounts budgeting is implemented.",
    }


async def cash_conversion_dashboard(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Slice 8 — Cash conversion cycle analytics (DSO/DPO/CCC).

    Approximations (until full COA + inventory available):
    - DSO = AR_open / (avg_daily_AR_invoice_sales) over last 30 days window
    - DPO = AP_open / (avg_daily_AP_invoice_purchases) over last 30 days window
    - DIO is not available (no inventory model); returned as null
    - CCC = DSO + DIO - DPO (with DIO=0 for CCC_proxy)
    """
    now = datetime.now(timezone.utc)
    window_days = 30
    window_start = now - timedelta(days=window_days)

    # AR open
    ar_open_q: Dict[str, Any] = {"status": {"$in": ["open", "overdue"]}, **_doc_dept_cc_clause(department_id, cost_center_id)}
    if entity_code:
        ar_open_q["entity"] = entity_code
    ar_open = [d async for d in db.ar_invoices.find(ar_open_q, {"_id": 0}).limit(10000)]
    ar_open_amt = sum(float(x.get("amount") or 0.0) for x in ar_open)

    # AR billed last 30 days (sales proxy)
    ar_sales_q: Dict[str, Any] = {"invoice_date": {"$gte": iso_utc(window_start), "$lte": iso_utc(now)}, **_doc_dept_cc_clause(department_id, cost_center_id)}
    if entity_code:
        ar_sales_q["entity"] = entity_code
    ar_recent = [d async for d in db.ar_invoices.find(ar_sales_q, {"_id": 0}).limit(20000)]
    ar_recent_amt = sum(float(x.get("amount") or 0.0) for x in ar_recent)
    ar_avg_daily = ar_recent_amt / max(1, window_days)
    dso = round((ar_open_amt / ar_avg_daily), 1) if ar_avg_daily > 0 else None

    # AP open (vendor invoices)
    ap_open_q: Dict[str, Any] = {"status": {"$in": ["open", "overdue"]}, **_doc_dept_cc_clause(department_id, cost_center_id)}
    if entity_code:
        ap_open_q["entity"] = entity_code
    ap_open = [d async for d in db.invoices.find(ap_open_q, {"_id": 0}).limit(10000)]
    ap_open_amt = sum(float(x.get("amount") or 0.0) for x in ap_open)

    # AP purchases last 30 days proxy
    ap_purch_q: Dict[str, Any] = {"invoice_date": {"$gte": iso_utc(window_start), "$lte": iso_utc(now)}, **_doc_dept_cc_clause(department_id, cost_center_id)}
    if entity_code:
        ap_purch_q["entity"] = entity_code
    ap_recent = [d async for d in db.invoices.find(ap_purch_q, {"_id": 0}).limit(20000)]
    ap_recent_amt = sum(float(x.get("amount") or 0.0) for x in ap_recent)
    ap_avg_daily = ap_recent_amt / max(1, window_days)
    dpo = round((ap_open_amt / ap_avg_daily), 1) if ap_avg_daily > 0 else None

    dio = None
    ccc_proxy = None
    if dso is not None and dpo is not None:
        ccc_proxy = round(dso - dpo, 1)

    # Exceptions that tend to hurt cash conversion (aged AR, duplicate payments, etc.)
    ex_q = _scope_exceptions(
        {"control_code": {"$in": ["C-OTC-002", "C-AP-002"]}, "status": {"$ne": "closed"}},
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    exs = [e async for e in db.exceptions.find(ex_q, {"_id": 0}).sort("financial_exposure", -1).limit(50)]

    filters_applied = {k: v for k, v in {
        "entity_code": entity_code,
        "period_ym": period_ym,
        "department_id": department_id,
        "cost_center_id": cost_center_id,
    }.items() if v}

    return {
        "kpis": {
            "dso_days": dso,
            "dpo_days": dpo,
            "dio_days": dio,
            "ccc_days_proxy": ccc_proxy,
            "ar_open_amount": round(ar_open_amt, 2),
            "ap_open_amount": round(ap_open_amt, 2),
            "ar_billed_30d": round(ar_recent_amt, 2),
            "ap_invoiced_30d": round(ap_recent_amt, 2),
            "cash_conversion_exceptions_open": len(exs),
        },
        "window_days": window_days,
        "as_of": iso_utc(now),
        "filters_applied": filters_applied,
        "exceptions": exs,
        "note": "DSO/DPO are proxies based on AR/AP invoices (last 30d) until full revenue/COGS + inventory model is implemented.",
    }


async def audit_workspace(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Audit workspace; ``period_ym`` scopes recent test runs by ``run_ts`` prefix (ISO).
    ``entity_code`` scopes runs to documents whose ``entities`` array contains that code (Phase 7).
    Control catalog stays global; control detail API scopes open exceptions."""
    controls = [c async for c in db.controls.find({}, {"_id": 0}).sort("code", 1)]
    run_q: Dict[str, Any] = {}
    if period_ym:
        run_q["run_ts"] = {"$regex": f"^{period_ym}"}
    if entity_code:
        run_q["entities"] = entity_code
    runs = [r async for r in db.test_runs.find(run_q if run_q else {}, {"_id": 0}).sort("run_ts", -1).limit(30)]
    filters_applied = {k: v for k, v in {
        "entity_code": entity_code,
        "period_ym": period_ym,
        "department_id": department_id,
        "cost_center_id": cost_center_id,
    }.items() if v}
    return {"controls": controls, "recent_runs": runs, "filters_applied": filters_applied}


async def evidence_graph(db, exception_id: str) -> Dict[str, Any]:
    ex = await db.exceptions.find_one({"id": exception_id}, {"_id": 0})
    if not ex:
        return {"nodes": [], "edges": []}
    control = await db.controls.find_one({"id": ex["control_id"]}, {"_id": 0})
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    def add_node(id_, type_, label, subtitle=None, meta=None):
        if any(n["id"] == id_ for n in nodes):
            return
        nodes.append({"id": id_, "type": type_, "label": label, "subtitle": subtitle, "meta": meta or {}})

    # Title as primary label so graphs differ per exception; control/entity as subtitle (same control can have many rows).
    add_node(
        ex["id"],
        "exception",
        ex.get("title") or f"Exception · {ex['control_code']}",
        f"{ex['control_code']} · {ex.get('entity', '')}",
        {"severity": ex.get("severity"), "exposure": ex.get("financial_exposure")},
    )
    # Always include a control node for graph stability.
    # Some modules create "ad-hoc" exceptions whose control_id doesn't exist in the controls catalog yet.
    if control:
        add_node(control["id"], "control", f"Control · {control.get('code')}", control.get("name"), {"criticality": control.get("criticality")})
        edges.append({"source": control["id"], "target": ex["id"], "relation": "detected"})
    else:
        cid = ex.get("control_id") or f"control::{ex.get('control_code')}"
        add_node(
            cid,
            "control",
            f"Control · {ex.get('control_code')}",
            ex.get("control_name") or ex.get("process") or "Ad-hoc control",
            {"criticality": ex.get("severity") or "medium", "source": "exception_fallback"},
        )
        edges.append({"source": cid, "target": ex["id"], "relation": "detected"})

    # Source record
    src_type = ex["source_record_type"]
    src_id = ex["source_record_id"]
    collection_map = {
        "invoice": "invoices", "payment": "payments", "journal": "journals",
        "reconciliation": "reconciliations", "access_event": "user_access_events", "user": None,
        # Phase 2:
        "customer": "customers", "ar_invoice": "ar_invoices", "sales_order": "sales_orders",
        "payroll_entry": "payroll_entries", "bank_transaction": "bank_transactions",
        "fx_rate": "fx_rates", "withholding": "withholding_records",
        "fixed_asset": "fixed_assets", "depreciation": "depreciation_schedules",
        "capex_project": "capex_projects",
    }
    coll = collection_map.get(src_type)
    if coll:
        rec = await db[coll].find_one({"id": src_id}, {"_id": 0})
        if rec:
            lbl = (rec.get("invoice_number") or rec.get("bank_reference") or rec.get("journal_number")
                   or rec.get("ar_number") or rec.get("so_number") or rec.get("customer_code")
                   or rec.get("asset_code") or rec.get("project_code")
                   or rec.get("reference") or rec.get("employee_code")
                   or rec.get("id"))
            # Evidence Explorer drill-down uses this (graph nodes are uniformly type "transaction").
            rec_meta = dict(rec)
            rec_meta["evidence_source_type"] = src_type
            add_node(src_id, "transaction", f"{src_type.title()} · {lbl}", f"${rec.get('amount', rec.get('total_amount', 0)):,.2f}" if isinstance(rec.get('amount', rec.get('total_amount')), (int, float)) else None, rec_meta)
            edges.append({"source": ex["id"], "target": src_id, "relation": "references"})
            # Link related PO/GRN if invoice
            if src_type == "invoice" and rec.get("po_id"):
                po = await db.purchase_orders.find_one({"id": rec["po_id"]}, {"_id": 0})
                if po:
                    add_node(po["id"], "transaction", f"PO · {po['po_number']}", f"${po['amount']:,.2f}")
                    edges.append({"source": src_id, "target": po["id"], "relation": "po_for"})
                    grn = await db.goods_receipts.find_one({"po_id": po["id"]}, {"_id": 0})
                    if grn:
                        add_node(grn["id"], "transaction", f"GRN · {grn['grn_number']}", f"${grn['amount']:,.2f}")
                        edges.append({"source": po["id"], "target": grn["id"], "relation": "receipt"})

    # Policy links (by control code heuristic)
    code_to_policy = {
        "C-AP": "Global AP Payment Policy v4.2",
        "C-GL": "Manual Journal Entry Policy v3.0",
        "C-ACC": "Segregation of Duties Matrix v2.1",
        "C-TR": "Manual Journal Entry Policy v3.0",
        "C-TX": "Global AP Payment Policy v4.2",
    }
    prefix = ex["control_code"][:4]
    policy_title = code_to_policy.get(prefix) or "Global AP Payment Policy v4.2"
    policy = await db.policies.find_one({"title": policy_title}, {"_id": 0})
    if policy:
        add_node(policy["id"], "policy", policy["title"], f"Effective {policy['effective_date']}", {"clauses": policy.get("clauses", [])})
        edges.append({"source": ex["id"], "target": policy["id"], "relation": "governed_by"})

    # Case
    case = await db.cases.find_one({"exception_id": ex["id"]}, {"_id": 0})
    if case:
        add_node(case["id"], "case", f"Case · {case['id'][:6]}", case.get("title", ""), {"status": case["status"], "owner": case.get("owner_email")})
        edges.append({"source": ex["id"], "target": case["id"], "relation": "has_case"})
        # Owner user
        if case.get("owner_email"):
            add_node(f"user::{case['owner_email']}", "user", case.get("owner_name") or case["owner_email"], case["owner_email"])
            edges.append({"source": case["id"], "target": f"user::{case['owner_email']}", "relation": "owned_by"})
        # Working papers that document this case (CA audit module)
        eng_id = case.get("engagement_id")
        if eng_id:
            async for wp in db.ca_working_papers.find({"engagement_id": eng_id, "linked_case_ids": case["id"]}, {"_id": 0}):
                wid = wp["id"]
                ref = wp.get("reference") or wid[:8]
                add_node(
                    wid,
                    "working_paper",
                    f"WP · {ref}",
                    wp.get("title") or "Working paper",
                    {"engagement_id": eng_id, "reference": wp.get("reference")},
                )
                edges.append({"source": wid, "target": case["id"], "relation": "documents_case"})

    return {"nodes": nodes, "edges": edges}
