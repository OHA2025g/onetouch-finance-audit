"""Data-access layer: queries and collection-specific helpers (expand incrementally).

Routers and services should call into repositories for MongoDB details so that
tests can mock a narrow surface and business rules stay in ``app.services``.
"""
