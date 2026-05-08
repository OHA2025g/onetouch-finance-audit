"""Shared dependencies: MongoDB client, logger, audit-log helper.

Imported by routers and the main FastAPI app entrypoint.
"""
from __future__ import annotations
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.audit_actions import assert_known_audit_action
from app.utils.timeutil import iso_utc

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("onetouch")

# Public alias used across routers; delegates to a DB-free time helper for testability
iso = iso_utc


async def audit_log(actor: str, action: str, object_type: str, object_id: str,
                    detail: Optional[Dict[str, Any]] = None) -> None:
    strict = os.environ.get("AUDIT_ACTION_STRICT", "").strip().lower() in ("1", "true", "yes")
    if strict:
        assert_known_audit_action(action, strict=True, log_warning=logger.warning)
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "actor_user_email": actor,
        "action_type": action,
        "object_type": object_type,
        "object_id": object_id,
        "event_ts": iso(datetime.now(timezone.utc)),
        "detail": detail or {},
    })
