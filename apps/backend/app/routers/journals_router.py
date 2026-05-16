"""Phase 16 — Journal Entry Risk Scoring (seed-backed)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.connectors.adapters._normalize import normalize_journal
from app.deps import audit_log, db
from app.services.kpi_service import as_of_now
from app.services.rbac_service import enforce_entity_scope


router = APIRouter(prefix="/journals", tags=["journals"])


DEFAULT_RULES: List[Dict[str, Any]] = [
    {
        "id": "JR-001",
        "name": "Manual JE above threshold",
        "weight": 40,
        "type": "threshold",
        "field": "total_amount",
        "op": ">=",
        "value": 100000,
        "when": {"is_manual": True},
    },
    {
        "id": "JR-002",
        "name": "Backdated posting (created after posting date by many days)",
        "weight": 35,
        "type": "date_diff_days",
        "posting_field": "posting_date",
        "created_field": "created_at",
        "min_days": 10,
    },
    {
        "id": "JR-003",
        "name": "Privileged user posted JE",
        "weight": 25,
        "type": "flag",
        "field": "is_privileged_poster",
        "value": True,
    },
    {
        "id": "JR-004",
        "name": "Missing approver on material JE",
        "weight": 20,
        "type": "missing",
        "field": "approver_email",
        "when": {"is_manual": True},
    },
]


async def _get_rules() -> List[Dict[str, Any]]:
    existing = [r async for r in db.journal_risk_rules.find({}, {"_id": 0}).sort("id", 1)]
    if existing:
        return existing
    # Seed-on-first-use for stable behavior.
    await db.journal_risk_rules.insert_many([dict(r, created_at=as_of_now()) for r in DEFAULT_RULES])
    return [r async for r in db.journal_risk_rules.find({}, {"_id": 0}).sort("id", 1)]


def _parse_dt(s: Any) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:  # noqa: BLE001
        return None


def _matches_when(je: Dict[str, Any], when: Dict[str, Any]) -> bool:
    for k, v in (when or {}).items():
        if je.get(k) != v:
            return False
    return True


def _scored_journal(je: Dict[str, Any], rules: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalize ERP/seed aliases then attach risk_score, risk_band, hits."""
    norm = normalize_journal(je)
    return {**norm, **_score_je(norm, rules)}


def _score_je(je: Dict[str, Any], rules: List[Dict[str, Any]]) -> Dict[str, Any]:
    score = 0
    hits = []
    for r in rules:
        if r.get("when") and not _matches_when(je, r["when"]):
            continue
        rtype = r.get("type")
        ok = False
        if rtype == "threshold":
            val = float(je.get(r.get("field")) or 0.0)
            thr = float(r.get("value") or 0.0)
            ok = val >= thr if r.get("op") == ">=" else val > thr
        elif rtype == "flag":
            ok = je.get(r.get("field")) == r.get("value")
        elif rtype == "missing":
            ok = je.get(r.get("field")) in (None, "", [])
        elif rtype == "date_diff_days":
            p = _parse_dt(je.get(r.get("posting_field")))
            c = _parse_dt(je.get(r.get("created_field")))
            if p and c:
                ok = (c - p).days >= int(r.get("min_days") or 0)
        if ok:
            w = int(r.get("weight") or 0)
            score += w
            hits.append({"rule_id": r.get("id"), "name": r.get("name"), "weight": w})
    score = min(100, max(0, score))
    band = "low" if score < 30 else "medium" if score < 60 else "high"
    return {"risk_score": score, "risk_band": band, "hits": hits}


def _backdated_days(je: Dict[str, Any]) -> int:
    posting = _parse_dt(je.get("posting_date"))
    created = _parse_dt(je.get("created_at"))
    if posting and created:
        return max(0, (created - posting).days)
    return 0


async def _reviewed_je_ids(je_ids: List[str]) -> set[str]:
    if not je_ids:
        return set()
    reviewed: set[str] = set()
    async for rev in db.journal_reviews.find({"je_id": {"$in": je_ids}}, {"je_id": 1, "_id": 0}):
        je_id = rev.get("je_id")
        if je_id:
            reviewed.add(str(je_id))
    return reviewed


def _enrich_scored_row(scored: Dict[str, Any], reviewed_ids: set[str]) -> Dict[str, Any]:
    hits = scored.get("hits") or []
    je_id = str(scored.get("id") or "")
    return {
        **scored,
        "hit_count": len(hits),
        "rules_hit": [h.get("rule_id") for h in hits if h.get("rule_id")],
        "backdated_days": _backdated_days(scored),
        "reviewed": je_id in reviewed_ids,
    }


def _journal_query(entity_code: Optional[str], period_ym: Optional[str]) -> Dict[str, Any]:
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    if period_ym and str(period_ym).strip():
        q["posting_date"] = {"$regex": f"^{str(period_ym).strip()}"}
    return q


