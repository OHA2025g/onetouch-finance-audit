from __future__ import annotations

from typing import Any, Dict, Type

from app.connectors.types import ConnectorProvider

from app.connectors.adapters.base import BaseConnectorAdapter
from app.connectors.adapters.mock_sap import MockSapAdapter
from app.connectors.adapters.mock_oracle import MockOracleErpAdapter
from app.connectors.adapters.oracle_ebs_integration import OracleEbsIntegrationAdapter
from app.connectors.adapters.oracle_fusion_rest import OracleFusionRestAdapter
from app.connectors.adapters.oracle_oci_replica import OracleOciReplicaAdapter
from app.connectors.adapters.sap_cpi_http import SapCpiHttpAdapter
from app.connectors.adapters.sap_datasphere import SapDatasphereAdapter
from app.connectors.adapters.sap_odata import SapODataAdapter


def _pattern(config: Dict[str, Any] | None) -> str:
    raw = (config or {}).get("extra")
    ex: Dict[str, Any] = raw if isinstance(raw, dict) else {}
    return str(ex.get("connection_pattern") or "mock").strip().lower()


def get_adapter_class(provider: ConnectorProvider, config: Dict[str, Any] | None = None) -> Type[BaseConnectorAdapter]:
    """Resolve adapter from ``provider`` + ``config.extra.connection_pattern``.

    Patterns (SAP): ``mock`` | ``odata`` | ``cpi_http`` | ``datasphere``
    Patterns (Oracle ERP): ``mock`` | ``fusion_rest`` | ``ebs_integration`` | ``oci_replica``
    """
    pat = _pattern(config)
    if provider == "sap":
        if pat == "odata":
            return SapODataAdapter
        if pat == "cpi_http":
            return SapCpiHttpAdapter
        if pat == "datasphere":
            return SapDatasphereAdapter
        return MockSapAdapter
    if provider == "oracle_erp":
        if pat == "fusion_rest":
            return OracleFusionRestAdapter
        if pat == "ebs_integration":
            return OracleEbsIntegrationAdapter
        if pat == "oci_replica":
            return OracleOciReplicaAdapter
        return MockOracleErpAdapter
    return MockSapAdapter
