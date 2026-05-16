"""ASGI app factory: routers, middleware, event handlers, exception wiring."""
from __future__ import annotations
import os

from fastapi import APIRouter, FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.core.exceptions import register_exception_handlers
from app.core.logging_config import configure_logging
from app.lifecycle import on_shutdown, on_startup
from app.middleware.stack import CorrelationErrorMiddleware
from app.routers.auth_router import router as auth_router
from app.routers.dashboards_router import router as dashboards_router
from app.routers.controls_router import router as controls_router
from app.routers.cases_router import router as cases_router
from app.routers.evidence_ai_router import router as evidence_ai_router
from app.routers.admin_router import router as admin_router
from app.routers.rollups_router import router as rollups_router
from app.routers.retention_router import router as retention_router
from app.routers.legal_holds_router import router as legal_holds_router
from app.routers.connectors_router import router as connectors_router
from app.routers.dq_router import router as dq_router
from app.routers.governance_router import router as governance_router
from app.routers.system_router import router as system_router
from app.routers.ca_audit_engagements import router as ca_audit_engagements_router
from app.routers.ca_audit_modules import router as ca_audit_modules_router
from app.routers.masters_router import router as masters_router
from app.routers.finance_team_router import router as finance_team_router
from app.routers.finance_rest_router import (
    wc_router,
    ar_router,
    ap_router,
    treasury_router,
    budget_router,
    forecast_router,
    srs_budget_vs_actual_router,
    srs_forecast_vs_actual_router,
)
from app.routers.gl_router import router as gl_router
from app.routers.journals_router import router as journals_router
from app.routers.reconciliations_router import router as reconciliations_router
from app.routers.bank_recon_router import router as bank_recon_router
from app.routers.vendor_risk_router import router as vendor_risk_router
from app.routers.three_way_match_router import router as three_way_match_router
from app.routers.o2c_router import router as o2c_router
from app.routers.credit_notes_router import router as credit_notes_router
from app.routers.inventory_audit_router import router as inventory_audit_router
from app.routers.physical_verification_router import router as physical_verification_router
from app.routers.fixed_assets_audit_router import router as fixed_assets_audit_router
from app.routers.forex_router import router as forex_router
from app.routers.rpt_router import router as rpt_router
from app.routers.legal_router import router as legal_router
from app.routers.doa_router import router as doa_router
from app.routers.policies_router import router as policies_router
from app.routers.access_router import router as access_router
from app.routers.master_data_quality_router import router as master_data_quality_router
from app.routers.evidence_intelligence_router import router as evidence_intelligence_router
from app.routers.continuous_audit_router import router as continuous_audit_router
from app.routers.risk_intelligence_router import router as risk_intelligence_router
from app.routers.audit_compliance_router import router as audit_compliance_router
from app.routers.governance_depth_router import router as governance_depth_router
from app.routers.board_reporting_router import router as board_reporting_router
from app.routers.kpi_router import router as kpi_router
from app.routers.cfo_router import router as cfo_router
from app.routers.close_router import router as close_router


def create_app() -> FastAPI:
    configure_logging()
    application = FastAPI(title="One Touch Audit AI")
    register_exception_handlers(application)
    # Last add_middleware is outer (browser hits CORS first, then correlation + 500 boundary).
    application.add_middleware(CorrelationErrorMiddleware)
    # Wildcard + allow_credentials=True is invalid for browsers; JWT uses Authorization header (no cookies), so credentials off + * is fine.
    _cors_raw = os.environ.get("CORS_ORIGINS", "*").strip()
    _origins = [o.strip() for o in _cors_raw.split(",") if o.strip()] or ["*"]
    _wildcard = _origins == ["*"]
    application.add_middleware(
        CORSMiddleware,
        allow_credentials=not _wildcard,
        allow_origins=_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api = APIRouter(prefix="/api")

    @api.get("/")
    async def health():
        return {"service": "One Touch Audit AI", "status": "ok"}

    for r in (auth_router, reconciliations_router, dashboards_router, controls_router, cases_router, evidence_ai_router, admin_router,
              rollups_router, retention_router, legal_holds_router, dq_router, governance_router,
              system_router,
              kpi_router,
              cfo_router,
              close_router,
              ca_audit_engagements_router, ca_audit_modules_router, masters_router,
              journals_router):
        api.include_router(r)

    api.include_router(finance_team_router)
    for fr in (
        wc_router,
        ar_router,
        ap_router,
        treasury_router,
        srs_budget_vs_actual_router,
        srs_forecast_vs_actual_router,
        budget_router,
        forecast_router,
    ):
        api.include_router(fr)
    api.include_router(gl_router)
    api.include_router(bank_recon_router)
    api.include_router(vendor_risk_router)
    api.include_router(three_way_match_router)
    api.include_router(o2c_router)
    api.include_router(credit_notes_router)
    api.include_router(inventory_audit_router)
    api.include_router(physical_verification_router)
    api.include_router(fixed_assets_audit_router)
    api.include_router(forex_router)
    api.include_router(rpt_router)
    api.include_router(legal_router)
    api.include_router(doa_router)
    api.include_router(policies_router)
    api.include_router(access_router)
    api.include_router(master_data_quality_router)
    api.include_router(evidence_intelligence_router)
    api.include_router(continuous_audit_router)
    api.include_router(risk_intelligence_router)
    api.include_router(audit_compliance_router)
    api.include_router(governance_depth_router)
    api.include_router(board_reporting_router)

    # Same connector handlers under SRS-preferred ``/integrations`` paths.
    # IMPORTANT: register more specific prefix first to avoid route shadowing
    # (e.g. /integrations/{connector_id} intercepting /integrations/connectors).
    api.include_router(connectors_router, prefix="/integrations/connectors")  # Phase 38 SRS path
    api.include_router(connectors_router, prefix="/connectors")
    api.include_router(connectors_router, prefix="/integrations")

    application.include_router(api)
    application.add_event_handler("startup", on_startup)
    application.add_event_handler("shutdown", on_shutdown)
    return application


# Default module export for Uvicorn and importers: ``from app.main import app``
app = create_app()
