"""Phase 2 — unified finance master data read APIs."""
from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.auth import get_current_user
from app.core.security import require_roles
from app.deps import db
from app.deps import audit_log
from app.services.rbac_service import enforce_entity_scope
from app.schemas.masters import (
    AuditTrailListResponse,
    BankAccountListResponse,
    BusinessUnitListResponse,
    CompanyListResponse,
    CostCenterListResponse,
    CustomerListResponse,
    DepartmentListResponse,
    DocumentListResponse,
    EmployeeListResponse,
    GLAccountListResponse,
    LegalEntityListResponse,
    LocationListResponse,
    RiskScoreListResponse,
    TransactionHeaderListResponse,
    TransactionLineListResponse,
    VendorListResponse,
)
from app.services import master_data_service as mds
from app.utils.timeutil import iso_utc

router = APIRouter(prefix="/masters", tags=["masters"])


@router.get("/companies", response_model=CompanyListResponse)
async def get_companies(current=Depends(get_current_user)):
    items = await mds.list_companies(db)
    return {"items": items, "count": len(items), "as_of": iso_utc(datetime.now(timezone.utc))}


@router.get("/entities", response_model=LegalEntityListResponse)
async def get_entities(
    entity_code: Optional[str] = Query(None, description="Filter by entity code"),
    current=Depends(get_current_user),
):
    """Legal entities (normalized from `entities` collection)."""
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    items = await mds.list_legal_entities(db, eff)
    return {"items": items, "count": len(items), "as_of": iso_utc(datetime.now(timezone.utc))}


@router.get("/entity-hierarchy")
async def get_entity_hierarchy(current=Depends(get_current_user)):
    """Org tree (delegates to rollup hierarchy collection)."""
    tree = await mds.entity_hierarchy_tree(db)
    return {"items": tree, "count": len(tree), "as_of": iso_utc(datetime.now(timezone.utc))}


