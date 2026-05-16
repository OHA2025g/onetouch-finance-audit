"""Audit workspace aggregates: summary KPIs, trends, heatmap (Finance Operations /app/audit)."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.analytics import _scope_exceptions, compute_readiness

_STALE_DAYS_BY_FREQUENCY: Dict[str, int] = {
    "daily": 2,
    "weekly": 10,
    "monthly": 35,
    "quarterly": 100,
}
_DEFAULT_STALE_DAYS = 14


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def control_is_stale(control: Dict[str, Any], *, now: Optional[datetime] = None) -> bool:
    """True when last run is missing or older than frequency-based threshold."""
    at = _parse_iso(control.get("last_run_at"))
    if not at:
        return False
    ref = now or datetime.now(timezone.utc)
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    freq = str(control.get("frequency") or "").strip().lower()
    limit = _STALE_DAYS_BY_FREQUENCY.get(freq, _DEFAULT_STALE_DAYS)
    return (ref - at).days > limit


def catalog_pass_fail_not_run(controls: List[Dict[str, Any]]) -> Dict[str, int]:
    passed = failed = not_run = 0
    for c in controls:
        if not c.get("last_run_at"):
            not_run += 1
        elif c.get("last_run_pass") is True:
            passed += 1
        elif c.get("last_run_pass") is False:
            failed += 1
        else:
            not_run += 1
    return {"pass": passed, "fail": failed, "not_run": not_run}


def catalog_stale_count(controls: List[Dict[str, Any]]) -> int:
    return sum(1 for c in controls if control_is_stale(c))


def catalog_critical_failing_count(controls: List[Dict[str, Any]]) -> int:
    crit_levels = {"critical", "high"}
    n = 0
    for c in controls:
        if str(c.get("criticality") or "").lower() not in crit_levels:
            continue
        if c.get("last_run_pass") is False:
            n += 1
    return n


async def build_audit_workspace_summary(
    db,
    controls: List[Dict[str, Any]],
    *,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Scoped exception aggregates + catalog stats for audit workspace header/charts."""
    readiness_rows = await compute_readiness(
        db,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    audit_readiness_pct = round(
        sum(r["readiness"] for r in readiness_rows) / max(1, len(readiness_rows)), 1
    )

    open_q = _scope_exceptions(
        {"status": {"$ne": "closed"}},
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )
    open_exceptions_count = await db.exceptions.count_documents(open_q if open_q else {})

    open_exposure_usd = 0.0
    async for ex in db.exceptions.find(open_q if open_q else {}, {"_id": 0, "financial_exposure": 1}):
        open_exposure_usd += float(ex.get("financial_exposure") or 0)

    catalog_by_process: Dict[str, int] = defaultdict(int)
    for c in controls:
        catalog_by_process[str(c.get("process") or "Unknown")] += 1

    per_control: Dict[str, int] = defaultdict(int)
    per_control_exposure: Dict[str, float] = defaultdict(float)
    by_process: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"open_count": 0, "open_exposure_usd": 0.0})
    by_severity: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"open_count": 0, "open_exposure_usd": 0.0})
    heatmap: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    heatmap_fail: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for c in controls:
        if c.get("last_run_pass") is False:
            proc = str(c.get("process") or "Unknown")
            sev = str(c.get("criticality") or "medium")
            heatmap_fail[proc][sev] += 1

    async for ex in db.exceptions.find(open_q if open_q else {}, {"_id": 0}):
        code = ex.get("control_code") or ""
        if code:
            per_control[code] += 1
            per_control_exposure[code] += float(ex.get("financial_exposure") or 0)
        proc = ex.get("process") or "Unknown"
        sev = ex.get("severity") or "medium"
        exp = float(ex.get("financial_exposure") or 0)
        by_process[proc]["open_count"] += 1
        by_process[proc]["open_exposure_usd"] += exp
        by_severity[sev]["open_count"] += 1
        by_severity[sev]["open_exposure_usd"] += exp
        heatmap[proc][sev] += 1

    top_failing = sorted(per_control.items(), key=lambda kv: -kv[1])[:6]
    top_failing_out: List[Dict[str, Any]] = []
    for code, count in top_failing:
        c = await db.controls.find_one({"code": code}, {"_id": 0})
        if c:
            top_failing_out.append({
                "id": c.get("id"),
                "code": code,
                "name": c.get("name"),
                "process": c.get("process"),
                "exceptions": count,
                "open_exposure_usd": round(per_control_exposure.get(code, 0.0), 2),
                "criticality": c.get("criticality"),
            })

    process_names = set(catalog_by_process.keys()) | set(by_process.keys())
    by_process_out = []
    for proc in sorted(process_names, key=lambda p: (-by_process[p]["open_count"] if p in by_process else 0, p)):
        exc = by_process.get(proc, {"open_count": 0, "open_exposure_usd": 0.0})
        by_process_out.append({
            "process": proc,
            "open_count": int(exc["open_count"]),
            "open_exposure_usd": round(float(exc["open_exposure_usd"]), 2),
            "control_count": int(catalog_by_process.get(proc, 0)),
        })
    by_process_out.sort(key=lambda row: -row["open_count"])

    by_severity_out = [
        {
            "severity": sev,
            "open_count": int(v["open_count"]),
            "open_exposure_usd": round(float(v["open_exposure_usd"]), 2),
        }
        for sev, v in sorted(by_severity.items(), key=lambda kv: -kv[1]["open_count"], reverse=True)
    ]

    heatmap_keys = set(heatmap.keys()) | set(heatmap_fail.keys())
    heatmap_out: List[Dict[str, Any]] = []
    for proc in sorted(heatmap_keys):
        sev_keys = set(heatmap[proc].keys()) | set(heatmap_fail[proc].keys())
        for sev in sorted(sev_keys, key=lambda s: {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(s, 0), reverse=True):
            open_cnt = int(heatmap[proc].get(sev, 0))
            fail_cnt = int(heatmap_fail[proc].get(sev, 0))
            if open_cnt or fail_cnt:
                heatmap_out.append({
                    "process": proc,
                    "criticality": sev,
                    "open_count": open_cnt,
                    "fail_count": fail_cnt,
                })

    pfn = catalog_pass_fail_not_run(controls)
    ran = pfn["pass"] + pfn["fail"]
    pass_rate_pct = round(100.0 * pfn["pass"] / ran, 1) if ran else 0.0

    return {
        "audit_readiness_pct": audit_readiness_pct,
        "open_exceptions_count": open_exceptions_count,
        "open_exposure_usd": round(open_exposure_usd, 2),
        "pass_fail_not_run": pfn,
        "pass_rate_pct": pass_rate_pct,
        "stale_control_count": catalog_stale_count(controls),
        "critical_failing_count": catalog_critical_failing_count(controls),
        "by_process": by_process_out,
        "by_severity": by_severity_out,
        "top_failing_controls": top_failing_out,
        "heatmap": heatmap_out,
        "control_count": len(controls),
    }


async def build_audit_workspace_trends(
    db,
    *,
    days: int = 30,
    entity_code: Optional[str] = None,
    period_ym: Optional[str] = None,
    department_id: Optional[str] = None,
    cost_center_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Daily buckets for new open exceptions and failed control runs."""
    days = max(7, min(int(days), 90))
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days - 1)

    series_map: Dict[str, Dict[str, int]] = {}
    for i in range(days):
        d = (start + timedelta(days=i)).date().isoformat()
        series_map[d] = {"new_exceptions": 0, "failed_runs": 0, "exceptions_closed": 0}

    open_base = _scope_exceptions(
        None,
        entity_code=entity_code,
        period_ym=period_ym,
        department_id=department_id,
        cost_center_id=cost_center_id,
    )

    async for ex in db.exceptions.find(open_base if open_base else {}, {"_id": 0, "detected_at": 1, "status": 1}):
        dt = _parse_iso(ex.get("detected_at"))
        if not dt:
            continue
        key = dt.date().isoformat()
        if key in series_map:
            series_map[key]["new_exceptions"] += 1
        if ex.get("status") == "closed":
            closed_dt = _parse_iso(ex.get("closed_at") if ex.get("closed_at") else ex.get("detected_at"))
            if closed_dt:
                ckey = closed_dt.date().isoformat()
                if ckey in series_map:
                    series_map[ckey]["exceptions_closed"] += 1

    run_q: Dict[str, Any] = {"status": {"$ne": "pass"}}
    if period_ym:
        run_q["run_ts"] = {"$regex": f"^{period_ym}"}
    if entity_code:
        run_q["entities"] = entity_code
    async for run in db.test_runs.find(run_q, {"_id": 0, "run_ts": 1, "exceptions_count": 1, "status": 1}):
        dt = _parse_iso(run.get("run_ts"))
        if not dt:
            continue
        key = dt.date().isoformat()
        if key in series_map and (run.get("exceptions_count") or 0) > 0:
            series_map[key]["failed_runs"] += 1

    series = [{"date": d, **series_map[d]} for d in sorted(series_map.keys())]
    filters_applied = {k: v for k, v in {
        "entity_code": entity_code,
        "period_ym": period_ym,
        "department_id": department_id,
        "cost_center_id": cost_center_id,
        "days": days,
    }.items() if v is not None and v != ""}
    return {"series": series, "filters_applied": filters_applied, "days": days}
