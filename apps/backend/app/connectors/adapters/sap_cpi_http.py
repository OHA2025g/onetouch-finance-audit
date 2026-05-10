"""SAP via Integration Suite (CPI) or API Gateway — HTTPS JSON contract (no direct RFC).

OneTouch calls *your* exposed HTTPS endpoints; CPI maps to BAPI/RFC/OData inside the landscape.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from app.connectors.adapters._normalize import normalize_generic, normalize_vendor_sap
from app.connectors.adapters.base import BaseConnectorAdapter
from app.connectors.credentials import load_connector_credentials
from app.connectors.http_client import ConnectorHttpClient
from app.connectors.types import FetchResult, HealthCheckResult


class SapCpiHttpAdapter(BaseConnectorAdapter):
    """Expected JSON: ``{ "records": [...], "next_cursor": "..." }`` (cursor opaque)."""

    provider = "sap"

    def _extra(self) -> Dict[str, Any]:
        return dict(self.config.extra or {})

    def _cpi_base(self) -> str:
        return (self._extra().get("cpi_exposed_base_url") or os.environ.get("SAP_CPI_EXPOSED_BASE_URL") or "").rstrip("/")

    def _auth_header(self) -> Dict[str, str]:
        secrets = load_connector_credentials(self.credentials)
        token = secrets.get("static_bearer_token") or secrets.get("bearer_token") or os.environ.get("SAP_CPI_STATIC_BEARER")
        if token:
            return {"Authorization": f"Bearer {token}"}
        api_key = secrets.get("api_key") or os.environ.get("SAP_CPI_API_KEY")
        if api_key:
            return {"X-API-Key": str(api_key)}
        return {}

    def expected_schema(self, domain: str) -> Dict[str, Any]:
        base = {"required": ["id", "entity", "created_at", "source_system"]}
        if domain == "vendors":
            return {**base, "required": base["required"] + ["vendor_code", "vendor_name", "status"]}
        return base

    def normalize(self, domain: str, record: Dict[str, Any]) -> Dict[str, Any]:
        ent = self.config.entity_code
        src = str(self._extra().get("source_system_label") or "SAP-CPI")
        if domain == "vendors":
            return normalize_vendor_sap(record, entity_code=ent, source_system=src)
        return normalize_generic(domain, record, entity_code=ent, source_system=src)

    async def health_check(self) -> HealthCheckResult:
        base = self._cpi_base()
        if not base:
            return HealthCheckResult(
                ok=False,
                message="SAP CPI: set config.extra.cpi_exposed_base_url or SAP_CPI_EXPOSED_BASE_URL",
                details={"pattern": "cpi_http"},
            )
        try:
            http = ConnectorHttpClient()
            health_path = self._extra().get("cpi_health_path", "/health")
            r = await http.request("GET", f"{base}{health_path}", headers={**self._auth_header(), "Accept": "application/json"})
            return HealthCheckResult(ok=True, message="SAP CPI HTTPS reachable", details={"pattern": "cpi_http", "status": r.status_code})
        except Exception as e:  # noqa: BLE001
            return HealthCheckResult(ok=False, message=str(e), details={"pattern": "cpi_http"})

    async def fetch_domain(self, *, domain: str, cursor: Optional[str], mode: str) -> FetchResult:
        base = self._cpi_base()
        if not base:
            return FetchResult(domain=domain, records=[], cursor=None)
        http = ConnectorHttpClient()
        path = self._extra().get("cpi_fetch_path_template") or "/v1/extract/{domain}"
        url = f"{base}{(path.replace('{domain}', domain))}"
        params: Dict[str, str] = {"mode": mode}
        if cursor:
            params["cursor"] = cursor
        from urllib.parse import urlencode

        full = f"{url}?{urlencode(params)}"
        r = await http.request("GET", full, headers={**self._auth_header(), "Accept": "application/json"})
        body = r.json()
        recs: List[Dict[str, Any]] = list(body.get("records") or body.get("items") or body.get("value") or [])
        next_c = body.get("next_cursor") or body.get("nextCursor")
        return FetchResult(domain=domain, records=recs, cursor=str(next_c) if next_c else None)
