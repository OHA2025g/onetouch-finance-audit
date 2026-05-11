"""Shared helpers for L4 HTTP contract tests (pytest + live API)."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

import requests


def read_backend_url_from_dotenv(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
            if line.startswith("BACKEND_URL="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        return None
    return None


def resolve_react_app_backend_url() -> Optional[str]:
    """Match docker-compose (REACT_APP_BACKEND_URL) and local monorepo ``apps/frontend/.env``."""
    for key in ("REACT_APP_BACKEND_URL", "BACKEND_URL"):
        v = (os.environ.get(key) or "").strip()
        if v:
            return v.rstrip("/")
    here = Path(__file__).resolve()
    # ``l4_http_common.py`` lives in ``apps/backend/tests/`` → ``apps/frontend/.env``
    for p in (
        Path("/app/frontend/.env"),
        here.parent.parent / "frontend" / ".env",
    ):
        u = read_backend_url_from_dotenv(p)
        if u:
            return u.rstrip("/")
    return None


def wait_until_api_ready(api: str, timeout_s: float = 60.0) -> None:
    """Block until ``GET {api}/`` returns 200 (public root mounted on the API router)."""
    deadline = time.time() + timeout_s
    last_err: Exception | None = None
    url = api.rstrip("/") + "/"
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                return
        except Exception as e:  # noqa: BLE001
            last_err = e
        time.sleep(0.5)
    raise AssertionError(f"API not reachable at {url} within {timeout_s}s: {last_err}")
