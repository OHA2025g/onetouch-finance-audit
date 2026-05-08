"""Shared list pagination / limit clamping (query params)."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import Query

_DEFAULT_LIMIT = 50
_MAX_LIMIT = 500
_MIN_LIMIT = 1


def clamp_limit(
    value: int,
    *,
    default: int = _DEFAULT_LIMIT,
    min_limit: int = _MIN_LIMIT,
    max_limit: int = _MAX_LIMIT,
) -> int:
    if value is None:  # type: ignore[unreachable]
        return default
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    if n < min_limit:
        return min_limit
    if n > max_limit:
        return max_limit
    return n


@dataclass(frozen=True)
class PaginationParams:
    limit: int
    offset: int

    @classmethod
    def from_query(
        cls,
        limit: int = Query(_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT, description="Max items"),
        offset: int = Query(0, ge=0, description="Rows to skip"),
    ) -> "PaginationParams":
        return cls(limit=limit, offset=offset)

    def mongo(self) -> dict[str, int]:
        return {"limit": self.limit, "skip": self.offset}
