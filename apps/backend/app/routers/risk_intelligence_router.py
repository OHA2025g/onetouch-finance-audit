"""Phase 36 — Finance Risk Intelligence Scoring (seed-friendly).

Stores computed scores in `finance_risk_scores` for dashboard aggregation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.deps import audit_log, db
from app.services.kpi_service import as_of_now


router = APIRouter(prefix="/risk-intelligence", tags=["risk-intelligence"])


def _now() -> str:
    return as_of_now()


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


async def _ensure_seed_risk_scores(entity_code: Optional[str] = None) -> Dict[str, Any]:
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity_code"] = entity_code
    if await db.finance_risk_scores.count_documents(q) > 0:
        return {"status": "already_present"}
    out = await _recompute_scores(entity_code=entity_code, limit_per_type=50)
    return {"status": "seeded", **out}


def _score_from_factors(factors: List[Dict[str, Any]]) -> Tuple[float, str]:
    s = 0.0
    for f in factors:
        s += float(f.get("weight") or 0.0) * float(f.get("value") or 0.0)
    s = _clamp01(s)
    band = "high" if s >= 0.75 else "medium" if s >= 0.4 else "low"
    return s, band


async def _recompute_scores(*, entity_code: Optional[str], limit_per_type: int = 50) -> Dict[str, Any]:
    """Compute risk scores across seeded objects and upsert into finance_risk_scores."""
    now = _now()
    upserts = 0

    async def upsert(row: Dict[str, Any]) -> None:
        nonlocal upserts
        nk = f"{row['object_type']}::{row['object_id']}"
        row["natural_key"] = nk
        row["computed_at"] = now
        await db.finance_risk_scores.update_one({"natural_key": nk}, {"$set": dict(row)}, upsert=True)
        upserts += 1

    # --- Vendors ---
    vq: Dict[str, Any] = {"entity": entity_code} if entity_code else {}
    vendors = [v async for v in db.vendors.find(vq, {"_id": 0}).limit(limit_per_type)]
    for v in vendors:
        factors = []
        if not (v.get("pan") or v.get("gstin")):
            factors.append({"key": "missing_tax_id", "value": 1.0, "weight": 0.35})
        if not v.get("ifsc"):
            factors.append({"key": "missing_ifsc", "value": 1.0, "weight": 0.15})
        ytd = float(v.get("ytd_spend") or 0.0)
        factors.append({"key": "spend_scale", "value": _clamp01(ytd / 1_000_000.0), "weight": 0.25})
        s, band = _score_from_factors(factors)
        await upsert(
            {
                "entity_code": v.get("entity"),
                "object_type": "vendor",
                "object_id": v.get("id"),
                "object_label": v.get("vendor_name") or v.get("vendor_code") or v.get("id"),
                "score": round(s, 4),
                "band": band,
                "factors": factors,
            }
        )

    # --- Customers ---
    cq: Dict[str, Any] = {"entity": entity_code} if entity_code else {}
    customers = [c async for c in db.customers.find(cq, {"_id": 0}).limit(limit_per_type)]
    for c in customers:
        factors = []
        if not c.get("gstin"):
            factors.append({"key": "missing_gstin", "value": 1.0, "weight": 0.15})
        cl = c.get("credit_limit")
        try:
            if cl is not None and float(cl) < 0:
                factors.append({"key": "negative_credit_limit", "value": 1.0, "weight": 0.35})
        except Exception:  # noqa: BLE001
            pass
        exposure = float(c.get("ar_open_amount") or 0.0)
        factors.append({"key": "exposure_scale", "value": _clamp01(exposure / 500_000.0), "weight": 0.25})
        s, band = _score_from_factors(factors)
        await upsert(
            {
                "entity_code": c.get("entity"),
                "object_type": "customer",
                "object_id": c.get("id"),
                "object_label": c.get("customer_name") or c.get("customer_code") or c.get("id"),
                "score": round(s, 4),
                "band": band,
                "factors": factors,
            }
        )

    # --- GL accounts (masters) ---
    gq: Dict[str, Any] = {"entity_code": entity_code} if entity_code else {}
    gls = [g async for g in db.master_gl_accounts.find(gq, {"_id": 0}).limit(limit_per_type)]
    for g in gls:
        factors = []
        acct_type = (g.get("account_type") or "").strip().lower()
        if acct_type and acct_type not in ("asset", "liability", "revenue", "expense", "equity"):
            factors.append({"key": "invalid_account_type", "value": 1.0, "weight": 0.25})
        if "suspense" in (g.get("account_name") or "").lower():
            factors.append({"key": "suspense_account", "value": 1.0, "weight": 0.45})
        s, band = _score_from_factors(factors)
        await upsert(
            {
                "entity_code": g.get("entity_code"),
                "object_type": "gl_account",
                "object_id": g.get("id") or g.get("account_code"),
                "object_label": g.get("account_name") or g.get("account_code"),
                "score": round(s, 4),
                "band": band,
                "factors": factors,
            }
        )

    # --- Journal entries (seeded collection `journals`) ---
    jq: Dict[str, Any] = {"entity": entity_code} if entity_code else {}
    jes = [j async for j in db.journals.find(jq, {"_id": 0}).limit(limit_per_type)]
    for j in jes:
        factors = []
        amount = float(j.get("amount") or j.get("total_amount") or 0.0)
        factors.append({"key": "amount_scale", "value": _clamp01(amount / 500_000.0), "weight": 0.3})
        if j.get("manual") is True:
            factors.append({"key": "manual_entry", "value": 1.0, "weight": 0.25})
        if (j.get("risk_score") is not None) or (j.get("risk_band") is not None):
            try:
                rs = float(j.get("risk_score") or 0.0)
                factors.append({"key": "engine_score", "value": _clamp01(rs), "weight": 0.35})
            except Exception:  # noqa: BLE001
                pass
        s, band = _score_from_factors(factors)
        await upsert(
            {
                "entity_code": j.get("entity"),
                "object_type": "journal",
                "object_id": j.get("id"),
                "object_label": j.get("journal_number") or j.get("id"),
                "score": round(s, 4),
                "band": band,
                "factors": factors,
            }
        )

    # --- Cases (open cases imply risk attention) ---
    kq: Dict[str, Any] = {"entity": entity_code} if entity_code else {}
    cases = [c async for c in db.cases.find(kq, {"_id": 0}).limit(limit_per_type)]
    for c in cases:
        factors = [{"key": "is_open", "value": 1.0 if c.get("status") != "closed" else 0.0, "weight": 0.5}]
        exposure = float(c.get("financial_exposure") or 0.0)
        factors.append({"key": "exposure_scale", "value": _clamp01(exposure / 1_000_000.0), "weight": 0.35})
        s, band = _score_from_factors(factors)
        await upsert(
            {
                "entity_code": c.get("entity"),
                "object_type": "case",
                "object_id": c.get("id"),
                "object_label": c.get("title") or c.get("id"),
                "score": round(s, 4),
                "band": band,
                "factors": factors,
            }
        )

    return {"status": "ok", "computed_at": now, "upserts": upserts}


@router.get("/summary")
async def risk_summary(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    await _ensure_seed_risk_scores(entity_code=entity_code)
    q: Dict[str, Any] = {"entity_code": entity_code} if entity_code else {}
    cur = db.finance_risk_scores.find(q, {"_id": 0}).sort("score", -1).limit(2000)
    items = [x async for x in cur]
    by_band = {"high": 0, "medium": 0, "low": 0}
    by_type: Dict[str, int] = {}
    for r in items:
        by_band[str(r.get("band") or "low")] = by_band.get(str(r.get("band") or "low"), 0) + 1
        typ = str(r.get("object_type") or "unknown")
        by_type[typ] = by_type.get(typ, 0) + 1
    return {"as_of": _now(), "entity_code": entity_code, "counts_by_band": by_band, "counts_by_object_type": by_type, "top": items[:20]}


@router.get("/scores")
async def risk_scores(entity_code: Optional[str] = Query(None), object_type: Optional[str] = Query(None), band: Optional[str] = Query(None), limit: int = Query(200, ge=1, le=2000), offset: int = Query(0, ge=0), current=Depends(get_current_user)):
    await _ensure_seed_risk_scores(entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity_code"] = entity_code
    if object_type:
        q["object_type"] = object_type
    if band:
        q["band"] = band
    cur = db.finance_risk_scores.find(q, {"_id": 0}).sort("score", -1).skip(offset).limit(limit)
    items = [x async for x in cur]
    total = await db.finance_risk_scores.count_documents(q)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": _now()}


@router.get("/{object_type}/{object_id}")
async def risk_object(object_type: str, object_id: str, current=Depends(get_current_user)):
    r = await db.finance_risk_scores.find_one({"natural_key": f"{object_type}::{object_id}"}, {"_id": 0})
    if not r:
        return {"found": False, "object_type": object_type, "object_id": object_id, "as_of": _now()}
    return {"found": True, "risk": r, "as_of": _now()}


@router.get("/heatmap")
async def risk_heatmap(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    await _ensure_seed_risk_scores(entity_code=entity_code)
    q: Dict[str, Any] = {"entity_code": entity_code} if entity_code else {}
    items = [x async for x in db.finance_risk_scores.find(q, {"_id": 0, "object_type": 1, "band": 1}).limit(5000)]
    # heatmap = object_type x band counts
    heat: Dict[str, Dict[str, int]] = {}
    for r in items:
        typ = str(r.get("object_type") or "unknown")
        band = str(r.get("band") or "low")
        heat.setdefault(typ, {"high": 0, "medium": 0, "low": 0})
        heat[typ][band] = heat[typ].get(band, 0) + 1
    rows = [{"object_type": k, **v} for k, v in sorted(heat.items())]
    return {"items": rows, "count": len(rows), "as_of": _now(), "entity_code": entity_code}


@router.post("/recalculate")
async def risk_recalculate(body: Dict[str, Any], current=Depends(get_current_user)):
    entity_code = body.get("entity_code")
    limit_per_type = int(body.get("limit_per_type") or 50)
    out = await _recompute_scores(entity_code=entity_code, limit_per_type=limit_per_type)
    await audit_log(current["email"], "risk_recalculate", "risk_scores", entity_code or "all", {"limit_per_type": limit_per_type, "upserts": out.get("upserts")})
    return {**out, "as_of": _now(), "entity_code": entity_code}


@router.post("/{object_id}/feedback")
async def risk_feedback(object_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    """Feedback loop: record an analyst label for a risk item."""
    fid = f"RFB-{__import__('uuid').uuid4().hex[:10]}"
    doc = {
        "id": fid,
        "object_id": object_id,
        "object_type": body.get("object_type"),
        "label": body.get("label") or "false_positive",  # false_positive|confirmed|needs_review
        "note": body.get("note"),
        "entity_code": body.get("entity_code"),
        "created_at": _now(),
        "created_by": current.get("email"),
    }
    await db.risk_feedback.insert_one(dict(doc))
    await audit_log(current["email"], "risk_feedback", "risk_feedback", fid, {"label": doc["label"], "object_id": object_id})
    return {"status": "ok", "feedback_id": fid, "as_of": _now()}

