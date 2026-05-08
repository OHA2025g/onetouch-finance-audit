"""Unified finance master data shapes (Phase 2) — typed contracts for /api/masters/*.

L4 goal: stable, explicit response shapes per endpoint (avoid `List[Dict]`).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CompanyOut(BaseModel):
    id: str
    name: str
    country: Optional[str] = None
    base_currency: str = "USD"
    source: str = Field(default="master", description="master | derived")


class LegalEntityOut(BaseModel):
    id: str
    code: str
    name: str
    geo: Optional[str] = None
    company_id: Optional[str] = None
    source: str = "entities"


class BusinessUnitOut(BaseModel):
    id: str
    code: str
    name: str
    entity_code: str
    company_id: Optional[str] = None
    active: bool = True


class LocationOut(BaseModel):
    id: str
    code: str
    name: str
    entity_code: str
    country: Optional[str] = None
    active: bool = True


class DepartmentOut(BaseModel):
    id: str
    code: str
    name: str
    entity_code: str
    cost_center_id: Optional[str] = None
    active: bool = True


class CostCenterOut(BaseModel):
    id: str
    code: str
    name: str
    entity_code: str
    department_id: Optional[str] = None
    active: bool = True


class GLAccountOut(BaseModel):
    id: str
    account_code: str
    account_name: str
    entity_code: str
    account_type: Optional[str] = None  # asset, liability, revenue, expense
    active: bool = True


class VendorMasterOut(BaseModel):
    id: str
    vendor_code: str
    vendor_name: str
    entity_code: str
    status: str
    source: str = "vendors"


class CustomerMasterOut(BaseModel):
    id: str
    customer_code: str
    customer_name: str
    entity_code: str
    status: str
    credit_limit: Optional[float] = None
    source: str = "customers"


class EmployeeMasterOut(BaseModel):
    id: str
    employee_number: str
    full_name: str
    entity_code: str
    email: Optional[str] = None
    department_id: Optional[str] = None
    status: str = "active"
    source: str = "employees"


class BankAccountOut(BaseModel):
    id: str
    account_name: str
    entity_code: str
    currency: str = "USD"
    bank_name: Optional[str] = None
    masked_number: Optional[str] = None
    source: str = "bank_accounts"


class TransactionHeaderOut(BaseModel):
    id: str
    document_number: str
    entity_code: str
    posting_date: str
    total_amount: float
    source: str = "journals"


class TransactionLineOut(BaseModel):
    id: str
    transaction_id: str
    line_no: int
    entity_code: str
    account_code: str
    debit: float = 0.0
    credit: float = 0.0
    description: Optional[str] = None


class DocumentMasterOut(BaseModel):
    id: str
    doc_type: str
    title: str
    entity_code: Optional[str] = None
    external_uri: Optional[str] = None
    source: str = "master_documents"


class RiskScoreOut(BaseModel):
    id: str
    object_type: str
    object_id: str
    entity_code: Optional[str] = None
    score: float
    band: str
    drivers: List[str] = Field(default_factory=list)


class AuditTrailEntryOut(BaseModel):
    id: str
    at: str
    actor_email: str
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    detail: Optional[Dict[str, Any]] = None


class MasterListResponse(BaseModel):
    items: List[Dict[str, Any]]
    count: int
    as_of: str


# ---------------- Typed list responses (L4 contract) ----------------

class CompanyListResponse(BaseModel):
    items: List[CompanyOut]
    count: int
    as_of: str


class LegalEntityListResponse(BaseModel):
    items: List[LegalEntityOut]
    count: int
    as_of: str


class BusinessUnitListResponse(BaseModel):
    items: List[BusinessUnitOut]
    count: int
    as_of: str


class LocationListResponse(BaseModel):
    items: List[LocationOut]
    count: int
    as_of: str


class DepartmentListResponse(BaseModel):
    items: List[DepartmentOut]
    count: int
    as_of: str


class CostCenterListResponse(BaseModel):
    items: List[CostCenterOut]
    count: int
    as_of: str


class GLAccountListResponse(BaseModel):
    items: List[GLAccountOut]
    count: int
    as_of: str


class VendorListResponse(BaseModel):
    items: List[VendorMasterOut]
    count: int
    as_of: str


class CustomerListResponse(BaseModel):
    items: List[CustomerMasterOut]
    count: int
    as_of: str


class EmployeeListResponse(BaseModel):
    items: List[EmployeeMasterOut]
    count: int
    as_of: str


class BankAccountListResponse(BaseModel):
    items: List[BankAccountOut]
    count: int
    as_of: str


class TransactionHeaderListResponse(BaseModel):
    items: List[TransactionHeaderOut]
    count: int
    as_of: str


class TransactionLineListResponse(BaseModel):
    items: List[TransactionLineOut]
    count: int
    as_of: str


class DocumentListResponse(BaseModel):
    items: List[DocumentMasterOut]
    count: int
    as_of: str


class RiskScoreListResponse(BaseModel):
    items: List[RiskScoreOut]
    count: int
    as_of: str


class AuditTrailListResponse(BaseModel):
    items: List[AuditTrailEntryOut]
    count: int
    as_of: str
