"""Per-user rate limits for CFO action queue bulk/refresh operations."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import HTTPException

from app.deps import db


async def enforce_action_queue_rate_limit(
    email: str,
    *,
    bucket: str,
    env_key: str,
    default_cap: int = 30,
) -> None:
    cap = int(os.environ.get(env_key, str(default_cap)))
    if cap <= 0:
        return
    minute_key = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    doc_id = f"{bucket}:{email}:{minute_key}"
    await db.cfo_action_queue_usage.update_one(
        {"id": doc_id},
        {"$inc": {"count": 1}, "$setOnInsert": {"email": email, "bucket": bucket, "minute_key": minute_key}},
        upsert=True,
    )
    doc = await db.cfo_action_queue_usage.find_one({"id": doc_id}, {"_id": 0, "count": 1})
    if doc and int(doc.get("count") or 0) > cap:
        raise HTTPException(
            429,
            f"Action queue {bucket} rate limit exceeded; try again in a minute.",
        )
