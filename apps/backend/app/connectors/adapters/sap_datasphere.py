"""SAP Datasphere / BW — analytics-heavy extracts (curated facts).

Production: land files/API payloads in object storage or an integration tier; this adapter reads a
configured HTTPS snapshot URL or returns a clear configuration error until wired.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from app.connectors.adapters._normalize import normalize_generic
from app.connectors.adapters.base import BaseConnectorAdapter
from app.connectors.credentials import load_connector_credentials
from app.connectors.http_client import ConnectorHttpClient
from app.connectors.types import FetchResult, HealthCheckResult


class SapDatasphereAdapter(BaseConnectorAdapter):
    provider = "sap"

    def _extra(self) -> Dict[str, Any]:
        return dict(self.config.extra or {})

    def expected_schema(self, domain: str) -> Dict[str, Any]:
        return {"required": ["id", "entity", "created_at", "source_system"]}

    def normalize(self, domain: str, record: Dict[str, Any]) -> Dict[str, Any]:
        return normalize_generic(
            domain,
            record,
            entity_code=self.config.entity_code,
            source_system=str(self._extra().get("source_system_label") or "SAP-DATASPHERE"),
        )

    def _auth_headers(self) -> Dict[str, str]:
        h: Dict[str, str] = {"Accept": "application/json"}
        secrets = load_connector_credentials(self.credentials)
        if secrets.get("static_bearer_token"):
            h["Authorization"] = f"Bearer {secrets['static_bearer_token']}"
        return h

    async def health_check(self) -> HealthCheckResult:
        snap = self._extra().get("datasphere_snapshot_url") or os.environ.get("SAP_DATASPHERE_SNAPSHOT_URL")
        if not snap:
            return HealthCheckResult(
                ok=False,
                message="Datasphere: set config.extra.datasphere_snapshot_url or pipeline export target",
                details={"pattern": "datasphere", "lineage": "reconcile_extract_to_finance_collections"},
            )
        try:
            http = ConnectorHttpClient()
            r = await http.request("GET", snap, headers=self._auth_headers())
            return HealthCheckResult(
                ok=True,
                message="Datasphere snapshot URL reachable",
                details={"pattern": "datasphere", "status": r.status_code},
            )
        except Exception as e:  # noqa: BLE001
            return HealthCheckResult(ok=False, message=str(e), details={"pattern": "datasphere"})

    async def fetch_domain(self, *, domain: str, cursor: Optional[str], mode: str) -> FetchResult:
        """Expect JSON array or ``{ value: [...] }`` from snapshot export."""
        snap = self._extra().get("datasphere_snapshot_url") or os.environ.get("SAP_DATASPHERE_SNAPSHOT_URL")
        if not snap:
            return FetchResult(domain=domain, records=[], cursor=None)
        http = ConnectorHttpClient()
        r = await http.request("GET", snap, headers=self._auth_headers())
        data = r.json()
        rows: List[Dict[str, Any]] = data if isinstance(data, list) else list(data.get("value") or data.get("records") or [])
        return FetchResult(domain=domain, records=rows[:5000], cursor=None)
