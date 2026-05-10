"""Pydantic models used for API I/O. Mongo docs are stored as plain dicts (with 'id' fields)."""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr


# ---------------- Auth ----------------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: str
    entity: Optional[str] = None


class LoginResponse(BaseModel):
    token: str
    user: UserPublic


class PlatformUserCreate(BaseModel):
    """Super Admin only — create platform login."""

    email: EmailStr
    full_name: str
    role: str = Field(..., min_length=2)
    password: str = Field(..., min_length=6)
    entity: Optional[str] = "US-HQ"


# ---------------- Controls ----------------
class ControlOut(BaseModel):
    id: str
    code: str
    name: str
    process: str
    risk: str
    criticality: str
    frequency: str
    owner_email: str
    description: str
    framework: str
    active: bool
    last_run_at: Optional[str] = None
    last_run_pass: Optional[bool] = None
    last_run_exceptions: Optional[int] = None


# ---------------- Exceptions / Cases ----------------
class ExceptionOut(BaseModel):
    id: str
    control_id: str
    control_code: str
    control_name: str
    process: str
    entity: str
    severity: str  # critical/high/medium/low
    status: str  # open/in_progress/closed
    materiality_score: float
    anomaly_score: float
    financial_exposure: float
    source_record_type: str
    source_record_id: str
    detected_at: str
    title: str
    summary: str
    recurrence_count: int = 0
    engagement_id: Optional[str] = None
    material_impact: Optional[bool] = None
    department_id: Optional[str] = None
    cost_center_id: Optional[str] = None


class CaseOut(BaseModel):
    id: str
    exception_id: str
    control_code: str
    control_name: str
    title: str
    summary: str
    severity: str
    status: str
    priority: str
    owner_email: str
    owner_name: Optional[str] = None
    due_date: str
    financial_exposure: float
    entity: str
    process: str
    detected_at: str
    opened_at: str
    closed_at: Optional[str] = None
    root_cause_category: Optional[str] = None
    engagement_id: Optional[str] = None
    material_impact: Optional[bool] = None
    material_watch: Optional[bool] = None
    department_id: Optional[str] = None
    cost_center_id: Optional[str] = None


class CaseUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    owner_email: Optional[str] = None
    root_cause_category: Optional[str] = None
    due_date: Optional[str] = None


class CommentCreate(BaseModel):
    comment: str


class CommentOut(BaseModel):
    id: str
    case_id: str
    user_email: str
    user_name: str
    comment: str
    created_at: str


# ---------------- Evidence ----------------
class EvidenceNode(BaseModel):
    id: str
    type: str  # control/test/exception/transaction/document/policy/user/case
    label: str
    subtitle: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


class EvidenceEdge(BaseModel):
    source: str
    target: str
    relation: str


class EvidenceGraph(BaseModel):
    nodes: List[EvidenceNode]
    edges: List[EvidenceEdge]
    governance: Optional[Dict[str, Any]] = None


# ---------------- Copilot ----------------
class CopilotAskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=8000)
    session_id: Optional[str] = None
    mode: Optional[str] = None
    # Phase 37/40 — scope Copilot retrieval to the same masters as dashboards.
    entity_code: Optional[str] = None
    period_ym: Optional[str] = None
    department_id: Optional[str] = None
    cost_center_id: Optional[str] = None


class CopilotCitation(BaseModel):
    source_type: str
    source_id: str
    label: str
    snippet: Optional[str] = None
    app_path: Optional[str] = None


class CopilotAnswer(BaseModel):
    session_id: str
    question: str
    answer: str
    confidence: float
    model: str
    citations: List[CopilotCitation]
    needs_human_review: bool
    created_at: str
    mode: Optional[str] = None


# ---------------- Readiness / KPIs ----------------
class KPI(BaseModel):
    label: str
    value: float
    unit: str  # pct, usd, count, days
    trend_pct: Optional[float] = None
    severity: Optional[str] = None


class HeatmapCell(BaseModel):
    process: str
    entity: str
    readiness: float
    open_high: int
    exposure: float


# ---------------- CSV Ingestion ----------------
class IngestResult(BaseModel):
    dataset: str
    rows_ingested: int
    rows_failed: int
    lineage_id: str
    ingested_at: str