async def _fetch_scored_journals(
    *,
    entity_code: Optional[str],
    period_ym: Optional[str],
    scan_limit: int,
) -> tuple[List[Dict[str, Any]], int, List[Dict[str, Any]]]:
    q = _journal_query(entity_code, period_ym)
    cur = db.journals.find(q, {"_id": 0}).sort("posting_date", -1).limit(scan_limit)
    items = [j async for j in cur]
    total = await db.journals.count_documents(q)
    rules = await _get_rules()
    reviewed_ids = await _reviewed_je_ids([str(j.get("id")) for j in items if j.get("id")])
    scored = [_enrich_scored_row(_scored_journal(j, rules), reviewed_ids) for j in items]
    return scored, total, rules


def _build_risk_summary(
    scored: List[Dict[str, Any]],
    total: int,
    rules: List[Dict[str, Any]],
    reviewed_ids: set[str],
) -> Dict[str, Any]:
    high = [j for j in scored if j.get("risk_band") == "high"]
    medium = [j for j in scored if j.get("risk_band") == "medium"]
    low = [j for j in scored if j.get("risk_band") == "low"]
    scores = [int(j.get("risk_score") or 0) for j in scored]

    rule_hit_counts: Dict[str, int] = {}
    rule_names = {str(r.get("id")): r.get("name") for r in rules}
    rule_weights = {str(r.get("id")): r.get("weight") for r in rules}
    for j in scored:
        for h in j.get("hits") or []:
            rid = h.get("rule_id")
            if rid:
                rule_hit_counts[str(rid)] = rule_hit_counts.get(str(rid), 0) + 1

    rule_hits: List[Dict[str, Any]] = []
    seen_rules = set(rule_hit_counts.keys())
    for rid, cnt in sorted(rule_hit_counts.items(), key=lambda kv: -kv[1]):
        rule_hits.append(
            {
                "rule_id": rid,
                "name": rule_names.get(rid),
                "weight": rule_weights.get(rid),
                "hit_count": cnt,
            }
        )
    for r in rules:
        rid = str(r.get("id"))
        if rid not in seen_rules:
            rule_hits.append(
                {"rule_id": rid, "name": r.get("name"), "weight": r.get("weight"), "hit_count": 0}
            )

    top_firing = rule_hits[0] if rule_hits and int(rule_hits[0].get("hit_count") or 0) > 0 else None

    poster_stats: Dict[str, Dict[str, Any]] = {}
    for j in high:
        by = str(j.get("created_by") or "unknown")
        if by not in poster_stats:
            poster_stats[by] = {"created_by": by, "high_risk_count": 0, "high_risk_amount": 0.0}
        poster_stats[by]["high_risk_count"] += 1
        poster_stats[by]["high_risk_amount"] += float(j.get("total_amount") or 0.0)
    top_posters = sorted(poster_stats.values(), key=lambda x: -float(x.get("high_risk_amount") or 0.0))[:5]

    manual = [j for j in scored if j.get("is_manual")]
    backdated = [j for j in scored if int(j.get("backdated_days") or 0) >= 10]
    missing_appr = [j for j in scored if j.get("is_manual") and j.get("approver_email") in (None, "", [])]
    privileged = [j for j in scored if j.get("is_privileged_poster")]
    unreviewed_high = sum(1 for j in high if str(j.get("id") or "") not in reviewed_ids)

    scanned = len(scored)
    pct_high = round(100.0 * len(high) / scanned, 1) if scanned else 0.0

    return {
        "kpis": {
            "total_journals": total,
            "scanned": scanned,
            "active_rules": len(rules),
            "high_count": len(high),
            "medium_count": len(medium),
            "low_count": len(low),
            "pct_high": pct_high,
            "high_risk_amount": round(sum(float(j.get("total_amount") or 0.0) for j in high), 2),
            "medium_risk_amount": round(sum(float(j.get("total_amount") or 0.0) for j in medium), 2),
            "manual_count": len(manual),
            "manual_amount": round(sum(float(j.get("total_amount") or 0.0) for j in manual), 2),
            "unreviewed_high_count": unreviewed_high,
            "backdated_count": len(backdated),
            "missing_approver_count": len(missing_appr),
            "privileged_poster_count": len(privileged),
            "avg_risk_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
            "max_risk_score": max(scores) if scores else 0,
            "top_rule_id": top_firing.get("rule_id") if top_firing else None,
            "top_rule_hits": int(top_firing.get("hit_count") or 0) if top_firing else 0,
        },
        "rule_hits": rule_hits,
        "top_posters": top_posters,
        "bands": {"high": len(high), "medium": len(medium), "low": len(low)},
    }


@router.get("")
async def journals_list(
    entity_code: Optional[str] = Query(None),
    is_manual: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current=Depends(get_current_user),
):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    q = _journal_query(entity_code, None)
    if is_manual is not None:
        q["is_manual"] = is_manual
    cur = db.journals.find(q, {"_id": 0}).sort("posting_date", -1).skip(offset).limit(limit)
    items = [j async for j in cur]
    total = await db.journals.count_documents(q)
    rules = await _get_rules()
    reviewed_ids = await _reviewed_je_ids([str(j.get("id")) for j in items if j.get("id")])
    scored = [_enrich_scored_row(_scored_journal(j, rules), reviewed_ids) for j in items]
    return {"items": scored, "total": total, "limit": limit, "offset": offset, "as_of": as_of_now()}


