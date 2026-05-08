"""Retention policies, eligible-artifact scan, and limited purge (respects legal hold)."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from app.services import legal_hold_service as lhs
from app.utils.timeutil import iso_utc

ARTIFACT_COLLECTIONS: Dict[str, tuple] = {
    "copilot_session": ("copilot_sessions", "created_at"),
    "ingestion_run": ("ingestion_runs", "run_start"),
    "audit_log": ("audit_logs", "event_ts"),
}


def _old_enough(iso_str: str, days: int) -> bool:
    try:
        t = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
    except Exception:
        return False
    return t < datetime.now(timezone.utc) - timedelta(days=days)


def _get_ts_field(doc: Dict[str, Any], field: str) -> Optional[str]:
    return doc.get(field) or doc.get("created_at", doc.get("run_start", doc.get("run_end")))


async def list_policies(db) -> List[Dict[str, Any]]:
    return [p async for p in db.retention_policies.find({}, {"_id": 0}).sort("artifact_type", 1)]


async def upsert_policy(
    db,
    policy_id: Optional[str],
    body: Dict[str, Any],
) -> Dict[str, Any]:
    now = iso_utc(datetime.now(timezone.utc))
    if policy_id:
        ex = await db.retention_policies.find_one({"id": policy_id}, {"_id": 0})
        if not ex:
            from fastapi import HTTPException
            raise HTTPException(404, "Policy not found")
        upd = {k: v for k, v in body.items() if v is not None}
        upd["updated_at"] = now
        await db.retention_policies.update_one({"id": policy_id}, {"$set": upd})
        out = await db.retention_policies.find_one({"id": policy_id}, {"_id": 0})
        return out  # type: ignore[return-value]
    pid = body.get("id") or f"rpol-{uuid.uuid4().hex[:8]}"
    doc: Dict[str, Any] = {
        "id": pid, "name": body.get("name", "Unnamed"), "artifact_type": body.get("artifact_type", "case"),
        "retention_days": int(body.get("retention_days", 365)), "scope": body.get("scope", "global"),
        "action": body.get("action", "archive"), "legal_hold_protection": bool(body.get("legal_hold_protection", True)),
        "active": body.get("active", True) is not False, "created_at": now, "updated_at": now,
    }
    await db.retention_policies.update_one({"id": pid}, {"$set": doc}, upsert=True)
    return await db.retention_policies.find_one({"id": pid}, {"_id": 0})  # type: ignore[return-value]


async def find_eligible(db) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for pol in [p async for p in db.retention_policies.find({"active": True}, {"_id": 0})]:
        at = str(pol.get("artifact_type", ""))
        if not pol.get("retention_days"):
            continue
        days = int(pol["retention_days"])
        pair = ARTIFACT_COLLECTIONS.get(at)
        if not pair:
            out.append(
                {
                    "policy": pol, "count_estimate": 0,
                    "note": "No direct collection map for this type; handle via archive ops.",
                }
            )
            continue
        coll, field = pair
        n = 0
        examples: List[str] = []
        async for doc in db[coll].find({}, {"_id": 0, field: 1, "id": 1}):
            ts = _get_ts_field(doc, field)
            if not ts or not _old_enough(str(ts), days):
                continue
            aid = str(doc.get("id", ""))
            if at in ("case",) and pol.get("legal_hold_protection", True) and aid and await lhs.is_held(
                db, "case", aid
            ):
                continue
            n += 1
            if len(examples) < 5 and aid:
                examples.append(aid)
        out.append({"policy": pol, "count_estimate": n, "example_ids": examples})
    return out


async def run_retention(
    db,
    *,
    dry_run: bool,
    artifact_types: Optional[List[str]],
    user_email: str,
) -> Dict[str, Any]:
    from app.deps import audit_log, logger

    now = iso_utc(datetime.now(timezone.utc))
    job_id = f"purge-job-{uuid.uuid4().hex[:10]}"
    result: Dict[str, Any] = {
        "id": job_id, "run_at": now, "dry_run": dry_run, "status": "done", "deleted": {}, "skipped_held": 0,
    }
    q: Dict[str, Any] = {"active": True}
    if artifact_types:
        q["artifact_type"] = {"$in": artifact_types}
    policies = [p async for p in db.retention_policies.find(q, {"_id": 0})]
    for pol in policies:
        at = str(pol.get("artifact_type", ""))
        pair = ARTIFACT_COLLECTIONS.get(at)
        if at == "audit_log":
            result.setdefault("protected", []).append("audit_log: in-app purge disabled; use archive / SIEM")
            continue
        if at == "case":
            result.setdefault("protected", []).append("case: in-app case delete disabled; use WORM/exports policy")
            continue
        if not pair or not pol.get("retention_days"):
            continue
        is_purge = pol.get("action") == "purge"
        if not dry_run and not is_purge:
            result.setdefault("protected", []).append(f"{at}: action is {pol.get('action')}; not deleting")
            continue
        coll, field = pair
        days = int(pol["retention_days"])
        n_del = 0
        async for doc in db[coll].find({}, {"_id": 0}):
            ts = _get_ts_field(doc, field)
            if not ts or not _old_enough(str(ts), days):
                continue
            aid = str(doc.get("id", ""))
            if not aid:
                continue
            if pol.get("legal_hold_protection", True) and at in ("case",) and await lhs.is_held(db, "case", aid):
                result["skipped_held"] += 1
                continue
            if dry_run or is_purge:
                if dry_run:
                    n_del += 1
                if not dry_run and is_purge:
                    dres = await db[coll].delete_one({"id": aid})
                    n_del += int(dres.deleted_count or 0)
        result["deleted"][at] = n_del
    if not dry_run and sum(result.get("deleted", {}).values()) > 0:
        await audit_log(
            user_email, "retention_purge", "retention", job_id, {"result": result.get("deleted"), "dry_run": False},
        )
    await db.purge_jobs.insert_one(
        {**result, "user": user_email, "total": sum((result.get("deleted") or {}).values())}
    )
    logger.info("retention job %s user=%s dry=%s", job_id, user_email, dry_run)
    return result
