"""Lightweight load smoke for action queue list (optional; needs running API)."""

from __future__ import annotations

import os
import time

import pytest
import requests

from l4_http_common import resolve_react_app_backend_url, wait_until_api_ready

BASE_URL = resolve_react_app_backend_url()
pytestmark = pytest.mark.skipif(not BASE_URL, reason="REACT_APP_BACKEND_URL not set")
API = f"{BASE_URL.rstrip('/')}/api" if BASE_URL else ""


def _token() -> str:
    wait_until_api_ready(API, timeout_s=60.0)
    r = requests.post(
        f"{API}/auth/login",
        json={"email": "cfo@onetouch.ai", "password": "demo1234"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.mark.slow
def test_action_queue_list_p95_under_3s():
    """Ten sequential list calls should stay under 3s p95 (local dev smoke)."""
    tok = _token()
    headers = {"Authorization": f"Bearer {tok}"}
    times: list[float] = []
    for _ in range(10):
        t0 = time.perf_counter()
        r = requests.get(
            f"{API}/cfo/action-queue",
            headers=headers,
            params={"limit": 50, "sort": "score"},
            timeout=30,
        )
        times.append(time.perf_counter() - t0)
        assert r.status_code == 200, r.text
    times.sort()
    p95 = times[int(len(times) * 0.95) - 1]
    assert p95 < 3.0, f"p95 list latency {p95:.2f}s exceeds 3s budget"
