from __future__ import annotations
from datetime import datetime, timezone


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()
