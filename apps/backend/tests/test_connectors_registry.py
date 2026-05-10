"""Unit tests for connector adapter registry + credential ref parsing."""

from __future__ import annotations

from app.connectors.adapters.mock_oracle import MockOracleErpAdapter
from app.connectors.adapters.mock_sap import MockSapAdapter
from app.connectors.adapters.oracle_ebs_integration import OracleEbsIntegrationAdapter
from app.connectors.adapters.oracle_fusion_rest import OracleFusionRestAdapter
from app.connectors.adapters.oracle_oci_replica import OracleOciReplicaAdapter
from app.connectors.adapters.sap_cpi_http import SapCpiHttpAdapter
from app.connectors.adapters.sap_datasphere import SapDatasphereAdapter
from app.connectors.adapters.sap_odata import SapODataAdapter
from app.connectors.registry import get_adapter_class
from app.services.connector_service import _parse_cred_ref


def test_get_adapter_class_sap_patterns():
    assert get_adapter_class("sap", None) is MockSapAdapter
    assert get_adapter_class("sap", {}) is MockSapAdapter
    assert get_adapter_class("sap", {"extra": {}}) is MockSapAdapter
    assert get_adapter_class("sap", {"extra": {"connection_pattern": "mock"}}) is MockSapAdapter
    assert get_adapter_class("sap", {"extra": {"connection_pattern": "odata"}}) is SapODataAdapter
    assert get_adapter_class("sap", {"extra": {"connection_pattern": "cpi_http"}}) is SapCpiHttpAdapter
    assert get_adapter_class("sap", {"extra": {"connection_pattern": "datasphere"}}) is SapDatasphereAdapter


def test_get_adapter_class_oracle_patterns():
    assert get_adapter_class("oracle_erp", {}) is MockOracleErpAdapter
    assert get_adapter_class("oracle_erp", {"extra": {"connection_pattern": "fusion_rest"}}) is OracleFusionRestAdapter
    assert get_adapter_class("oracle_erp", {"extra": {"connection_pattern": "ebs_integration"}}) is OracleEbsIntegrationAdapter
    assert get_adapter_class("oracle_erp", {"extra": {"connection_pattern": "oci_replica"}}) is OracleOciReplicaAdapter


def test_parse_cred_ref_vault():
    r = _parse_cred_ref(
        {
            "kind": "vault_ref",
            "vault_provider": "env_bridge",
            "vault_secret_id": "MY_SECRET_JSON",
        }
    )
    assert r.kind == "vault_ref"
    assert r.vault_secret_id == "MY_SECRET_JSON"
    assert r.vault_provider == "env_bridge"
