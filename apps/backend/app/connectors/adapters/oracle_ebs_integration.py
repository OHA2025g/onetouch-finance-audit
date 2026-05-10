"""Oracle E-Business Suite via integration tier (REST/SOAP gateway) — not direct DB access."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from app.connectors.adapters._normalize import normalize_generic
from app.connectors.adapters.base import BaseConnectorAdapter
from app.connectors.credentials import load_connector_credentials
from app.connectors.http_client import ConnectorHttpClient
from app.connectors.types import FetchResult, HealthCheckResult


class OracleEbsIntegrationAdapter(BaseConnectorAdapter):
    """Call your HTTPS integration layer that wraps EBS APIs."""

    provider = "oracle_erp"

    def _extra(self) -> Dict[str, Any]:
        return dict(self.config.extra or {})

    def _base(self) -> str:
        return (self._extra().get("ebs_integration_base_url") or os.environ.get("ORACLE_EBS_INTEGRATION_BASE_URL") or "").rstrip("/")

    def _headers(self) -> Dict[str, str]:
        h = {"Accept": "application/json"}
        secrets = load_connector_credentials(self.credentials)
        tok = secrets.get("static_bearer_token") or secrets.get("bearer_token")
        if tok:
            h["Authorization"] = f"Bearer {tok}"
        user = secrets.get("basic_user")
        pw = secrets.get("basic_password")
        if user and pw:
            import base64

            b = base64.b64encode(f"{user}:{pw}".encode()).decode()
            h["Authorization"] = f"Basic {b}"
        return h

    def expected_schema(self, domain: str) -> Dict[str, Any]:
        return {"required": ["id", "entity", "created_at", "source_system"]}

    def normalize(self, domain: str, record: Dict[str, Any]) -> Dict[str, Any]:
        return normalize_generic(
            domain,
            record,
            entity_code=self.config.entity_code,
            source_system=str(self._extra().get("source_system_label") or "ORACLE-EBS"),
        )

    async def health_check(self) -> HealthCheckResult:
        base = self._base()
        if not base:
            return HealthCheckResult(
                ok=False,
                message="EBS integration: set config.extra.ebs_integration_base_url",
                details={"pattern": "ebs_integration"},
            )
        try:
            http = ConnectorHttpClient()
            path = self._extra().get("ebs_health_path", "/health")
            r = await http.request("GET", f"{base}{path}", headers=self._headers())
            return HealthCheckResult(ok=True, message="EBS integration tier reachable", details={"pattern": "ebs_integration"})
        except Exception as e:  # noqa: BLE001
            return HealthCheckResult(ok=False, message=str(e), details={"pattern": "ebs_integration"})

    async def fetch_domain(self, *, domain: str, cursor: Optional[str], mode: str) -> FetchResult:
        base = self._base()
        if not base:
            return FetchResult(domain=domain, records=[], cursor=None)
        tmpl = self._extra().get("ebs_fetch_path_template") or "/api/v1/domains/{domain}"
        url = f"{base}{tmpl.replace('{domain}', domain)}"
        params = {"mode": mode}
        if cursor:
            params["cursor"] = cursor
        full = f"{url}?{urlencode(params)}"
        http = ConnectorHttpClient()
        r = await http.request("GET", full, headers=self._headers())
        body = r.json()
        recs = list(body.get("records") or body.get("items") or body.get("value") or [])
        nxt = body.get("next_cursor") or body.get("nextCursor")
        return FetchResult(domain=domain, records=recs, cursor=str(nxt) if nxt else None)