@router.get("/business-units", response_model=BusinessUnitListResponse)
async def get_business_units(
    entity_code: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    items = await mds.list_business_units(db, eff)
    return {"items": items, "count": len(items), "as_of": iso_utc(datetime.now(timezone.utc))}


@router.get("/locations", response_model=LocationListResponse)
async def get_locations(
    entity_code: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    items = await mds.list_locations(db, eff)
    return {"items": items, "count": len(items), "as_of": iso_utc(datetime.now(timezone.utc))}


@router.get("/departments", response_model=DepartmentListResponse)
async def get_departments(
    entity_code: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    items = await mds.list_departments(db, eff)
    return {"items": items, "count": len(items), "as_of": iso_utc(datetime.now(timezone.utc))}


@router.get("/cost-centers", response_model=CostCenterListResponse)
async def get_cost_centers(
    entity_code: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    items = await mds.list_cost_centers(db, eff)
    return {"items": items, "count": len(items), "as_of": iso_utc(datetime.now(timezone.utc))}


@router.get("/gl-accounts", response_model=GLAccountListResponse)
async def get_gl_accounts(
    entity_code: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    items = await mds.list_gl_accounts(db, eff)
    return {"items": items, "count": len(items), "as_of": iso_utc(datetime.now(timezone.utc))}


@router.get("/vendors", response_model=VendorListResponse)
async def get_vendors(
    entity_code: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Search by code/name/id (case-insensitive)"),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    current=Depends(get_current_user),
):
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    items = await mds.list_vendors(db, eff, limit=limit, offset=offset, q=q)
    return {"items": items, "count": len(items), "as_of": iso_utc(datetime.now(timezone.utc))}


@router.get("/customers", response_model=CustomerListResponse)
async def get_customers(
    entity_code: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Search by code/name/id (case-insensitive)"),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    current=Depends(get_current_user),
):
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    items = await mds.list_customers(db, eff, limit=limit, offset=offset, q=q)
    return {"items": items, "count": len(items), "as_of": iso_utc(datetime.now(timezone.utc))}


@router.get("/employees", response_model=EmployeeListResponse)
async def get_employees(
    entity_code: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Search by name/employee_code/email/id (case-insensitive)"),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    current=Depends(get_current_user),
):
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    items = await mds.list_employees(db, eff, limit=limit, offset=offset, q=q)
    return {"items": items, "count": len(items), "as_of": iso_utc(datetime.now(timezone.utc))}


@router.get("/bank-accounts", response_model=BankAccountListResponse)
async def get_bank_accounts(
    entity_code: Optional[str] = Query(None),
    current=Depends(get_current_user),
):
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    items = await mds.list_bank_accounts(db, eff)
    return {"items": items, "count": len(items), "as_of": iso_utc(datetime.now(timezone.utc))}


@router.get("/transactions", response_model=TransactionHeaderListResponse)
async def get_transactions(
    entity_code: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Search by journal_number/id/narration (case-insensitive)"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current=Depends(get_current_user),
):
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    items = await mds.list_transactions(db, eff, limit=limit, offset=offset, q=q)
    return {"items": items, "count": len(items), "as_of": iso_utc(datetime.now(timezone.utc))}


@router.get("/transaction-lines", response_model=TransactionLineListResponse)
async def get_transaction_lines(
    entity_code: Optional[str] = Query(None),
    transaction_id: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=5000),
    current=Depends(get_current_user),
):
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    items = await mds.list_transaction_lines(db, eff, transaction_id, limit)
    return {"items": items, "count": len(items), "as_of": iso_utc(datetime.now(timezone.utc))}


@router.get("/documents", response_model=DocumentListResponse)
async def get_documents(
    entity_code: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    current=Depends(get_current_user),
):
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    items = await mds.list_documents(db, eff, limit)
    return {"items": items, "count": len(items), "as_of": iso_utc(datetime.now(timezone.utc))}


@router.get("/risk-scores", response_model=RiskScoreListResponse)
async def get_risk_scores(
    entity_code: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
    current=Depends(get_current_user),
):
    eff = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    items = await mds.list_risk_scores(db, eff, limit)
    return {"items": items, "count": len(items), "as_of": iso_utc(datetime.now(timezone.utc))}


@router.get("/audit-trail", response_model=AuditTrailListResponse)
async def get_audit_trail(
    q: Optional[str] = Query(None, description="Substring match on actor/action/resource fields"),
    actor_email: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    resource_id: Optional[str] = Query(None),
    entity_code: Optional[str] = Query(None),
    since_ts: Optional[str] = Query(None, description="ISO prefix match, e.g. 2026-05-01"),
    until_ts: Optional[str] = Query(None, description="ISO prefix match, e.g. 2026-05-31"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current=Depends(get_current_user),
):
    # Entity scope applies to entity-filtered audit trail only (for non-admins).
    eff_entity = await enforce_entity_scope(db, current=current, requested_entity_code=entity_code)
    out = await mds.query_audit_trail(
        db,
        q=q,
        actor_email=actor_email,
        resource_type=resource_type,
        resource_id=resource_id,
        entity_code=eff_entity,
        since_ts=since_ts,
        until_ts=until_ts,
        limit=limit,
        offset=offset,
    )
    items = out["items"]
    return {"items": items, "count": len(items), "as_of": iso_utc(datetime.now(timezone.utc))}


_MASTER_TYPES: Dict[str, Dict[str, str]] = {
    # type -> {collection, id_field, entity_field}
    "companies": {"collection": "companies", "id": "id", "entity": ""},
    "entities": {"collection": "entities", "id": "id", "entity": "code"},
    "business-units": {"collection": "master_business_units", "id": "id", "entity": "entity_code"},
    "locations": {"collection": "master_locations", "id": "id", "entity": "entity_code"},
    "departments": {"collection": "master_departments", "id": "id", "entity": "entity_code"},
    "cost-centers": {"collection": "master_cost_centers", "id": "id", "entity": "entity_code"},
    "gl-accounts": {"collection": "master_gl_accounts", "id": "id", "entity": "entity_code"},
    "vendors": {"collection": "vendors", "id": "id", "entity": "entity"},
    "customers": {"collection": "customers", "id": "id", "entity": "entity"},
    "employees": {"collection": "employees", "id": "id", "entity": "entity"},
    "bank-accounts": {"collection": "bank_accounts", "id": "id", "entity": "entity"},
}


def _master_type_cfg(master_type: str) -> Dict[str, str]:
    cfg = _MASTER_TYPES.get(master_type)
    if not cfg:
        raise HTTPException(400, f"Unknown master_type: {master_type}")
    return cfg


async def _append_master_audit(
    *,
    actor_email: str,
    action: str,
    resource_type: str,
    resource_id: str,
    entity_code: Optional[str],
    before: Optional[Dict[str, Any]],
    after: Optional[Dict[str, Any]],
) -> None:
    now = iso_utc(datetime.now(timezone.utc))
    entry = {
        "id": str(uuid.uuid4()),
        "at": now,
        "actor_email": actor_email,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "entity_code": entity_code,
        "detail": {"before": before, "after": after},
    }
    await db.master_data_audit_trail.insert_one(dict(entry))
    await audit_log(actor_email, action, "master_data", f"{resource_type}:{resource_id}", {"entity_code": entity_code})


@router.post("/{master_type}")
async def master_create(
    master_type: str,
    body: Dict[str, Any] = Body(...),
    current=Depends(require_roles("Super Admin")),
):
    cfg = _master_type_cfg(master_type)
    coll = db[cfg["collection"]]
    id_field = cfg["id"]
    entity_field = cfg.get("entity") or ""

    doc = dict(body or {})
    if not doc.get(id_field):
        doc[id_field] = f"{master_type[:3]}-{uuid.uuid4().hex[:10]}"
    if entity_field and not doc.get(entity_field):
        # Allow seed/demo to write entity-less rows; mutations should be explicit.
        raise HTTPException(400, f"{entity_field} is required for {master_type}")
    doc["_meta_updated_at"] = iso_utc(datetime.now(timezone.utc))
    doc["_meta_updated_by"] = current["email"]
    await coll.insert_one(dict(doc))

    entity_code = doc.get(entity_field) if entity_field else None
    await _append_master_audit(
        actor_email=current["email"],
        action="master_create",
        resource_type=master_type,
        resource_id=str(doc[id_field]),
        entity_code=entity_code,
        before=None,
        after={k: v for k, v in doc.items() if k != "_id"},
    )
    return {"status": "created", "id": doc[id_field]}


@router.patch("/{master_type}/{item_id}")
async def master_patch(
    master_type: str,
    item_id: str,
    body: Dict[str, Any] = Body(...),
    current=Depends(require_roles("Super Admin")),
):
    cfg = _master_type_cfg(master_type)
    coll = db[cfg["collection"]]
    id_field = cfg["id"]
    entity_field = cfg.get("entity") or ""

    before = await coll.find_one({id_field: item_id}, {"_id": 0})
    if not before:
        raise HTTPException(404, "Not found")

    patch = dict(body or {})
    patch["_meta_updated_at"] = iso_utc(datetime.now(timezone.utc))
    patch["_meta_updated_by"] = current["email"]
    await coll.update_one({id_field: item_id}, {"$set": patch})
    after = await coll.find_one({id_field: item_id}, {"_id": 0})
    entity_code = (after or {}).get(entity_field) if entity_field else None
    await _append_master_audit(
        actor_email=current["email"],
        action="master_update",
        resource_type=master_type,
        resource_id=item_id,
        entity_code=entity_code,
        before=before,
        after=after,
    )
    return {"status": "updated", "id": item_id}


@router.post("/{master_type}/{item_id}/deactivate")
async def master_deactivate(
    master_type: str,
    item_id: str,
    current=Depends(require_roles("Super Admin")),
):
    cfg = _master_type_cfg(master_type)
    coll = db[cfg["collection"]]
    id_field = cfg["id"]
    entity_field = cfg.get("entity") or ""

    before = await coll.find_one({id_field: item_id}, {"_id": 0})
    if not before:
        raise HTTPException(404, "Not found")
    patch = {"active": False, "status": "inactive", "_meta_updated_at": iso_utc(datetime.now(timezone.utc)), "_meta_updated_by": current["email"]}
    await coll.update_one({id_field: item_id}, {"$set": patch})
    after = await coll.find_one({id_field: item_id}, {"_id": 0})
    entity_code = (after or {}).get(entity_field) if entity_field else None
    await _append_master_audit(
        actor_email=current["email"],
        action="master_deactivate",
        resource_type=master_type,
        resource_id=item_id,
        entity_code=entity_code,
        before=before,
        after=after,
    )
    return {"status": "deactivated", "id": item_id}
