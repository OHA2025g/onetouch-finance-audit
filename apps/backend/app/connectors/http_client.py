"""HTTP client for ERP connectors: retries, backoff, simple 429/5xx handling."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class ConnectorHttpClient:
    """Thin async HTTP wrapper with exponential backoff (429 / 5xx)."""

    def __init__(
        self,
        *,
        timeout_s: float = 60.0,
        max_retries: int = 5,
        base_backoff_s: float = 0.5,
        max_backoff_s: float = 30.0,
        run_id: Optional[str] = None,
    ) -> None:
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.base_backoff_s = base_backoff_s
        self.max_backoff_s = max_backoff_s
        self.run_id = run_id

    def _log(self, msg: str, **kwargs: Any) -> None:
        if self.run_id:
            logger.info("connector_http run_id=%s %s", self.run_id, msg, extra=kwargs)
        else:
            logger.info("connector_http %s", msg, extra=kwargs)

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        headers = dict(kwargs.pop("headers", {}) or {})
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                    resp = await client.request(method, url, headers=headers, **kwargs)
                if resp.status_code == 429 or resp.status_code >= 500:
                    if attempt >= self.max_retries:
                        resp.raise_for_status()
                    ra = resp.headers.get("Retry-After")
                    if ra and ra.isdigit():
                        delay = min(float(ra), self.max_backoff_s)
                    else:
                        delay = min(
                            self.max_backoff_s,
                            self.base_backoff_s * (2**attempt) + random.random() * 0.25,
                        )
                    self._log("retry_after_status", status=resp.status_code, attempt=attempt, delay=delay)
                    await asyncio.sleep(delay)
                    continue
                resp.raise_for_status()
                return resp
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last_exc = e
                if attempt >= self.max_retries:
                    raise
                delay = min(self.max_backoff_s, self.base_backoff_s * (2**attempt) + random.random() * 0.25)
                self._log("retry_transport", attempt=attempt, delay=delay, err=str(e))
                await asyncio.sleep(delay)
        if last_exc:
            raise last_exc
        raise RuntimeError("request failed without response")
