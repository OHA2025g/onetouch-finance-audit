from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.connectors.adapters.base import BaseConnectorAdapter
from app.connectors.types import FetchResult, HealthCheckResult
from app.utils.timeutil import iso_utc


class MockOracleErpAdapter(BaseConnectorAdapter):
    provider = "oracle_erp"

    async def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(ok=True, message="mock Oracle ERP adapter OK", details={"mode": "mock"})

    def expected_schema(self, domain: str) -> Dict[str, Any]:
        base = {"required": ["id", "entity", "created_at", "source_system"]}
        if domain == "customers":
            return {**base, "required": base["required"] + ["customer_code", "customer_name", "status"]}
        if domain == "sales_orders":
            return {**base, "required": base["required"] + ["order_number", "customer_id", "amount", "order_date", "status"]}
        if domain == "ar_invoices":
            return {**base, "required": base["required"] + ["invoice_number", "customer_id", "amount", "invoice_date", "status"]}
        if domain == "employees":
            return {**base, "required": base["required"] + ["employee_code", "full_name", "status"]}
        if domain == "payroll_entries":
            return {**base, "required": base["required"] + ["employee_id", "payroll_date", "net_pay", "status"]}
        if domain == "bank_transactions":
            return {**base, "required": base["required"] + ["txn_date", "amount", "direction", "status"]}
        if domain == "fixed_assets":
            return {**base, "required": base["required"] + ["asset_tag", "asset_name", "cost", "status"]}
        if domain == "tax_records":
            return {**base, "required": base["required"] + ["tax_type", "period", "amount", "status"]}
        return base

    async def fetch_domain(
        self,
        *,
        domain: str,
        cursor: Optional[str],
        mode: str,
    ) -> FetchResult:
        now = iso_utc(datetime.now(timezone.utc))
        ent = self.config.entity_code
        src = "ORACLE-MOCK"
        recs: list[dict[str, Any]] = []

        def _id(prefix: str) -> str:
            return f"{prefix}-ORCL-{uuid.uuid4().hex[:8]}"

        if domain == "customers":
            for i in range(3):
                recs.append(
                    {
                        "id": _id("CUST"),
                        "customer_code": f"ORCL-C{i+200}",
                        "customer_name": f"Oracle Customer {i+1}",
                        "entity": ent,
                        "status": "active",
                        "created_at": now,
                        "source_system": src,
                    }
                )
        elif domain == "employees":
            for i in range(3):
                recs.append(
                    {
                        "id": _id("EMP"),
                        "employee_code": f"E{i+100}",
                        "full_name": f"Employee {i+1}",
                        "entity": ent,
                        "status": "active",
                        "created_at": now,
                        "source_system": src,
                    }
                )
        elif domain == "bank_transactions":
            for i in range(3):
                recs.append(
                    {
                        "id": _id("BT"),
                        "entity": ent,
                        "txn_date": now,
                        "amount": float(10000 + i * 2500),
                        "direction": "outbound" if i % 2 == 0 else "inbound",
                        "counterparty": f"Counterparty {i+1}",
                        "status": "posted",
                        "created_at": now,
                        "source_system": src,
                    }
                )
        elif domain == "fixed_assets":
            for i in range(2):
                recs.append(
                    {
                        "id": _id("FA"),
                        "entity": ent,
                        "asset_tag": f"AT-{i+1}",
                        "asset_name": f"Asset {i+1}",
                        "cost": float(250000 + i * 50000),
                        "status": "in_service",
                        "created_at": now,
                        "source_system": src,
                    }
                )
        elif domain == "tax_records":
            recs.append(
                {
                    "id": _id("TAX"),
                    "entity": ent,
                    "tax_type": "GST",
                    "period": "2026-03",
                    "amount": 12345.67,
                    "status": "filed",
                    "created_at": now,
                    "source_system": src,
                }
            )
        else:
            recs = []

        return FetchResult(domain=domain, records=recs, cursor=None)

