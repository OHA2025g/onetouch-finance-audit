from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from app.connectors.adapters._normalize import normalize_generic, normalize_journal
from app.connectors.adapters.base import BaseConnectorAdapter
from app.connectors.types import FetchResult, HealthCheckResult
from app.utils.timeutil import iso_utc


class MockSapAdapter(BaseConnectorAdapter):
    provider = "sap"

    async def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(ok=True, message="mock SAP adapter OK", details={"mode": "mock"})

    def expected_schema(self, domain: str) -> Dict[str, Any]:
        base = {"required": ["id", "entity", "created_at", "source_system"]}
        if domain == "vendors":
            return {**base, "required": base["required"] + ["vendor_code", "vendor_name", "status"]}
        if domain == "invoices":
            return {**base, "required": base["required"] + ["invoice_number", "vendor_id", "amount", "invoice_date", "status"]}
        if domain == "payments":
            return {**base, "required": base["required"] + ["payment_ref", "vendor_id", "amount", "payment_date", "status"]}
        if domain == "journals":
            return {
                **base,
                "required": base["required"] + ["journal_number", "amount", "created_by", "created_at", "posting_date"],
            }
        if domain == "purchase_orders":
            return {**base, "required": base["required"] + ["po_number", "vendor_id", "amount", "po_date", "status"]}
        if domain == "goods_receipts":
            return {**base, "required": base["required"] + ["grn_number", "po_id", "received_date", "status"]}
        return base

    async def fetch_domain(
        self,
        *,
        domain: str,
        cursor: Optional[str],
        mode: str,
    ) -> FetchResult:
        # Deterministic-enough for tests and UI: generate a small batch
        now = iso_utc(datetime.now(timezone.utc))
        ent = self.config.entity_code
        src = "SAP-MOCK"
        recs: list[dict[str, Any]] = []

        def _id(prefix: str) -> str:
            return f"{prefix}-SAP-{uuid.uuid4().hex[:8]}"

        if domain == "vendors":
            for i in range(3):
                recs.append(
                    {
                        "id": _id("V"),
                        "vendor_code": f"SAPV{i+1000}",
                        "vendor_name": f"SAP Vendor {i+1}",
                        "entity": ent,
                        "bank_account_hash": f"HASH{uuid.uuid4().hex[:6]}",
                        "bank_changed_at": now,
                        "status": "active",
                        "created_at": now,
                        "source_system": src,
                    }
                )
        elif domain == "invoices":
            for i in range(3):
                vid = _id("V")
                recs.append(
                    {
                        "id": _id("INV"),
                        "invoice_number": f"SAP-INV-{i+1}",
                        "vendor_id": vid,
                        "vendor_name": f"SAP Vendor {i+1}",
                        "entity": ent,
                        "invoice_date": now,
                        "amount": float(1000 + i * 250),
                        "tax_amount": float(180 + i * 10),
                        "expected_tax_amount": float(180 + i * 10),
                        "status": "posted",
                        "po_id": None,
                        "approver_email": "controller@onetouch.ai",
                        "created_at": now,
                        "source_system": src,
                    }
                )
        elif domain == "payments":
            for i in range(3):
                recs.append(
                    {
                        "id": _id("PAY"),
                        "payment_ref": f"SAP-PAY-{i+1}",
                        "vendor_id": _id("V"),
                        "vendor_name": f"SAP Vendor {i+1}",
                        "invoice_id": None,
                        "entity": ent,
                        "payment_date": now,
                        "amount": float(900 + i * 120),
                        "status": "settled",
                        "created_at": now,
                        "source_system": src,
                    }
                )
        elif domain == "journals":
            now_dt = datetime.now(timezone.utc)
            scenarios = [
                {
                    "journal_number": "SAP-JRN-1",
                    "amount": 125_000.0,
                    "created_by": "gl.lead@onetouch.ai",
                    "approver_email": "controller@onetouch.ai",
                    "posting_date": iso_utc(now_dt - timedelta(days=2)),
                    "created_at": iso_utc(now_dt - timedelta(days=2)),
                },
                {
                    "journal_number": "SAP-JRN-2",
                    "amount": 85_000.0,
                    "created_by": "gl.lead@onetouch.ai",
                    "approver_email": None,
                    "posting_date": iso_utc(now_dt - timedelta(days=25)),
                    "created_at": iso_utc(now_dt - timedelta(days=1)),
                },
                {
                    "journal_number": "SAP-JRN-3",
                    "amount": 42_000.0,
                    "created_by": "ap.clerk@onetouch.ai",
                    "approver_email": "controller@onetouch.ai",
                    "posting_date": iso_utc(now_dt - timedelta(days=5)),
                    "created_at": iso_utc(now_dt - timedelta(days=5)),
                },
            ]
            for i, sc in enumerate(scenarios):
                recs.append(
                    {
                        "id": _id("JRN"),
                        "entity": ent,
                        "currency": self.config.base_currency,
                        "description": "SAP mock journal",
                        "source_system": src,
                        **sc,
                    }
                )
        else:
            recs = []

        return FetchResult(domain=domain, records=recs, cursor=None)

    def normalize(self, domain: str, record: Dict[str, Any]) -> Dict[str, Any]:
        ent = self.config.entity_code
        src = str(record.get("source_system") or "SAP-MOCK")
        base = normalize_generic(domain, record, entity_code=ent, source_system=src)
        if domain == "journals":
            return normalize_journal(base)
        return base

