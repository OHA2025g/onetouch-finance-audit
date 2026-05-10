"""OCI Integration / curated read replica — HTTPS JSON over your read model (ATP, Object Storage exports, OIC)."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from app.connectors.adapters._normalize import normalize_generic
from app.connectors.adapters.base import BaseConnectorAdapter
from app.connectors.credentials import load_connector_credentials
from app.connectors.http_client import ConnectorHttpClient
from app.connectors.types import FetchResult, HealthCheckResult


class OracleOciReplicaAdapter(BaseConnectorAdapter):
    provider = "oracle_erp"

    def _extra(self) -> Dict[str, Any]:
        return dict(self.config.extra or {})

    def _base(self) -> str:
        return (self._extra().get("oci_read_api_base_url") or os.environ.get("ORACLE_OCI_READ_API_BASE_URL") or "").rstrip("/")

    def _headers(self) -> Dict[str, str]:
        h = {"Accept": "application/json"}
        secrets = load_connector_credentials(self.credentials)
        if secrets.get("static_bearer_token"):
            h["Authorization"] = f"Bearer {secrets['static_bearer_token']}"
        return h

    def expected_schema(self, domain: str) -> Dict[str, Any]:
        return {"required": ["id", "entity", "created_at", "source_system"]}

    def normalize(self, domain: str, record: Dict[str, Any]) -> Dict[str, Any]:
        return normalize_generic(
            domain,
            record,
            entity_code=self.config.entity_code,
            source_system=str(self._extra().get("source_system_label") or "ORACLE-OCI-REPLICA"),
        )

    async def health_check(self) -> HealthCheckResult:
        base = self._base()
        if not base:
            return HealthCheckResult(
                ok=False,
                message="OCI replica: set config.extra.oci_read_api_base_url (HTTPS read model / OIC)",
                details={"pattern": "oci_replica"},
            )
        try:
            http = ConnectorHttpClient()
            path = self._extra().get("oci_health_path", "/healthz")
            r = await http.request("GET", f"{base}{path}", headers=self._headers())
            return HealthCheckResult(ok=True, message="OCI read API reachable", details={"pattern": "oci_replica"})
        except Exception as e:  # noqa: BLE001
            return HealthCheckResult(ok=False, message=str(e), details={"pattern": "oci_replica"})

    async def fetch_domain(self, *, domain: str, cursor: Optional[str], mode: str) -> FetchResult:
        base = self._base()
        if not base:
            return FetchResult(domain=domain, records=[], cursor=None)
        tmpl = self._extra().get("oci_fetch_path_template") or "/v1/read/{domain}"
        url = f"{base}{tmpl.replace('{domain}', domain)}"
        params: Dict[str, str] = {"mode": mode}
        if cursor:
            params["cursor"] = cursor
        full = f"{url}?{urlencode(params)}"
        http = ConnectorHttpClient()
        r = await http.request("GET", full, headers=self._headers())
        body = r.json()
        recs = list(body.get("records") or body.get("rows") or [])
        nxt = body.get("next_cursor")
        return FetchResult(domain=domain, records=recs, cursor=str(nxt) if nxt else None)
