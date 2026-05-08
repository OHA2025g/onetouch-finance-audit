from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

ConnectorProvider = Literal["sap", "oracle_erp"]
AuthStrategy = Literal["env_ref", "none"]
RunMode = Literal["sync", "backfill"]


@dataclass(frozen=True)
class ConnectorCredentialRef:
    """Do not store raw secrets in DB; store a reference."""

    id: str
    kind: AuthStrategy
    env_key: Optional[str] = None  # kind=env_ref


@dataclass(frozen=True)
class ConnectorConfig:
    entity_code: str
    base_currency: str = "USD"
    reporting_currency: str = "USD"
    extra: Dict[str, Any] | None = None


@dataclass(frozen=True)
class HealthCheckResult:
    ok: bool
    message: str
    details: Dict[str, Any] | None = None


@dataclass(frozen=True)
class FetchResult:
    """Result of fetching a domain payload from a source system."""

    domain: str
    records: list[dict[str, Any]]
    cursor: Optional[str] = None

