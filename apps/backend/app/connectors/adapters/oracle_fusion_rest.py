"""Oracle Fusion Cloud ERP — REST APIs with OAuth2 (IDCS client credentials).

Respect API version in path (``fscmRestApi/resources/{version}/...``) and rate limits (429 handled in http client).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from app.connectors.adapters._normalize import normalize_generic
from app.connectors.adapters.base import BaseConnectorAdapter
from app.connectors.credentials import load_connector_credentials
from app.connectors.http_client import ConnectorHttpClient
from app.connectors.types import FetchResult, HealthCheckResult


DEFAULT_FUSION_RESOURCES: Dict[str, str] = {
    "customers": "customers",
    "ar_invoices": "receivablesInvoices",
    "sales_orders": "salesOrdersForOrderHub",
    "employees": "emps",
    "payroll_entries": "payrollRelationships",
    "bank_transactions": "cashBankAccounts",
    "fixed_assets": "assets",
    "tax_records": "taxRates",
}


class OracleFusionRestAdapter(BaseConnectorAdapter):
    provider = "oracle_erp"

    def _extra(self) -> Dict[str, Any]:
        return dict(self.config.extra or {})

    def _host(self) -> str:
        return (self._extra().get("fusion_host") or os.environ.get("ORACLE_FUSION_HOST") or "").rstrip("/")

    def _api_version(self) -> str:
        return str(self._extra().get("fusion_api_version") or os.environ.get("ORACLE_FUSION_API_VERSION", "11.13.18.05"))

    def _resource(self, domain: str) -> str:
        m = {**DEFAULT_FUSION_RESOURCES, **(self._extra().get("fusion_domain_resources") or {})}
        return str(m.get(domain) or domain)

    def _page_size(self) -> int:
        return int(self._extra().get("page_size") or os.environ.get("ORACLE_FUSION_PAGE_SIZE", "100"))

    def expected_schema(self, domain: str) -> Dict[str, Any]:
        base = {"required": ["id", "entity", "created_at", "source_system"]}
        if domain == "customers":
            return {**base, "required": base["required"] + ["customer_code", "customer_name", "status"]}
        if domain == "ar_invoices":
            return {**base, "required": base["required"] + ["invoice_number", "customer_id", "amount", "invoice_date", "status"]}
        return base

    async def _oauth_token(self, http: ConnectorHttpClient) -> str:
        secrets = load_connector_credentials(self.credentials)
        cid = secrets.get("client_id") or secrets.get("CLIENT_ID")
        csec = secrets.get("client_secret") or secrets.get("CLIENT_SECRET")
        scope = secrets.get("scope") or self._extra().get("oauth_scope") or os.environ.get("ORACLE_FUSION_SCOPE", "")
        token_url = self._extra().get("token_url") or os.environ.get("ORACLE_FUSION_TOKEN_URL")
        if not all([cid, csec, token_url]):
            raise OSError("Oracle Fusion: need client_id, client_secret, token_url (JSON env or vault)")
        body = {"grant_type": "client_credentials", "client_id": str(cid), "client_secret": str(csec)}
        if scope:
            body["scope"] = scope
        resp = await http.request(
            "POST",
            str(token_url),
            data=urlencode(body),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        data = resp.json()
        tok = data.get("access_token")
        if not tok:
            raise OSError(f"Oracle Fusion OAuth: no access_token keys={list(data.keys())}")
        return str(tok)

    def normalize(self, domain: str, record: Dict[str, Any]) -> Dict[str, Any]:
        ent = self.config.entity_code
        src = str(self._extra().get("source_system_label") or "ORACLE-FUSION")
        if domain == "customers":
            rec = {
                **record,
                "customer_code": record.get("CustomerNumber") or record.get("customer_code") or record.get("CustomerId"),
                "customer_name": record.get("CustomerName") or record.get("customer_name") or "",
                "id": record.get("CustomerId") or record.get("id"),
                "status": record.get("Status") or "active",
            }
        else:
            rec = {**record, "id": record.get("InvoiceId") or record.get("TransactionId") or record.get("id")}
        return normalize_generic(domain, rec, entity_code=ent, source_system=src)

    async def health_check(self) -> HealthCheckResult:
        host = self._host()
        if not host:
            return HealthCheckResult(
                ok=False,
                message="Oracle Fusion: set config.extra.fusion_host or ORACLE_FUSION_HOST",
                details={"pattern": "fusion_rest"},
            )
        try:
            http = ConnectorHttpClient()
            token = await self._oauth_token(http)
            ver = self._api_version()
            res = self._resource("customers")
            url = f"{host}/fscmRestApi/resources/{ver}/{res}?onlyData=true&limit=1"
            r = await http.request("GET", url, headers={"Authorization": f"Bearer {token}", "REST-Framework-Version": "2"})
            return HealthCheckResult(ok=True, message="Oracle Fusion REST reachable", details={"pattern": "fusion_rest", "resource": res})
        except Exception as e:  # noqa: BLE001
            return HealthCheckResult(ok=False, message=str(e), details={"pattern": "fusion_rest"})

    async def fetch_domain(self, *, domain: str, cursor: Optional[str], mode: str) -> FetchResult:
        host = self._host()
        if not host:
            return FetchResult(domain=domain, records=[], cursor=None)
        http = ConnectorHttpClient()
        token = await self._oauth_token(http)
        ver = self._api_version()
        res = self._resource(domain)
        limit = self._page_size()
        offset = int(cursor or "0")
        q = {"onlyData": "true", "limit": str(limit), "offset": str(offset)}
        url = f"{host}/fscmRestApi/resources/{ver}/{res}?{urlencode(q)}"
        r = await http.request("GET", url, headers={"Authorization": f"Bearer {token}", "REST-Framework-Version": "2"})
        body = r.json()
        items: List[Dict[str, Any]] = list(body.get("items") or body.get("rows") or [])
        has_more = body.get("hasMore") is True or len(items) >= limit
        next_cursor = str(offset + limit) if has_more and items else None
        return FetchResult(domain=domain, records=items, cursor=next_cursor)
