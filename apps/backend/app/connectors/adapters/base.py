from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.connectors.types import ConnectorConfig, ConnectorCredentialRef, FetchResult, HealthCheckResult


class BaseConnectorAdapter(ABC):
    """Adapter interface. Real adapters can be plugged in later without changing APIs."""

    provider: str

    def __init__(self, *, config: ConnectorConfig, credentials: ConnectorCredentialRef) -> None:
        self.config = config
        self.credentials = credentials

    @abstractmethod
    async def health_check(self) -> HealthCheckResult:
        raise NotImplementedError

    @abstractmethod
    async def fetch_domain(
        self,
        *,
        domain: str,
        cursor: Optional[str],
        mode: str,
    ) -> FetchResult:
        raise NotImplementedError

    @abstractmethod
    def expected_schema(self, domain: str) -> Dict[str, Any]:
        """JSON-schema-like dict for validation. Keep it simple for now."""
        raise NotImplementedError

    def normalize(self, domain: str, record: Dict[str, Any]) -> Dict[str, Any]:
        """Convert provider-specific payload to OneTouch normalized shape."""
        return dict(record)

