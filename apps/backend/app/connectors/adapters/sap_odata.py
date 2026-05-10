"""SAP S/4HANA (Cloud / API-enabled on-prem) — OData / CDS with OAuth2 client credentials.

Production: call through API Gateway / SAP Cloud Integration (CPI) HTTPS if direct OData is not exposed.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urljoin

from app.connectors.adapters._normalize import normalize_generic, normalize_vendor_sap
from app.connectors.adapters.base import BaseConnectorAdapter
from app.connectors.credentials import load_connector_credentials
from app.connectors.http_client import ConnectorHttpClient
from app.connectors.types import FetchResult, HealthCheckResult


DEFAULT_ENTITY_SETS: Dict[str, str] = {
    "vendors": "A_BusinessPartner",
    "invoices": "A_SupplierInvoice",
    "payments": "A_SupplierPayment",
    "journals": "A_GLAccountLineItem",
    "purchase_orders": "A_PurchaseOrder",
    "goods_receipts": "A_MaterialDocumentHeader",
}


class SapODataAdapter(BaseConnectorAdapter):
    """OData v2/v4 style JSON: ``{ "value": [...], "@odata.nextLink": "..." }``."""

    provider = "sap"

    def _extra(self) -> Dict[str, Any]:
        return dict(self.config.extra or {})

    def _entity_set(self, domain: str) -> str:
        custom = self._extra().get("sap_domain_entity_sets") or {}
        merged = {**DEFAULT_ENTITY_SETS, **custom}
        return str(merged.get(domain) or f"ZZ_{domain.upper()}")

    def _page_size(self) -> int:
        return int(self._extra().get("page_size") or os.environ.get("SAP_ODATA_PAGE_SIZE", "200"))

    def _source_label(self) -> str:
        return str(self._extra().get("source_system_label") or "SAP-ODATA")

    def expected_schema(self, domain: str) -> Dict[str, Any]:
        base = {"required": ["id", "entity", "created_at", "source_system"]}
        if domain == "vendors":
            return {**base, "required": base["required"] + ["vendor_code", "vendor_name", "status"]}
        if domain == "invoices":
            return {**base, "required": base["required"] + ["invoice_number", "vendor_id", "amount", "invoice_date", "status"]}
        if domain == "payments":
            return {**base, "required": base["required"] + ["payment_ref", "vendor_id", "amount", "payment_date", "status"]}
        if domain == "journals":
            return {**base, "required": base["required"] + ["journal_number", "amount", "created_by", "created_at"]}
        if domain == "purchase_orders":
            return {**base, "required": base["required"] + ["po_number", "vendor_id", "amount", "po_date", "status"]}
        if domain == "goods_receipts":
            return {**base, "required": base["required"] + ["grn_number", "po_id", "received_date", "status"]}
        return base

    async def _oauth_token(self, http: ConnectorHttpClient) -> str:
        secrets = load_connector_credentials(self.credentials)
        cid = secrets.get("client_id") or secrets.get("CLIENT_ID")
        csec = secrets.get("client_secret") or secrets.get("CLIENT_SECRET")
        if not cid or not csec:
            raise OSError("SAP OData: missing client_id/client_secret (env_ref JSON or vault_ref)")
        ex = self._extra()
        token_url = ex.get("token_url") or os.environ.get("SAP_OAUTH_TOKEN_URL")
        if not token_url:
            raise OSError("SAP OData: set config.extra.token_url or SAP_OAUTH_TOKEN_URL")
        scope = ex.get("oauth_scope") or os.environ.get("SAP_OAUTH_SCOPE", "")
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
            raise OSError(f"SAP OAuth: no access_token in response keys={list(data.keys())}")
        return str(tok)

    async def health_check(self) -> HealthCheckResult:
        ex = self._extra()
        base = (ex.get("base_url") or os.environ.get("SAP_ODATA_BASE_URL") or "").rstrip("/")
        if not base:
            return HealthCheckResult(
                ok=False,
                message="SAP OData: set config.extra.base_url (service root) or SAP_ODATA_BASE_URL",
                details={"pattern": "odata"},
            )
        try:
            http = ConnectorHttpClient()
            token = await self._oauth_token(http)
            es = self._entity_set("vendors")
            probe = f"{base}/{es}?$top=1"
            r = await http.request("GET", probe, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
            return HealthCheckResult(
                ok=True,
                message="SAP OData reachable (OAuth + sample entity set)",
                details={"pattern": "odata", "entity_set": es, "status": r.status_code},
            )
        except Exception as e:  # noqa: BLE001
            return HealthCheckResult(ok=False, message=str(e), details={"pattern": "odata", "type": type(e).__name__})

    def normalize(self, domain: str, record: Dict[str, Any]) -> Dict[str, Any]:
        ent = self.config.entity_code
        src = self._source_label()
        if domain == "vendors":
            mapped = {
                "vendor_code": record.get("BusinessPartner") or record.get("Supplier") or record.get("vendor_code"),
                "vendor_name": record.get("BusinessPartnerFullName") or record.get("OrganizationBPName1") or record.get("vendor_name"),
                "status": record.get("BusinessPartnerGrouping") or record.get("AuthorizationGroup") or "active",
                "id": record.get("BusinessPartner") or record.get("id"),
            }
            return normalize_vendor_sap({**record, **{k: v for k, v in mapped.items() if v is not None}}, entity_code=ent, source_system=src)
        return normalize_generic(domain, record, entity_code=ent, source_system=src)

    async def fetch_domain(self, *, domain: str, cursor: Optional[str], mode: str) -> FetchResult:
        ex = self._extra()
        base = (ex.get("base_url") or os.environ.get("SAP_ODATA_BASE_URL") or "").rstrip("/")
        if not base:
            return FetchResult(domain=domain, records=[], cursor=None)

        http = ConnectorHttpClient()
        token = await self._oauth_token(http)
        es = self._entity_set(domain)
        top = self._page_size()

        incremental_field = ex.get("sap_incremental_field")  # e.g. LastChangeDateTime
        watermark = ex.get("watermark_changed_after") or ex.get("changed_after")  # ISO string for incremental

        if cursor and (cursor.startswith("http://") or cursor.startswith("https://")):
            url = cursor
        else:
            q: Dict[str, str] = {"$top": str(top)}
            if cursor:
                q["$skiptoken"] = cursor
            if mode != "backfill" and incremental_field and watermark:
                # OData v2 filter example — customer may override filter template
                filt = ex.get("sap_incremental_filter") or f"{incremental_field} ge datetimeoffset'{watermark}'"
                q["$filter"] = filt
            url = f"{base}/{es}?{urlencode(q)}"

        r = await http.request("GET", url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
        payload = r.json()
        rows: List[Dict[str, Any]] = list(payload.get("value") or payload.get("d", {}).get("results") or [])
        next_cursor: Optional[str] = None
        next_link = payload.get("@odata.nextLink") or payload.get("odata.nextLink")
        if isinstance(next_link, str) and next_link.startswith("http"):
            next_cursor = next_link
        elif isinstance(next_link, str):
            next_cursor = urljoin(base + "/", next_link.lstrip("/"))

        return FetchResult(domain=domain, records=rows, cursor=next_cursor)
