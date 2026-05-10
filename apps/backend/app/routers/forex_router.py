"""Phase 27 — Forex exposure & hedge tracking (seed-friendly, L4 contract)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.deps import audit_log, db
from app.services.kpi_service import as_of_now
from app.services.rbac_service import enforce_entity_scope


router = APIRouter(prefix="/forex", tags=["forex"])


def _parse_dt(s: Any) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:  # noqa: BLE001
        return None


async def _latest_rate(pair: str) -> Optional[float]:
    r = await db.fx_rates.find_one({"pair": pair, "mid_rate": {"$exists": True}}, {"_id": 0}, sort=[("date", -1)])
    if not r:
        return None
    try:
        return float(r.get("mid_rate"))
    except Exception:  # noqa: BLE001
        return None


async def _ensure_seed_forex(entity_code: Optional[str] = None) -> Dict[str, int]:
    """Seed-on-first-use exposures + hedges (works even if Phase 2 seed wasn't run)."""
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code

    out = {"fx_exposures": 0, "fx_hedges": 0}
    now = datetime.now(timezone.utc)

    if await db.fx_exposures.count_documents(q) == 0:
        # Use known seeded pairs; if fx_rates isn't present, still seed stable pairs.
        pairs = ["USD/INR", "USD/GBP", "USD/SGD"]
        docs = []
        for i in range(18):
            pair = pairs[i % len(pairs)]
            base, quote = pair.split("/")
            direction = "payable" if i % 2 == 0 else "receivable"
            notional = round(75_000 * (1 + (i % 6) * 0.55), 2)
            maturity = (now + timedelta(days=15 * (2 + (i % 12)))).date().isoformat()
            docs.append(
                {
                    "id": f"FXEXP-{7000+i}",
                    "entity": entity_code or ["IN-SVC", "UK-OPS", "SG-APAC"][i % 3],
                    "pair": pair,
                    "base_currency": base,
                    "quote_currency": quote,
                    "direction": direction,
                    "notional_base": notional,
                    "maturity_date": maturity,
                    "source": "synthetic",
                    "status": "open",
                    "created_at": as_of_now(),
                }
            )
        await db.fx_exposures.insert_many(docs)
        out["fx_exposures"] = len(docs)

    if await db.fx_hedges.count_documents(q) == 0:
        exps = [e async for e in db.fx_exposures.find(q, {"_id": 0}).limit(30)]
        docs = []
        for i, e in enumerate(exps[:10]):
            hedged = float(e.get("notional_base") or 0.0) * (0.6 if i % 3 else 1.0)
            pair = e.get("pair")
            spot = await _latest_rate(pair) or 1.0
            forward = round(spot * (1.01 if i % 2 else 0.99), 4)
            docs.append(
                {
                    "id": f"HEDGE-{8000+i}",
                    "entity": e.get("entity"),
                    "pair": pair,
                    "exposure_id": e.get("id"),
                    "hedge_type": "forward",
                    "notional_base": round(hedged, 2),
                    "start_date": (now - timedelta(days=10 + i)).date().isoformat(),
                    "maturity_date": e.get("maturity_date"),
                    "rate_locked": forward,
                    "status": "active",
                    "created_at": as_of_now(),
                    "created_by": "treasury@onetouch.ai",
                }
            )
        if docs:
            await db.fx_hedges.insert_many(docs)
            out["fx_hedges"] = len(docs)

    return out


@router.get("/summary")
async def forex_summary(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_forex(entity_code=entity_code)
    q: Dict[str, Any] = {"entity": entity_code} if entity_code else {}
    exposures = [e async for e in db.fx_exposures.find(q, {"_id": 0}).limit(500)]
    hedges = [h async for h in db.fx_hedges.find(q, {"_id": 0}).limit(500)]

    by_pair: Dict[str, Dict[str, float]] = {}
    for e in exposures:
        pair = e.get("pair") or "UNKNOWN"
        by_pair.setdefault(pair, {"gross_base": 0.0, "receivable_base": 0.0, "payable_base": 0.0})
        amt = float(e.get("notional_base") or 0.0)
        by_pair[pair]["gross_base"] += amt
        if e.get("direction") == "receivable":
            by_pair[pair]["receivable_base"] += amt
        else:
            by_pair[pair]["payable_base"] += amt

    hedged_by_pair: Dict[str, float] = {}
    for h in hedges:
        pair = h.get("pair") or "UNKNOWN"
        hedged_by_pair[pair] = hedged_by_pair.get(pair, 0.0) + float(h.get("notional_base") or 0.0)

    rows = []
    for pair, s in sorted(by_pair.items()):
        gross = float(s["gross_base"])
        hedged = float(hedged_by_pair.get(pair, 0.0))
        unhedged = max(gross - hedged, 0.0)
        rows.append(
            {
                "pair": pair,
                "gross_exposure_base": round(gross, 2),
                "hedged_base": round(hedged, 2),
                "unhedged_base": round(unhedged, 2),
                "hedge_ratio_pct": round(100.0 * hedged / max(gross, 1.0), 2),
            }
        )
    return {"as_of": as_of_now(), "entity_code": entity_code, "items": rows, "exposure_count": len(exposures), "hedge_count": len(hedges)}


@router.get("/exposures")
async def forex_exposures(entity_code: Optional[str] = Query(None), pair: Optional[str] = Query(None), status: Optional[str] = Query(None), limit: int = Query(200, ge=1, le=2000), offset: int = Query(0, ge=0), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_forex(entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    if pair:
        q["pair"] = pair
    if status:
        q["status"] = status
    cur = db.fx_exposures.find(q, {"_id": 0}).sort("maturity_date", 1).skip(offset).limit(limit)
    items = [x async for x in cur]
    total = await db.fx_exposures.count_documents(q)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": as_of_now()}


@router.get("/hedges")
async def forex_hedges(entity_code: Optional[str] = Query(None), pair: Optional[str] = Query(None), status: Optional[str] = Query(None), limit: int = Query(200, ge=1, le=2000), offset: int = Query(0, ge=0), current=Depends(get_current_user)):
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_forex(entity_code=entity_code)
    q: Dict[str, Any] = {}
    if entity_code:
        q["entity"] = entity_code
    if pair:
        q["pair"] = pair
    if status:
        q["status"] = status
    cur = db.fx_hedges.find(q, {"_id": 0}).sort("maturity_date", 1).skip(offset).limit(limit)
    items = [x async for x in cur]
    total = await db.fx_hedges.count_documents(q)
    return {"items": items, "total": total, "limit": limit, "offset": offset, "as_of": as_of_now()}


@router.get("/unhedged-risk")
async def forex_unhedged_risk(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    """Unhedged risk surface: group exposures - hedges by pair with a proxy risk score."""
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_forex(entity_code=entity_code)
    summ = await forex_summary(entity_code=entity_code, current=current)
    items = []
    for r in summ.get("items") or []:
        unhedged = float(r.get("unhedged_base") or 0.0)
        ratio = float(r.get("hedge_ratio_pct") or 0.0)
        risk = round(min(1.0, (unhedged / 250_000.0) * (1.0 if ratio < 80 else 0.6)), 3)
        items.append({**r, "risk_score": risk, "risk_band": "high" if risk >= 0.75 else "medium" if risk >= 0.4 else "low"})
    items.sort(key=lambda x: (-float(x.get("risk_score") or 0.0), -float(x.get("unhedged_base") or 0.0)))
    return {"items": items, "count": len(items), "as_of": as_of_now(), "entity_code": entity_code, "note": "Risk score is a proxy based on unhedged notional; replace with VaR/CFaR when modeled."}


@router.get("/gain-loss")
async def forex_gain_loss(entity_code: Optional[str] = Query(None), current=Depends(get_current_user)):
    """Proxy realized/unrealized gain-loss using locked vs latest mid on hedges."""
    entity_code = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    await _ensure_seed_forex(entity_code=entity_code)
    q: Dict[str, Any] = {"entity": entity_code} if entity_code else {}
    hedges = [h async for h in db.fx_hedges.find(q, {"_id": 0}).limit(500)]

    realized = 0.0
    unrealized = 0.0
    rows = []
    for h in hedges:
        pair = h.get("pair")
        locked = float(h.get("rate_locked") or 0.0)
        mid = await _latest_rate(pair) or locked
        notional = float(h.get("notional_base") or 0.0)
        # P/L proxy: (mid - locked) * notional, sign depends on direction; we don't model buy/sell, so keep absolute directionless.
        pl = round((mid - locked) * notional, 2)
        maturity = _parse_dt(h.get("maturity_date"))
        is_realized = bool(maturity and maturity.date() <= datetime.now(timezone.utc).date())
        if is_realized:
            realized += pl
        else:
            unrealized += pl
        rows.append({"hedge_id": h.get("id"), "pair": pair, "notional_base": notional, "rate_locked": locked, "mid_rate": mid, "pl_amount": pl, "bucket": "realized" if is_realized else "unrealized"})
    return {"as_of": as_of_now(), "entity_code": entity_code, "realized_pl": round(realized, 2), "unrealized_pl": round(unrealized, 2), "items": rows[:200], "note": "P/L is a proxy; integrate actual settlement and accounting entries for accuracy."}


@router.post("/hedges")
async def forex_hedge_create(body: Dict[str, Any], current=Depends(get_current_user)):
    ent = await enforce_entity_scope(
        db, current=current, requested_entity_code=(body.get("entity") or body.get("entity_code"))
    )
    await _ensure_seed_forex(entity_code=ent or body.get("entity"))
    hid = f"HEDGE-{__import__('uuid').uuid4().hex[:10]}"
    pair = str(body.get("pair") or "USD/INR")
    spot = await _latest_rate(pair) or 1.0
    doc = {
        "id": hid,
        "entity": ent or body.get("entity") or "US-HQ",
        "pair": pair,
        "exposure_id": body.get("exposure_id"),
        "hedge_type": body.get("hedge_type") or "forward",
        "notional_base": float(body.get("notional_base") or 0.0),
        "start_date": body.get("start_date") or datetime.now(timezone.utc).date().isoformat(),
        "maturity_date": body.get("maturity_date") or (datetime.now(timezone.utc) + timedelta(days=90)).date().isoformat(),
        "rate_locked": float(body.get("rate_locked") or round(spot * 1.01, 4)),
        "status": body.get("status") or "active",
        "created_at": as_of_now(),
        "created_by": current.get("email"),
    }
    await db.fx_hedges.insert_one(dict(doc))
    await audit_log(current["email"], "forex_hedge_create", "fx_hedge", hid, {"pair": pair, "exposure_id": body.get("exposure_id")})
    return {"status": "ok", "hedge_id": hid, "as_of": as_of_now()}


@router.post("/{source_id}/create-case")
async def forex_create_case(source_id: str, body: Dict[str, Any], current=Depends(get_current_user)):
    await _ensure_seed_forex()
    exp = await db.fx_exposures.find_one({"id": source_id}, {"_id": 0})
    hedge = None if exp else await db.fx_hedges.find_one({"id": source_id}, {"_id": 0})
    if not exp and not hedge:
        raise HTTPException(404, "Exposure/Hedge not found")
    ent_src = (exp or hedge).get("entity")
    if ent_src:
        await enforce_entity_scope(db, current=current, requested_entity_code=ent_src)

    now = as_of_now()
    cid = f"case-fx-{__import__('uuid').uuid4().hex[:10]}"
    ex_id = f"fx-{source_id}"
    entity = (exp or hedge).get("entity") or current.get("entity") or "US-HQ"
    pair = (exp or hedge).get("pair") or "USD/INR"
    exposure = float(body.get("financial_exposure") or (exp.get("notional_base") if exp else hedge.get("notional_base")) or 0.0)

    title = body.get("title") or (f"Unhedged FX exposure: {pair}" if exp else f"FX hedge review: {pair}")
    summary = body.get("summary") or ("Case created from FX exposure/hedge surface." if exp else "Case created from FX hedge register.")
    control_code = "FX-UNH-001" if exp else "FX-HEDGE-001"
    control_name = "Unhedged FX Exposure" if exp else "FX Hedge Governance"

    ex_doc = {
        "id": ex_id,
        "control_id": f"adhoc-{control_code.lower()}",
        "control_code": control_code,
        "control_name": control_name,
        "process": "Treasury",
        "entity": entity,
        "severity": str(body.get("severity") or ("high" if exp else "medium")),
        "status": "open",
        "materiality_score": float(body.get("materiality_score") or 0.5),
        "anomaly_score": float(body.get("anomaly_score") or 0.5),
        "financial_exposure": exposure,
        "source_record_type": "fx_exposure" if exp else "fx_hedge",
        "source_record_id": source_id,
        "detected_at": now,
        "title": title,
        "summary": summary,
        "recurrence_count": 0,
        "department_id": None,
        "cost_center_id": None,
    }
    await db.exceptions.update_one({"id": ex_id}, {"$setOnInsert": ex_doc}, upsert=True)

    case_doc = {
        "id": cid,
        "exception_id": ex_id,
        "control_code": control_code,
        "control_name": control_name,
        "title": title,
        "summary": summary,
        "severity": ex_doc["severity"],
        "status": "open",
        "priority": body.get("priority") or ("P1" if exp else "P2"),
        "owner_email": body.get("owner_email") or current.get("email"),
        "owner_name": None,
        "due_date": body.get("due_date") or now,
        "financial_exposure": float(ex_doc.get("financial_exposure") or 0.0),
        "entity": entity,
        "process": "Treasury",
        "detected_at": now,
        "opened_at": now,
        "closed_at": None,
        "root_cause_category": None,
        "engagement_id": None,
        "material_impact": body.get("material_impact"),
        "material_watch": None,
        "department_id": None,
        "cost_center_id": None,
    }
    await db.cases.insert_one(dict(case_doc))
    await audit_log(current["email"], "forex_create_case", "case", cid, {"source_id": source_id, "pair": pair})
    return {"status": "ok", "case_id": cid, "exception_id": ex_id, "as_of": as_of_now()}

