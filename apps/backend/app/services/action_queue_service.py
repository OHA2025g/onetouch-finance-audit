"""CFO Action Queue — materialization, scoped listing, lifecycle, bulk actions."""

from __future__ import annotations

import base64
import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.analytics import _scope_exceptions
from app.services.case_service import merge_cases_master_filters
from app.services.reconciliation_metrics import is_overdue, recon_query
from app.utils.timeutil import iso_utc

SLA_DAYS = {"P0": 1, "P1": 3, "P2": 7, "P3": 14}
STALE_OPEN_DAYS = 14

SORT_FIELDS = {
    "score": [("score", 1), ("materiality_score", -1), ("updated_at", -1)],
    "exposure": [("detail.exposure", -1), ("score", 1), ("id", 1)],
    "age": [("created_at", 1), ("id", 1)],
    "materiality": [("materiality_score", -1), ("score", 1), ("id", 1)],
}


def encode_cursor(payload: Dict[str, Any]) -> str:
    return base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()


def decode_cursor(cursor: Optional[str]) -> Optional[Dict[str, Any]]:
    if not cursor:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor.encode())
        data = json.loads(raw.decode())
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _keyset_clause(sort: str, cursor_doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Keyset pagination filter for stable sort + id tie-break."""
    cid = cursor_doc.get("id")
    if not cid:
        return None
    if sort == "score":
        score = cursor_doc.get("score")
        if score is None:
            return None
        return {
            "$or": [
                {"score": {"$gt": score}},
                {"score": score, "id": {"$gt": cid}},
            ]
        }
    if sort == "materiality":
        mat = cursor_doc.get("materiality_score")
        if mat is None:
            return None
        return {
            "$or": [
                {"materiality_score": {"$lt": mat}},
                {"materiality_score": mat, "id": {"$gt": cid}},
            ]
        }
    if sort == "age":
        created = cursor_doc.get("created_at")
        if not created:
            return None
        return {
            "$or": [
                {"created_at": {"$gt": created}},
                {"created_at": created, "id": {"$gt": cid}},
            ]
        }
    if sort == "exposure":
        exp = cursor_doc.get("detail.exposure")
        if exp is None:
            exp = cursor_doc.get("exposure")
        if exp is None:
            return None
        return {
            "$or": [
                {"detail.exposure": {"$lt": exp}},
                {"detail.exposure": exp, "id": {"$gt": cid}},
            ]
        }
    return None


def _now() -> str:
    return iso_utc(datetime.now(timezone.utc))


def _stable_id(key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return f"aq-{h}"


def _priority_score(priority: str) -> int:
    return {"P0": 0, "P1": 10, "P2": 20, "P3": 30}.get(priority, 30)


def _derive_priority_for_case(case: Dict[str, Any]) -> str:
    sev = (case.get("severity") or "").lower()
    if sev == "critical":
        return "P0"
    if sev == "high":
        return "P1"
    if (case.get("priority") or "").upper() == "P1":
        return "P1"
    return "P2"


def _derive_priority_for_exception(ex: Dict[str, Any]) -> str:
    sev = (ex.get("severity") or "").lower()
    if sev == "critical":
        return "P0"
    if sev == "high":
        return "P1"
    return "P2"


def _materiality_score(priority: str, exposure: Any) -> float:
    try:
        exp = max(0.0, float(exposure or 0))
    except (TypeError, ValueError):
        exp = 0.0
    base = {"P0": 100.0, "P1": 75.0, "P2": 50.0, "P3": 25.0}.get(priority, 25.0)
    return round(base + min(25.0, math.log10(exp + 1.0) * 6.0), 2)


def _parse_dt(val: Any) -> Optional[datetime]:
    if not val:
        return None
    try:
        dt = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _age_days(created_at: Any, *, now: Optional[datetime] = None) -> float:
    dt = _parse_dt(created_at)
    if not dt:
        return 0.0
    now = now or datetime.now(timezone.utc)
    return max(0.0, (now - dt).total_seconds() / 86400.0)


def is_sla_breached(item: Dict[str, Any], age_days: Optional[float] = None) -> bool:
    age = age_days if age_days is not None else float(item.get("age_days") or 0)
    pri = (item.get("priority") or "P3").upper()
    return age > SLA_DAYS.get(pri, 14)


def scope_filters(
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
    process: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    action_type: Optional[str] = None,
    assignee_email: Optional[str] = None,
) -> Dict[str, Any]:
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    if period_ym:
        q["period_ym"] = period_ym
    if department_id:
        q["department_id"] = department_id
    if cost_center_id:
        q["cost_center_id"] = cost_center_id
    if process:
        q["process"] = process
    if status:
        q["status"] = status
    if priority:
        q["priority"] = priority
    if action_type:
        q["type"] = action_type
    if assignee_email:
        q["assignee_email"] = assignee_email
    return q


def _enrich_item(
    raw: Dict[str, Any],
    *,
    entity_code: Optional[str],
    period_ym: Optional[str],
    department_id: Optional[str],
    cost_center_id: Optional[str],
) -> Dict[str, Any]:
    det = raw.get("detail") or {}
    entity = det.get("entity") or entity_code
    process = det.get("process")
    exposure = det.get("exposure") or det.get("financial_exposure") or 0
    priority = raw.get("priority") or "P2"
    owner = det.get("owner_email")
    item = dict(raw)
    item["entity"] = entity
    item["process"] = process
    item["period_ym"] = period_ym
    item["department_id"] = department_id
    item["cost_center_id"] = cost_center_id
    item["assignee_email"] = owner
    item["materiality_score"] = _materiality_score(priority, exposure)
    if "detail" in item and exposure:
        item["detail"] = {**det, "exposure": exposure}
    item.setdefault("events", [])
    item.setdefault("comments", [])
    return item


def _base_item(
    *,
    key: str,
    type_: str,
    title: str,
    priority: str,
    detail: Dict[str, Any],
    drill: Dict[str, str],
    entity_code: Optional[str],
    period_ym: Optional[str],
    department_id: Optional[str],
    cost_center_id: Optional[str],
) -> Dict[str, Any]:
    raw = {
        "id": _stable_id(key),
        "action_key": key,
        "type": type_,
        "status": "open",
        "priority": priority,
        "score": _priority_score(priority),
        "title": title,
        "detail": detail,
        "drill": drill,
        "created_at": _now(),
        "updated_at": _now(),
    }
    return _enrich_item(
        raw,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )


async def _candidate_actions(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
    limit: int = 80,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    cq = merge_cases_master_filters(
        {"status": {"$ne": "closed"}},
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    cases = [c async for c in db.cases.find(cq, {"_id": 0}).sort("due_date", 1).limit(limit)]
    for c in cases:
        try:
            due = datetime.fromisoformat(c.get("due_date"))
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            if due >= now:
                continue
        except Exception:
            continue
        priority = _derive_priority_for_case(c)
        out.append(
            _base_item(
                key=f"case_overdue::{c.get('id')}",
                type_="case_overdue",
                title=f"Overdue case: {c.get('title', '')}",
                priority=priority,
                detail={
                    "case_id": c.get("id"),
                    "owner_email": c.get("owner_email"),
                    "due_date": c.get("due_date"),
                    "severity": c.get("severity"),
                    "entity": c.get("entity"),
                    "exposure": c.get("financial_exposure"),
                },
                drill={"route": f"/app/cases/{c.get('id')}"},
                entity_code=entity_code,
                period_ym=period_ym,
                department_id=department_id,
                cost_center_id=cost_center_id,
            )
        )

    ex_q = _scope_exceptions(
        {"status": {"$ne": "closed"}, "severity": {"$in": ["critical", "high"]}},
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    exc = [e async for e in db.exceptions.find(ex_q, {"_id": 0}).sort("financial_exposure", -1).limit(15)]
    for e in exc:
        priority = _derive_priority_for_exception(e)
        out.append(
            _base_item(
                key=f"exception_highrisk::{e.get('id')}",
                type_="exception_highrisk",
                title=f"High-risk exception: {e.get('title', '')}",
                priority=priority,
                detail={
                    "exception_id": e.get("id"),
                    "control_code": e.get("control_code"),
                    "severity": e.get("severity"),
                    "entity": e.get("entity"),
                    "process": e.get("process"),
                    "exposure": e.get("financial_exposure"),
                },
                drill={"route": f"/app/evidence/{e.get('id')}"},
                entity_code=entity_code,
                period_ym=period_ym,
                department_id=department_id,
                cost_center_id=cost_center_id,
            )
        )

    apr_q: Dict[str, Any] = {"status": "pending"}
    if entity_code:
        apr_q["entity"] = entity_code
    apr = [r async for r in db.approval_requests.find(apr_q, {"_id": 0}).sort("requested_at", -1).limit(15)]
    for r in apr:
        out.append(
            _base_item(
                key=f"approval_pending::{r.get('id')}",
                type_="approval_pending",
                title=f"Approval pending: {r.get('request_type')} · {r.get('subject_type')}",
                priority="P2",
                detail=r,
                drill={"route": "/app/approvals"},
                entity_code=entity_code,
                period_ym=period_ym,
                department_id=department_id,
                cost_center_id=cost_center_id,
            )
        )

    runs = [
        rr
        async for rr in db.connector_runs.find(
            {"status": {"$in": ["failed", "error"]}}, {"_id": 0}
        ).sort("started_at", -1).limit(10)
    ]
    for rr in runs:
        out.append(
            _base_item(
                key=f"connector_failed::{rr.get('id')}",
                type_="connector_failed",
                title=f"Connector run failed: {rr.get('connector_id')}",
                priority="P2",
                detail=rr,
                drill={"route": "/app/connectors"},
                entity_code=entity_code,
                period_ym=period_ym,
                department_id=department_id,
                cost_center_id=cost_center_id,
            )
        )

    from app.services.finance_team_service import _cycle_ids_for_entity, _cycle_scope_query

    cids = await _cycle_ids_for_entity(db, entity_code)
    close_q: Dict[str, Any] = {
        "critical": True,
        "status": {"$in": ["draft", "reopened", "submitted"]},
        **_cycle_scope_query(cids),
    }
    async for t in db.close_tasks.find(close_q, {"_id": 0}).limit(10):
        out.append(
            _base_item(
                key=f"close_critical_task::{t.get('id')}",
                type_="close_critical_task",
                title=f"Critical close task: {t.get('name', t.get('id'))}",
                priority="P0",
                detail={
                    "task_id": t.get("id"),
                    "cycle_id": t.get("cycle_id"),
                    "owner_email": t.get("owner_email"),
                    "status": t.get("status"),
                    "entity": entity_code,
                },
                drill={"route": "/app/finance-operations/month-end-close"},
                entity_code=entity_code,
                period_ym=period_ym,
                department_id=department_id,
                cost_center_id=cost_center_id,
            )
        )

    rq = recon_query(entity_code, period_ym)
    async for rec in db.reconciliations.find(rq or {}, {"_id": 0}).limit(200):
        if not is_overdue(rec, now=now):
            continue
        rid = rec.get("id")
        out.append(
            _base_item(
                key=f"reconciliation_overdue::{rid}",
                type_="reconciliation_overdue",
                title=f"Overdue reconciliation: {rec.get('recon_type', rid)}",
                priority="P1",
                detail={
                    "reconciliation_id": rid,
                    "entity": rec.get("entity"),
                    "due_date": rec.get("due_date"),
                    "status": rec.get("status"),
                },
                drill={"route": "/app/financial-audit/reconciliations-dashboard"},
                entity_code=entity_code,
                period_ym=period_ym,
                department_id=department_id,
                cost_center_id=cost_center_id,
            )
        )
        if sum(1 for x in out if x.get("type") == "reconciliation_overdue") >= 8:
            break

    try:
        from app.services import bank_recon_service as brs

        bank = await brs.build_summary(db, entity_code=entity_code, scan_limit=200)
        pending = int((bank.get("kpis") or {}).get("pending_signoff_count") or 0)
        if pending > 0:
            out.append(
                _base_item(
                    key=f"bank_signoff_pending::{entity_code or 'all'}",
                    type_="bank_signoff_pending",
                    title=f"Bank recon pending sign-off ({pending})",
                    priority="P1",
                    detail={"pending_signoff_count": pending, "entity": entity_code},
                    drill={"route": "/app/financial-audit/bank-reconciliation-dashboard"},
                    entity_code=entity_code,
                    period_ym=period_ym,
                    department_id=department_id,
                    cost_center_id=cost_center_id,
                )
            )
    except Exception:
        pass

    # Journal approval backlog — high/medium risk JEs without review
    try:
        from app.routers.journals_router import _fetch_scored_journals

        scored, _, _ = await _fetch_scored_journals(
            entity_code=entity_code, period_ym=period_ym, scan_limit=40
        )
        je_added = 0
        for j in scored:
            if j.get("risk_band") not in ("high", "medium") or j.get("reviewed"):
                continue
            je_id = j.get("id")
            if not je_id:
                continue
            pri = "P1" if j.get("risk_band") == "high" else "P2"
            out.append(
                _base_item(
                    key=f"journal_approval_backlog::{je_id}",
                    type_="journal_approval_backlog",
                    title=f"Journal review required: {j.get('je_number') or je_id}",
                    priority=pri,
                    detail={
                        "journal_id": je_id,
                        "risk_band": j.get("risk_band"),
                        "risk_score": j.get("risk_score"),
                        "entity": j.get("entity"),
                        "process": "Record-to-Report",
                        "exposure": j.get("total_amount") or j.get("amount"),
                    },
                    drill={"route": "/app/financial-audit/journal-risk"},
                    entity_code=entity_code,
                    period_ym=period_ym,
                    department_id=department_id,
                    cost_center_id=cost_center_id,
                )
            )
            je_added += 1
            if je_added >= 8:
                break
    except Exception:
        pass

    twq: Dict[str, Any] = {}
    if entity_code:
        twq["entity"] = entity_code
    tw_n = 0
    async for ex in db.three_way_match_exceptions.find(twq, {"_id": 0}).sort("created_at", -1).limit(12):
        ex_id = ex.get("id")
        if not ex_id:
            continue
        out.append(
            _base_item(
                key=f"three_way_match_failure::{ex_id}",
                type_="three_way_match_failure",
                title=f"3-way match exception: {ex.get('invoice_id') or ex_id}",
                priority="P1",
                detail={
                    **ex,
                    "process": "Procure-to-Pay",
                    "exposure": ex.get("variance_amount") or ex.get("amount"),
                },
                drill={"route": "/app/financial-audit/three-way-match"},
                entity_code=entity_code,
                period_ym=period_ym,
                department_id=department_id,
                cost_center_id=cost_center_id,
            )
        )
        tw_n += 1
        if tw_n >= 8:
            break

    try:
        from app.routers.access_router import _compute_sod_conflicts

        sod_added = 0
        for conflict in await _compute_sod_conflicts(entity_code=entity_code):
            if (conflict.get("severity") or "").lower() not in ("high", "critical", "medium"):
                continue
            cid = conflict.get("id")
            out.append(
                _base_item(
                    key=f"sod_violation::{cid}",
                    type_="sod_violation",
                    title=f"SoD conflict: {conflict.get('user_email')} · {conflict.get('rule_name')}",
                    priority="P1" if (conflict.get("severity") or "").lower() == "high" else "P2",
                    detail={
                        **conflict,
                        "process": "Access/SoD",
                        "exposure": 0,
                    },
                    drill={"route": "/app/governance/access-sod"},
                    entity_code=entity_code,
                    period_ym=period_ym,
                    department_id=department_id,
                    cost_center_id=cost_center_id,
                )
            )
            sod_added += 1
            if sod_added >= 8:
                break
    except Exception:
        pass

    pbq: Dict[str, Any] = {"status": "open"}
    if entity_code:
        pbq["entity"] = entity_code
    pol_n = 0
    async for breach in db.policy_breaches.find(pbq, {"_id": 0}).sort("detected_at", -1).limit(12):
        bid = breach.get("id")
        if not bid:
            continue
        sev = (breach.get("severity") or "medium").lower()
        pri = "P0" if sev == "critical" else ("P1" if sev == "high" else "P2")
        out.append(
            _base_item(
                key=f"policy_exception::{bid}",
                type_="policy_exception",
                title=f"Policy breach: {breach.get('policy_title') or bid}",
                priority=pri,
                detail={
                    **breach,
                    "process": "Policy compliance",
                    "exposure": breach.get("financial_exposure") or breach.get("amount"),
                },
                drill={"route": "/app/governance/policy-compliance"},
                entity_code=entity_code,
                period_ym=period_ym,
                department_id=department_id,
                cost_center_id=cost_center_id,
            )
        )
        pol_n += 1
        if pol_n >= 8:
            break

    try:
        from app.analytics import treasury_dashboard

        treasury = await treasury_dashboard(db, entity_code=entity_code, period_ym=period_ym)
        tk = treasury.get("kpis") or {}
        runway = tk.get("liquidity_runway_weeks")
        if runway is not None:
            try:
                rw = float(runway)
            except (TypeError, ValueError):
                rw = None
            if rw is not None and rw < 8:
                out.append(
                    _base_item(
                        key=f"treasury_alert::runway::{entity_code or 'all'}",
                        type_="treasury_alert",
                        title=f"Treasury alert: liquidity runway {rw:.1f} weeks",
                        priority="P0" if rw < 4 else "P1",
                        detail={
                            "liquidity_runway_weeks": rw,
                            "entity": entity_code,
                            "process": "Treasury",
                            "exposure": tk.get("net_debt") or 0,
                        },
                        drill={"route": "/app/treasury"},
                        entity_code=entity_code,
                        period_ym=period_ym,
                        department_id=department_id,
                        cost_center_id=cost_center_id,
                    )
                )
        fxq: Dict[str, Any] = {}
        if entity_code:
            fxq["entity"] = entity_code
        unhedged_total = 0.0
        async for fx in db.fx_exposures.find(fxq, {"_id": 0}).limit(100):
            gross = float(fx.get("notional_base") or 0)
            pair = fx.get("currency_pair") or fx.get("pair")
            hedged = 0.0
            async for h in db.fx_hedges.find({**fxq, "currency_pair": pair}, {"_id": 0, "notional_base": 1}).limit(20):
                hedged += float(h.get("notional_base") or 0)
            unhedged_total += max(gross - hedged, 0.0)
        if unhedged_total >= 500_000:
            out.append(
                _base_item(
                    key=f"treasury_alert::fx::{entity_code or 'all'}",
                    type_="treasury_alert",
                    title=f"FX unhedged exposure {unhedged_total:,.0f} base",
                    priority="P1",
                    detail={
                        "unhedged_base": round(unhedged_total, 2),
                        "entity": entity_code,
                        "process": "Treasury",
                        "exposure": unhedged_total,
                    },
                    drill={"route": "/app/treasury/forex-exposure"},
                    entity_code=entity_code,
                    period_ym=period_ym,
                    department_id=department_id,
                    cost_center_id=cost_center_id,
                )
            )
    except Exception:
        pass

    out.sort(key=lambda x: (x.get("score", 999), -float(x.get("materiality_score") or 0)))
    return out[:limit]


async def refresh_action_queue(
    db,
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
) -> Dict[str, Any]:
    items = await _candidate_actions(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    upserted = 0
    for it in items:
        existing = await db.cfo_action_queue.find_one({"id": it["id"]}, {"_id": 0, "status": 1, "events": 1})
        if existing and existing.get("status") in ("approved", "rejected"):
            continue
        if existing:
            it["status"] = existing.get("status", it["status"])
            it["events"] = existing.get("events") or []
        await db.cfo_action_queue.update_one({"id": it["id"]}, {"$set": it}, upsert=True)
        upserted += 1
    scope_q = scope_filters(
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    total = await db.cfo_action_queue.count_documents(scope_q or {})
    return {"items": items, "upserted": upserted, "total_materialized": total}


async def list_queue(
    db,
    *,
    limit: int = 100,
    offset: int = 0,
    cursor: Optional[str] = None,
    status: Optional[str] = None,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
    process: Optional[str] = None,
    priority: Optional[str] = None,
    action_type: Optional[str] = None,
    assignee_email: Optional[str] = None,
    sort: str = "score",
) -> Dict[str, Any]:
    q = scope_filters(
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
        process=process,
        status=status,
        priority=priority,
        action_type=action_type,
        assignee_email=assignee_email,
    )
    base_q = dict(q or {})
    cur_data = decode_cursor(cursor)
    if cur_data and cur_data.get("sort") == sort:
        keyset = _keyset_clause(sort, cur_data)
        if keyset:
            base_q = {"$and": [base_q, keyset]} if base_q else keyset
    total = await db.cfo_action_queue.count_documents(q or {})
    sort_spec = SORT_FIELDS.get(sort, SORT_FIELDS["score"])
    use_cursor = bool(cur_data and cur_data.get("sort") == sort)
    if use_cursor:
        cur = db.cfo_action_queue.find(base_q, {"_id": 0}).sort(sort_spec).limit(limit + 1)
    else:
        cur = (
            db.cfo_action_queue.find(base_q, {"_id": 0})
            .sort(sort_spec)
            .skip(offset)
            .limit(limit + 1)
        )
    rows = [r async for r in cur]
    has_more = len(rows) > limit
    items = rows[:limit]
    now = datetime.now(timezone.utc)
    for it in items:
        it["age_days"] = round(_age_days(it.get("created_at"), now=now), 1)
        it["sla_breached"] = is_sla_breached(it, it["age_days"])
    next_cursor = None
    if has_more and items:
        last = items[-1]
        det = last.get("detail") or {}
        next_cursor = encode_cursor(
            {
                "sort": sort,
                "id": last.get("id"),
                "score": last.get("score"),
                "materiality_score": last.get("materiality_score"),
                "created_at": last.get("created_at"),
                "detail.exposure": det.get("exposure") or det.get("financial_exposure"),
            }
        )
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset if not use_cursor else 0,
        "sort": sort,
        "next_cursor": next_cursor,
        "has_more": has_more,
    }


async def get_action(db, action_id: str) -> Optional[Dict[str, Any]]:
    doc = await db.cfo_action_queue.find_one({"id": action_id}, {"_id": 0})
    if doc:
        doc["age_days"] = round(_age_days(doc.get("created_at")), 1)
        doc["sla_breached"] = is_sla_breached(doc, doc["age_days"])
    return doc


async def _update_status(
    db,
    action_id: str,
    *,
    status: str,
    actor: str,
    note: str = "",
    reject_reason: Optional[str] = None,
) -> Dict[str, Any]:
    now = _now()
    patch: Dict[str, Any] = {"status": status, "updated_at": now, "updated_by": actor}
    if note:
        patch["last_note"] = note
    if reject_reason:
        patch["reject_reason"] = reject_reason
    await db.cfo_action_queue.update_one({"id": action_id}, {"$set": patch})
    evt: Dict[str, Any] = {"at": now, "actor": actor, "type": status, "note": note}
    if reject_reason:
        evt["reject_reason"] = reject_reason
    await db.cfo_action_queue.update_one({"id": action_id}, {"$push": {"events": evt}})
    return await get_action(db, action_id)


async def approve(db, action_id: str, *, actor: str, note: str = "") -> Dict[str, Any]:
    return await _update_status(db, action_id, status="approved", actor=actor, note=note)


async def reject(
    db,
    action_id: str,
    *,
    actor: str,
    note: str = "",
    reject_reason: Optional[str] = None,
) -> Dict[str, Any]:
    return await _update_status(
        db,
        action_id,
        status="rejected",
        actor=actor,
        note=note,
        reject_reason=reject_reason,
    )


async def escalate(db, action_id: str, *, actor: str, note: str = "") -> Dict[str, Any]:
    return await _update_status(db, action_id, status="escalated", actor=actor, note=note)


async def reopen(db, action_id: str, *, actor: str, note: str = "") -> Dict[str, Any]:
    return await _update_status(db, action_id, status="open", actor=actor, note=note)


async def comment(db, action_id: str, *, actor: str, comment_text: str) -> Dict[str, Any]:
    now = _now()
    await db.cfo_action_queue.update_one(
        {"id": action_id},
        {"$push": {"comments": {"at": now, "actor": actor, "text": comment_text}}},
    )
    await db.cfo_action_queue.update_one(
        {"id": action_id},
        {"$set": {"updated_at": now, "updated_by": actor}},
    )
    return await get_action(db, action_id)


async def bulk_action(
    db,
    *,
    action_ids: List[str],
    action: str,
    actor: str,
    note: str = "",
    reject_reason: Optional[str] = None,
) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    for aid in action_ids:
        try:
            if action == "approve":
                doc = await approve(db, aid, actor=actor, note=note)
            elif action == "reject":
                doc = await reject(db, aid, actor=actor, note=note, reject_reason=reject_reason)
            elif action == "escalate":
                doc = await escalate(db, aid, actor=actor, note=note)
            else:
                results.append({"id": aid, "ok": False, "error": f"unknown action {action}"})
                continue
            results.append({"id": aid, "ok": True, "status": doc.get("status")})
        except Exception as exc:
            results.append({"id": aid, "ok": False, "error": str(exc)})
    ok = sum(1 for r in results if r.get("ok"))
    return {"results": results, "succeeded": ok, "failed": len(results) - ok}


def export_xlsx_bytes(items: List[Dict[str, Any]]) -> bytes:
    from io import BytesIO

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Action Queue"
    headers = [
        "id",
        "type",
        "status",
        "priority",
        "title",
        "entity",
        "process",
        "exposure",
        "age_days",
        "materiality_score",
        "sla_breached",
    ]
    ws.append(headers)
    for it in items:
        det = it.get("detail") or {}
        exp = det.get("exposure") or det.get("financial_exposure") or ""
        ws.append(
            [
                it.get("id"),
                it.get("type"),
                it.get("status"),
                it.get("priority"),
                it.get("title"),
                it.get("entity") or det.get("entity"),
                it.get("process") or det.get("process"),
                exp,
                it.get("age_days"),
                it.get("materiality_score"),
                it.get("sla_breached"),
            ]
        )
    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()


def export_csv_rows(items: List[Dict[str, Any]]) -> str:
    lines = ["id,type,status,priority,title,entity,process,exposure,age_days,materiality_score"]
    for it in items:
        det = it.get("detail") or {}
        exp = det.get("exposure") or ""
        lines.append(
            ",".join(
                [
                    str(it.get("id", "")),
                    str(it.get("type", "")),
                    str(it.get("status", "")),
                    str(it.get("priority", "")),
                    '"' + str(it.get("title", "")).replace('"', "'") + '"',
                    str(it.get("entity") or det.get("entity") or ""),
                    str(it.get("process") or det.get("process") or ""),
                    str(exp),
                    str(it.get("age_days", "")),
                    str(it.get("materiality_score", "")),
                ]
            )
        )
    return "\n".join(lines)
