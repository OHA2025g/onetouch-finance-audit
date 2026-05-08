"""API path aliases and naming policy (Wave 0).

**Integrations vs connectors:** HTTP handlers for the connector console are mounted at
both ``/api/connectors`` (primary) and ``/api/integrations`` (SRS / product alias).
Responses are identical.

**Dashboards vs CFO BFF:** Persona dashboards remain under ``/api/dashboard/*``.
CFO-oriented aggregates are also exposed under ``/api/cfo/*`` where noted in OpenAPI
(aliases for executive clients that expect a ``/cfo`` namespace).

**Working capital / treasury trees:** REST-style namespaces ``/api/working-capital``,
``/api/ar``, ``/api/ap``, ``/api/treasury`` delegate to the same analytics functions
as ``/api/dashboard/working-capital`` and ``/api/dashboard/treasury`` for contract
stability without duplicating business logic.

OpenAPI is the source of truth; breaking path changes require a version bump or an
explicit compatibility alias maintained for at least one release.
"""
