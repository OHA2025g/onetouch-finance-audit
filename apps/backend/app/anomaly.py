"""Anomaly scoring: isolation forest over transaction features + per-control z-score blend.

Produces a `recalibrate_anomaly_scores(db)` routine that:
 1. Pulls invoices, payments, journals
 2. Fits an IsolationForest on numeric features
 3. For each open exception, computes an anomaly percentile in [0,1]
 4. Updates exception documents with new `anomaly_score`
"""
from __future__ import annotations
from typing import Dict, Any, List
import numpy as np
from sklearn.ensemble import IsolationForest


async def _collect_samples(db) -> Dict[str, List[Dict[str, Any]]]:
    invoices = [i async for i in db.invoices.find({}, {"_id": 0})]
    payments = [p async for p in db.payments.find({}, {"_id": 0})]
    journals = [j async for j in db.journals.find({}, {"_id": 0})]
    return {"invoices": invoices, "payments": payments, "journals": journals}


def _fit_iforest(samples: List[float]) -> IsolationForest:
    X = np.array(samples, dtype=float).reshape(-1, 1) if samples else np.array([[0.0]])
    model = IsolationForest(n_estimators=80, contamination=0.06, random_state=42)
    model.fit(X)
    return model


def _percentile_score(model: IsolationForest, value: float) -> float:
    # Convert `decision_function` to 0-1 (higher = more anomalous)
    raw = float(model.decision_function(np.array([[value]]))[0])
    # decision_function: positive = inlier. Map to anomaly_score in [0,1]
    # Use sigmoid-ish around 0: anomaly_score = 1 - sigmoid(raw * k)
    k = 6.0
    return round(max(0.0, min(1.0, 1 / (1 + np.exp(raw * k)))), 3)


async def recalibrate_anomaly_scores(db) -> Dict[str, Any]:
    """Blend isolation-forest percentile with per-control z-score to update anomaly_score."""
    data = await _collect_samples(db)

    # Build models per record type, keyed on the primary numeric feature.
    inv_model = _fit_iforest([float(i.get("amount") or 0) for i in data["invoices"]])
    pay_model = _fit_iforest([float(p.get("amount") or 0) for p in data["payments"]])
    jrn_model = _fit_iforest([float(j.get("total_amount") or j.get("amount") or 0) for j in data["journals"]])

    # Per-control z-score distributions
    exceptions = [e async for e in db.exceptions.find({}, {"_id": 0})]
    by_control: Dict[str, List[float]] = {}
    for e in exceptions:
        by_control.setdefault(e["control_code"], []).append(e["financial_exposure"])

    control_stats = {
        code: (float(np.mean(vals)), float(np.std(vals) or 1.0))
        for code, vals in by_control.items()
    }

    recalibrated = 0
    type_model = {"invoice": inv_model, "payment": pay_model, "journal": jrn_model}

    for e in exceptions:
        model = type_model.get(e["source_record_type"])
        if model is None:
            continue
        # Fetch the underlying record's numeric feature
        feature = None
        if e["source_record_type"] == "invoice":
            rec = await db.invoices.find_one({"id": e["source_record_id"]}, {"_id": 0, "amount": 1})
            if rec:
                feature = rec.get("amount")
        elif e["source_record_type"] == "payment":
            rec = await db.payments.find_one({"id": e["source_record_id"]}, {"_id": 0, "amount": 1})
            if rec:
                feature = rec.get("amount")
        elif e["source_record_type"] == "journal":
            rec = await db.journals.find_one(
                {"id": e["source_record_id"]}, {"_id": 0, "total_amount": 1, "amount": 1}
            )
            if rec:
                feature = rec.get("total_amount")
                if feature is None:
                    feature = rec.get("amount")
        if feature is None:
            continue

        p_score = _percentile_score(model, feature)
        mean, std = control_stats.get(e["control_code"], (0.0, 1.0))
        z = abs((e["financial_exposure"] - mean) / std) if std else 0.0
        z_score = min(1.0, z / 3.0)
        blended = round(0.6 * p_score + 0.4 * z_score, 3)
        await db.exceptions.update_one({"id": e["id"]}, {"$set": {"anomaly_score": blended}})
        recalibrated += 1

    return {
        "models_fit": 3,
        "exceptions_recalibrated": recalibrated,
        "controls_analyzed": len(control_stats),
        "algorithm": "IsolationForest(n=80) + per-control z-score blend (60/40)",
    }
