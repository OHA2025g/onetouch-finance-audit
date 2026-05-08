"""Uvicorn entry: ``uvicorn server:app --reload`` (or ``--host 0.0.0.0``).

The ASGI app is built in ``app.main`` (``create_app``) so that routers, middleware, and
lifecycle are composed in one testable place; this file stays a stable import path.
"""
from app.main import app  # noqa: F401  — re-exported for Uvicorn

__all__ = ["app"]
