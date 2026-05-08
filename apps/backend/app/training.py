"""Anomaly model training job: fits a fresh IsolationForest and registers a versioned artefact.

Persists to `model_versions` with training params, metrics, and approval_status='pending_review'.
Approvers (CFO/Controller/Internal Auditor) can then activate a specific version.
"""
from __future__ import annotations
import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import numpy as np
try:
    # Optional: some environments (e.g., system Python) may have incompatible numpy wheels.
    from sklearn.ensemble import IsolationForest  # type: ignore
    from sklearn.model_selection import train_test_split  # type: ignore
except Exception:  # pragma: no cover
    IsolationForest = None  # type: ignore
    train_test_split = None  # type: ignore


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


async def train_anomaly_model(db, *, trained_by: str, notes: str = "",
                              contamination: float = 0.06, n_estimators: int = 100,
                              test_fraction: float = 0.2) -> Dict[str, Any]:
    """Fit IsolationForest on unified transaction amounts, compute metrics, register version."""
    if IsolationForest is None or train_test_split is None:
        return {"error": "ml_runtime_unavailable", "detail": "sklearn is not available in this runtime"}
    # Build sample dataset combining invoices, payments, journals with type tag as synthetic feature
    rows: List[List[float]] = []
    tags: List[str] = []
    async for i in db.invoices.find({}, {"_id": 0, "amount": 1}):
        rows.append([float(i["amount"]), 0.0]); tags.append("invoice")
    async for p in db.payments.find({}, {"_id": 0, "amount": 1}):
        rows.append([float(p["amount"]), 1.0]); tags.append("payment")
    async for j in db.journals.find({}, {"_id": 0, "total_amount": 1, "amount": 1}):
        amt = j.get("total_amount")
        if amt is None:
            amt = j.get("amount")
        rows.append([float(amt or 0.0), 2.0])
        tags.append("journal")

    if len(rows) < 10:
        return {"error": "insufficient_samples", "samples": len(rows)}

    X = np.array(rows)
    X_train, X_test = train_test_split(X, test_size=test_fraction, random_state=42)

    model = IsolationForest(
        n_estimators=n_estimators, contamination=contamination, random_state=42,
    )
    model.fit(X_train)

    # Evaluate: decision_function distribution on test + anomaly ratio
    test_scores = model.decision_function(X_test)
    test_pred = model.predict(X_test)  # 1=inlier, -1=outlier
    anomalies = int((test_pred == -1).sum())
    inliers = int((test_pred == 1).sum())

    metrics = {
        "n_train": int(X_train.shape[0]),
        "n_test": int(X_test.shape[0]),
        "test_anomaly_rate": round(anomalies / max(1, len(test_pred)), 4),
        "test_score_mean": float(round(np.mean(test_scores), 4)),
        "test_score_std": float(round(np.std(test_scores), 4)),
        "test_score_min": float(round(np.min(test_scores), 4)),
        "test_score_max": float(round(np.max(test_scores), 4)),
        "feature_count": int(X.shape[1]),
        "train_types": {
            "invoice": tags.count("invoice"),
            "payment": tags.count("payment"),
            "journal": tags.count("journal"),
        },
    }

    # Determine next version number
    count = await db.model_versions.count_documents({"model_id": "M-002"})
    version_label = f"v{count + 1}.0"
    now = _iso(datetime.now(timezone.utc))
    artefact = {
        "id": str(uuid.uuid4()),
        "model_id": "M-002",
        "model_name": "anomaly-iforest",
        "version_label": version_label,
        "params": {
            "algorithm": "IsolationForest",
            "n_estimators": n_estimators,
            "contamination": contamination,
            "random_state": 42,
        },
        "metrics": metrics,
        "approval_status": "pending_review",
        "approved_by": None,
        "approved_at": None,
        "trained_by": trained_by,
        "notes": notes,
        "created_at": now,
        "active": False,
    }
    await db.model_versions.insert_one(dict(artefact))

    return artefact


async def list_model_versions(db, model_id: str = "M-002") -> List[Dict[str, Any]]:
    return [m async for m in db.model_versions.find({"model_id": model_id}, {"_id": 0}).sort("created_at", -1)]


async def approve_model_version(db, version_id: str, approver_email: str) -> Dict[str, Any]:
    v = await db.model_versions.find_one({"id": version_id}, {"_id": 0})
    if not v:
        return {"error": "not_found"}
    # Deactivate other versions of the same model
    await db.model_versions.update_many(
        {"model_id": v["model_id"], "id": {"$ne": version_id}},
        {"$set": {"active": False}},
    )
    await db.model_versions.update_one(
        {"id": version_id},
        {"$set": {
            "approval_status": "approved",
            "approved_by": approver_email,
            "approved_at": _iso(datetime.now(timezone.utc)),
            "active": True,
        }},
    )
    return await db.model_versions.find_one({"id": version_id}, {"_id": 0})
