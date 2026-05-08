from __future__ import annotations

from typing import Dict

from app.connectors.types import ConnectorProvider

from app.connectors.adapters.base import BaseConnectorAdapter
from app.connectors.adapters.mock_sap import MockSapAdapter
from app.connectors.adapters.mock_oracle import MockOracleErpAdapter


_REGISTRY: Dict[ConnectorProvider, type[BaseConnectorAdapter]] = {
    "sap": MockSapAdapter,
    "oracle_erp": MockOracleErpAdapter,
}


def get_adapter_class(provider: ConnectorProvider) -> type[BaseConnectorAdapter]:
    return _REGISTRY[provider]

