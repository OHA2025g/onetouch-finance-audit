from app.connectors.validation import validate_required_fields
from app.connectors.adapters.mock_sap import MockSapAdapter
from app.connectors.adapters.mock_oracle import MockOracleErpAdapter
from app.connectors.types import ConnectorConfig, ConnectorCredentialRef


def test_schema_validation_required() -> None:
    ok, rep = validate_required_fields({"required": ["id", "name"]}, [{"id": "1", "name": "x"}, {"id": "2"}])
    assert ok is False
    assert rep["violations"] == 1

def test_mock_sap_fetch_has_ids() -> None:
    import asyncio
    ad = MockSapAdapter(config=ConnectorConfig(entity_code="US-HQ"), credentials=ConnectorCredentialRef(id="c1", kind="none"))
    fr = asyncio.run(ad.fetch_domain(domain="vendors", cursor=None, mode="sync"))
    assert fr.domain == "vendors"
    assert len(fr.records) > 0
    assert all("id" in r for r in fr.records)


def test_mock_oracle_health_ok() -> None:
    import asyncio
    ad = MockOracleErpAdapter(config=ConnectorConfig(entity_code="US-HQ"), credentials=ConnectorCredentialRef(id="c1", kind="none"))
    h = asyncio.run(ad.health_check())
    assert h.ok is True

