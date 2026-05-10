from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

ConnectorProvider = Literal["sap", "oracle_erp"]
AuthStrategy = Literal["env_ref", "none", "vault_ref"]
RunMode = Literal["sync", "backfill"]

@dataclass(frozen=True)
class ConnectorCredentialRef:
    """Do not store raw secrets in Mongo; store a reference only.

    - env_ref: JSON or key=value text in process env (``env_key``).
    - vault_ref: Resolve at runtime from a vault / secret manager (never persist secret values).
    """

    id: str
    kind: AuthStrategy
    env_key: Optional[str] = None  # kind=env_ref
    vault_provider: Optional[str] = None  # env_bridge | aws_secretsmanager | hashicorp_vault | azure_keyvault
    vault_secret_id: Optional[str] = None  # ARN, logical id, Vault path, or Key Vault secret name
    rotation_version: Optional[str] = None  # optional version/stage for rotation-aware lookups


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