@router.get("/high-risk")
async def journals_high_risk(
    entity_code: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    current=Depends(get_current_user),
):
    data = await journals_list(entity_code=entity_code, is_manual=None, limit=500, offset=0, current=current)
    items = sorted(data["items"], key=lambda j: -int(j.get("risk_score") or 0))[:limit]
    return {"items": items, "count": len(items), "as_of": as_of_now(), "source": "computed"}

@router.get("/risk-rules")
async def journal_risk_rules(current=Depends(get_current_user)):
    rules = await _get_rules()
    return {"items": rules, "count": len(rules), "as_of": as_of_now()}


@router.get("/risk-summary")
async def journals_risk_summary(
    entity_code: Optional[str] = Query(None),
    period_ym: Optional[str] = Query(None),
    scan_limit: int = Query(2000, ge=1, le=5000),
    current=Depends(get_current_user),
):
    """Aggregated journal risk KPIs, rule hit counts, and top posters for the workbench."""
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    scored, total, rules = await _fetch_scored_journals(
        entity_code=entity_code,
        period_ym=period_ym,
        scan_limit=scan_limit,
    )
    reviewed_ids = await _reviewed_je_ids([str(j.get("id")) for j in scored if j.get("id")])
    summary = _build_risk_summary(scored, total, rules, reviewed_ids)
    return {
        **summary,
        "entity_code": entity_code,
        "period_ym": period_ym,
        "scan_limit": scan_limit,
        "as_of": as_of_now(),
    }


@router.post("/risk-rules")
async def journal_risk_rules_upsert(body: Dict[str, Any], current=Depends(get_current_user)):
    rid = body.get("id") or f"JR-{__import__('uuid').uuid4().hex[:6].upper()}"
    doc = {**body, "id": rid, "updated_at": as_of_now(), "updated_by": current.get("email")}
    await db.journal_risk_rules.update_one({"id": rid}, {"$set": doc, "$setOnInsert": {"created_at": as_of_now()}}, upsert=True)
    await audit_log(current["email"], "journal_risk_rule_upsert", "journal_risk_rule", rid, {"name": body.get("name")})
    return {"status": "ok", "rule_id": rid, "as_of": as_of_now()}


@router.get("/{je_id}")
async def journal_detail(je_id: str, current=Depends(get_current_user)):
    doc = await db.journals.find_one({"id": je_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Journal entry not found")
    if doc.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=doc.get("entity"))
    rules = await _get_rules()
    return {**_scored_journal(doc, rules), "as_of": as_of_now()}


@router.post("/{je_id}/review")
async def journal_review(je_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    je = await db.journals.find_one({"id": je_id}, {"_id": 0, "entity": 1})
    if not je:
        raise HTTPException(404, "Journal entry not found")
    if je.get("entity"):
        await enforce_entity_scope(db, current=current, requested_entity_code=je.get("entity"))
    # Persist review decision separately (journals are seed-like immutable docs).
    decision = str(body.get("decision") or "reviewed")
    note = body.get("note")
    doc = {"id": f"rev-{__import__('uuid').uuid4().hex[:10]}", "je_id": je_id, "decision": decision, "note": note, "by": current.get("email"), "at": as_of_now()}
    await db.journal_reviews.insert_one(dict(doc))
    await audit_log(current["email"], "journal_review", "journal", je_id, {"decision": decision})
    return {"status": "ok", "review_id": doc["id"], "as_of": as_of_now()}


@router.post("/sample")
async def journal_sample(body: Dict[str, Any], current=Depends(get_current_user)):
    """Return a simple sample set for audit testing.

    Input: { "n": 20, "entity_code": "...", "risk_band": "high|medium|low" }
    """
    n = int(body.get("n") or 20)
    entity_code = body.get("entity_code")
    if entity_code and str(entity_code).strip():
        entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=str(entity_code))
    risk_band = body.get("risk_band")
    data = await journals_list(entity_code=entity_code, is_manual=None, limit=500, offset=0, current=current)
    items = data["items"]
    if risk_band:
        items = [i for i in items if i.get("risk_band") == risk_band]
    # deterministic sample: top by risk_score then take first n
    items = sorted(items, key=lambda j: (-int(j.get("risk_score") or 0), str(j.get("id"))))[:n]
    sid = f"samp-{__import__('uuid').uuid4().hex[:10]}"
    await db.journal_samples.insert_one({"id": sid, "n": n, "entity_code": entity_code, "risk_band": risk_band, "items": [i.get("id") for i in items], "created_at": as_of_now(), "created_by": current.get("email")})
    await audit_log(current["email"], "journal_sample", "journal_sample", sid, {"n": n, "risk_band": risk_band})
    return {"sample_id": sid, "items": items, "count": len(items), "as_of": as_of_now()}

