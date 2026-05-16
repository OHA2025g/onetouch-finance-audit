"""Rollup FX: functional currency + conversion into reporting USD."""

from __future__ import annotations

from app.services.rollup_service import (
    convert_amount_to_reporting_usd,
    exposure_currency_for_exception,
    functional_currency_for_entity,
)


def test_functional_currency_for_known_entities() -> None:
    assert functional_currency_for_entity("UK-OPS") == "GBP"
    assert functional_currency_for_entity("IN-SVC") == "INR"
    assert functional_currency_for_entity("US-HQ") == "USD"
    assert functional_currency_for_entity("SG-APAC") == "USD"


def test_functional_currency_unknown_defaults_usd() -> None:
    assert functional_currency_for_entity("ZZ-UNKNOWN") == "USD"
    assert functional_currency_for_entity(None) == "USD"


def test_exception_currency_override() -> None:
    exc = {"entity": "IN-SVC", "exposure_currency": "EUR", "financial_exposure": 100}
    assert exposure_currency_for_exception(exc) == "EUR"
    exc2 = {"entity": "IN-SVC", "currency": "GBP"}
    assert exposure_currency_for_exception(exc2) == "GBP"


def test_convert_inr_and_gbp_using_rates() -> None:
    rates = {"USD": 1.0, "INR": 0.012, "GBP": 1.27}
    assert convert_amount_to_reporting_usd(10000.0, "INR", rates) == 120.0
    assert convert_amount_to_reporting_usd(1000.0, "GBP", rates) == 1270.0
    assert convert_amount_to_reporting_usd(50.0, "USD", rates) == 50.0


def test_convert_falls_back_when_rate_missing() -> None:
    rates = {"USD": 1.0}
    # Fallback map includes INR
    out = convert_amount_to_reporting_usd(10000.0, "INR", rates)
    assert out == 120.0


def test_drill_path_in_rollup_envelope() -> None:
    from app.services.rollup_service import _rollup_envelope

    env = _rollup_envelope()
    assert "drill_path" in env
    assert env["drill_path"]["reporting_currency_default"] == "USD"
    levels = env["drill_path"]["levels"]
    assert any(x.get("key") == "process" for x in levels)
