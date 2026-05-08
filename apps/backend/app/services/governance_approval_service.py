from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from app.utils.timeutil import iso_utc


async def get_policy(db) -> Dict[str, Any]:
    """Singleton governance policy with approval requirements."""
    doc = await db.governance_policy_versions.find_one({"id": "singleton"}, {"_id": 0})
    if doc:
        return doc
    now = iso_utc(datetime.now(timezone.utc))
    doc = {
        "id": "singleton",
        "version": 1,
        "requires_approval": {
            "connector_activation": True,
            "retention_policy_change": True,
            "legal_hold_release": True,
            # Default to permissive for copilot tuning/reindex in self-hosted/demo environments.
            # Operators can tighten this via /governance/policies.
            "copilot_retrieval_config_change": False,
            "copilot_rebuild_index": False,
        },
        "updated_at": now,
        "updated_by": "system",
    }
    await db.governance_policy_versions.insert_one(dict(doc))
    return doc


async def create_request(
    db,
    *,
    request_type: str,
    subject_type: str,
    subject_id: str,
    proposed_change: Dict[str, Any],
    requested_by: str,
    reason: str,
) -> Dict[str, Any]:
    now = iso_utc(datetime.now(timezone.utc))
    rid = f"apr-{uuid.uuid4().hex[:10]}"
    doc = {
        "id": rid,
        "request_type": request_type,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "proposed_change": proposed_change,
        "reason": reason,
        "status": "pending",
        "requested_by": requested_by,
        "requested_at": now,
        "decided_at": None,
    }
    await db.approval_requests.insert_one(dict(doc))
    return doc


async def list_requests(db, status: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    return [r async for r in db.approval_requests.find(q, {"_id": 0}).sort("requested_at", -1).limit(limit)]


async def decide(
    db,
    *,
    request_id: str,
    decision: str,
    decided_by: str,
    note: str = "",
) -> Dict[str, Any]:
    req = await db.approval_requests.find_one({"id": request_id}, {"_id": 0})
    if not req:
        raise HTTPException(404, "Approval request not found")
    if req.get("status") != "pending":
        raise HTTPException(409, "Request already decided")
    now = iso_utc(datetime.now(timezone.utc))
    if decision not in ("approved", "rejected"):
        raise HTTPException(400, "decision must be approved|rejected")

    await db.approval_decisions.insert_one(
        {
            "id": f"apd-{uuid.uuid4().hex[:10]}",
            "request_id": request_id,
            "decision": decision,
            "decided_by": decided_by,
            "note": note,
            "decided_at": now,
        }
    )
    await db.approval_requests.update_one(
        {"id": request_id},
        {"$set": {"status": decision, "decided_at": now, "decided_by": decided_by}},
    )
    return await db.approval_requests.find_one({"id": request_id}, {"_id": 0})  # type: ignore[return-value]


async def require_approval_or_raise(db, *, action: str, subject_type: str, subject_id: str) -> None:
    pol = await get_policy(db)
    if not (pol.get("requires_approval") or {}).get(action, False):
        return
    # If there is a recently approved request for this subject+action, allow
    approved = await db.approval_requests.find_one(
        {"request_type": action, "subject_type": subject_type, "subject_id": subject_id, "status": "approved"},
        {"_id": 0},
    )
    if approved:
        return
    raise HTTPException(403, f"Action requires approval: {action}. Create an approval request first.")

