"""Reusable auth guards (Depends) for role-based access."""
from __future__ import annotations
from typing import Any, Callable

from fastapi import Depends, HTTPException, status

from app.auth import get_current_user


def require_roles(*allowed: str) -> Callable[..., Any]:
    """Return a FastAPI dependency that enforces the current user role is in ``allowed``."""

    async def _guard(current: dict = Depends(get_current_user)) -> dict:
        role = current.get("role")
        if role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this operation",
            )
        return current

    return _guard
