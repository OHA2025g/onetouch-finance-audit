"""Pydantic schemas for CA-grade audit modules (engagements, materiality, RACM, FS, etc.)."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

AuditType = Literal["statutory", "internal", "GST", "tax", "IFC", "special audit"]
# Canonical status uses hyphen for "in progress" (API + UI). Legacy `in_progress` accepted on write.
EngagementStatus = Literal["draft", "planned", "in-progress", "completed", "archived"]
RiskLevel = Literal["low", "medium", "high", "critical"]
RiskCategory = Literal[
    "Financial Reporting Risk",
    "Fraud Risk",
    "Compliance Risk",
    "Operational Risk",
    "IT/ERP Risk",
    "Tax Risk",
]
MaterialityApprovalStatus = Literal["draft", "prepared", "reviewed", "approved"]
ControlType = Literal["preventive", "detective", "automated", "manual", "IT-dependent"]
TestType = Literal["design effectiveness", "operating effectiveness"]
ControlEffectivenessScore = Literal["effective", "partially_effective", "ineffective"]
DeficiencyStatus = Literal["open", "remediated", "closed"]
SamplingMethod = Literal[
    "random",
    "monetary unit sampling",
    "judgmental",
    "high-value selection",
    "exception-based selection",
]
TickMark = Literal[
    "agreed to invoice",
    "agreed to bank",
    "recalculated",
    "verified",
    "exception noted",
    "pending clarification",
]


class AuditScopeIn(BaseModel):
    id: Optional[str] = None
    description: str
    process_area: Optional[str] = None
    financial_statement_area: Optional[str] = None


class AuditObjectiveIn(BaseModel):
    id: Optional[str] = None
    title: str
    description: Optional[str] = None


class AuditTimelineIn(BaseModel):
    planning_start: Optional[str] = None
    fieldwork_start: Optional[str] = None
    fieldwork_end: Optional[str] = None
    reporting_date: Optional[str] = None


class AuditMilestoneIn(BaseModel):
    title: str
    due_date: str
    status: Literal["pending", "done", "late"] = "pending"
    owner_email: Optional[str] = None


class AuditTeamMemberIn(BaseModel):
    user_email: str
    role: str  # partner, manager, senior, staff
    allocation_pct: Optional[float] = None


class AuditPlanningNoteIn(BaseModel):
    note: str
    visibility: Literal["team", "partner_only"] = "team"


class AuditMilestone(BaseModel):
    """Stored milestone on an engagement."""

    id: str
    title: str
    due_date: str
    status: Literal["pending", "done", "late"] = "pending"
    owner_email: Optional[str] = None
    created_at: Optional[str] = None


class AuditTeamMember(BaseModel):
    """Stored team roster row."""

    id: str
    user_email: str
    role: str
    allocation_pct: float = 100.0
    added_at: Optional[str] = None


class AuditPlanningNote(BaseModel):
    id: str
    note: str
    visibility: Literal["team", "partner_only"] = "team"
    author_email: Optional[str] = None
    created_at: Optional[str] = None


class AuditScope(BaseModel):
    id: str
    description: str
    process_area: Optional[str] = None
    financial_statement_area: Optional[str] = None


class AuditObjective(BaseModel):
    id: str
    title: str
    description: Optional[str] = None


class AuditTimeline(BaseModel):
    planning_start: Optional[str] = None
    fieldwork_start: Optional[str] = None
    fieldwork_end: Optional[str] = None
    reporting_date: Optional[str] = None


class AuditEngagement(BaseModel):
    """Full engagement document returned by the planning module (Mongo-shaped, nested rows are dicts)."""

    id: str
    engagement_id: str
    entity_name: str
    financial_year: str
    audit_type: AuditType
    audit_scope: str
    audit_objectives: List[str] = Field(default_factory=list)
    start_date: str
    end_date: str
    audit_partner: str
    audit_manager: str
    assigned_team: List[str] = Field(default_factory=list)
    status: Union[EngagementStatus, str]
    risk_level: Union[RiskLevel, str]
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    milestones: List[Dict[str, Any]] = Field(default_factory=list)
    team_members: List[Dict[str, Any]] = Field(default_factory=list)
    planning_notes: List[Dict[str, Any]] = Field(default_factory=list)
    detailed_scopes: List[Dict[str, Any]] = Field(default_factory=list)
    detailed_objectives: List[Dict[str, Any]] = Field(default_factory=list)
    timeline: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


class PlanningMetricsMilestone(BaseModel):
    engagement_id: str
    entity_name: str
    milestone_id: str
    title: str
    due_date: str
    status: str


class PlanningMetricsEngagementBrief(BaseModel):
    engagement_id: str
    entity_name: str
    end_date: str
    status: str
    risk_level: str


class AuditEngagementPlanningMetrics(BaseModel):
    """Dashboard aggregates for Audit Planning home."""

    active_audit_count: int
    upcoming_milestone_count: int
    overdue_engagement_count: int
    high_risk_engagement_count: int
    upcoming_milestones: List[PlanningMetricsMilestone] = Field(default_factory=list)
    overdue_engagements: List[PlanningMetricsEngagementBrief] = Field(default_factory=list)
    high_risk_engagements: List[PlanningMetricsEngagementBrief] = Field(default_factory=list)


class AuditEngagementCreate(BaseModel):
    engagement_id: str = Field(..., description="Unique business key e.g. ENG-2025-IN-001")
    entity_name: str
    entity_code: Optional[str] = Field(
        default=None,
        description="Legal entity code (e.g. US-HQ); used for RBAC when entity scope is enforced.",
    )
    financial_year: str
    audit_type: AuditType
    audit_scope: str
    audit_objectives: List[str] = Field(default_factory=list)
    start_date: str
    end_date: str
    audit_partner: str
    audit_manager: str
    assigned_team: List[str] = Field(default_factory=list, description="Emails of assigned staff")
    status: EngagementStatus = "draft"
    risk_level: RiskLevel = "medium"
    scopes: List[AuditScopeIn] = Field(default_factory=list)
    objectives: List[AuditObjectiveIn] = Field(default_factory=list)
    timeline: Optional[AuditTimelineIn] = None

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status_in(cls, v: Any) -> Any:
        if v == "in_progress":
            return "in-progress"
        return v


class AuditEngagementUpdate(BaseModel):
    entity_name: Optional[str] = None
    entity_code: Optional[str] = None
    financial_year: Optional[str] = None
    audit_type: Optional[AuditType] = None
    audit_scope: Optional[str] = None
    audit_objectives: Optional[List[str]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    audit_partner: Optional[str] = None
    audit_manager: Optional[str] = None
    assigned_team: Optional[List[str]] = None
    status: Optional[EngagementStatus] = None
    risk_level: Optional[RiskLevel] = None
    scopes: Optional[List[AuditScopeIn]] = None
    objectives: Optional[List[AuditObjectiveIn]] = None
    timeline: Optional[AuditTimelineIn] = None

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status_upd(cls, v: Any) -> Any:
        if v == "in_progress":
            return "in-progress"
        return v


class MaterialityBaseIn(BaseModel):
    revenue: Optional[float] = None
    profit_before_tax: Optional[float] = None
    total_assets: Optional[float] = None
    gross_expenses: Optional[float] = None
    benchmark_selected: Optional[str] = None
    override_amount: Optional[float] = None
    override_reason: Optional[str] = None

    @model_validator(mode="after")
    def override_requires_justification(self) -> "MaterialityBaseIn":
        if self.override_amount is not None and abs(float(self.override_amount)) > 1e-12:
            if not (self.override_reason and str(self.override_reason).strip()):
                raise ValueError("override_reason is required when override_amount is set (manual materiality must be justified)")
        return self


class MaterialityBenchmark(BaseModel):
    """Single benchmark candidate (5% PBT, 1% revenue, etc.)."""

    key: str
    label: str
    rule_pct: float
    amount: float
    selected: bool = False


class PerformanceMateriality(BaseModel):
    """Planning band used for substantive scope (50–75% of overall)."""

    low: float
    high: float
    mid: float
    basis_note: str = "Performance materiality is set at 50–75% of overall materiality for designing substantive procedures."
    of_overall_pct_range: str = "50%–75%"
    overall_materiality: float = 0.0


class ClearlyTrivialThreshold(BaseModel):
    """Upper bound for clearly trivial misstatements (here 5% of overall)."""

    amount: float
    pct_of_final: float = 0.05
    basis_note: str = "Clearly trivial is often set around 5% of overall materiality."


class MaterialityExceptionFlag(BaseModel):
    exception_id: Optional[str] = None
    summary: Optional[str] = None
    financial_exposure: float = 0.0
    exceeds_overall_materiality: bool = False
    exceeds_trivial_threshold: bool = False
    severity_hint: str = "below_trivial"


class MaterialityAssessment(BaseModel):
    """Consolidated materiality engine view for an engagement."""

    engagement_id: str
    materiality_record_id: str
    benchmark_selected: str
    calculated_materiality: float
    final_materiality: float
    override_applied: bool = False
    override_amount: Optional[float] = None
    override_reason: Optional[str] = None
    approval_status: str = "draft"
    prepared_by: Optional[str] = None
    reviewed_by: Optional[str] = None
    approved_by: Optional[str] = None
    benchmarks: List[MaterialityBenchmark] = Field(default_factory=list)
    performance_materiality: PerformanceMateriality
    clearly_trivial_threshold: ClearlyTrivialThreshold
    impact_explanation: str = ""


class MaterialityApproveIn(BaseModel):
    """Workflow: Prepared → Reviewed → Approved."""

    approval_status: MaterialityApprovalStatus
    approved_by: Optional[str] = None
    reviewed_by: Optional[str] = None
    prepared_by: Optional[str] = None

    @model_validator(mode="after")
    def signoff_rules(self) -> "MaterialityApproveIn":
        if self.approval_status == "approved":
            if not (self.approved_by and str(self.approved_by).strip()):
                raise ValueError("approved_by is required when approval_status is approved")
        if self.approval_status == "reviewed":
            if not (self.reviewed_by and str(self.reviewed_by).strip()):
                raise ValueError("reviewed_by is required when approval_status is reviewed")
        if self.approval_status == "prepared" and self.prepared_by is not None and not str(self.prepared_by).strip():
            raise ValueError("prepared_by must be non-empty when provided")
        return self


class RiskScore(BaseModel):
    """RACM scoring block (inherent = likelihood × impact; residual uses control effectiveness when set)."""

    likelihood_score: int = 0
    impact_score: int = 0
    inherent_risk_score: int = 0
    control_effectiveness_score: Optional[int] = None
    residual_risk_score: int = 0
    risk_rating: str = "low"
    formulas: Dict[str, str] = Field(
        default_factory=lambda: {
            "inherent": "likelihood × impact",
            "residual": "inherent adjusted by (control_effectiveness ÷ 5) when control score is set; else equals inherent",
        }
    )


class AuditProcedure(BaseModel):
    id: str
    title: str
    description: str = ""
    source: Literal["manual", "high_risk_auto"] = "manual"


class RiskControlMapping(BaseModel):
    id: str
    risk_id: str
    control_id: str
    control_code: Optional[str] = None
    control_name: Optional[str] = None
    created_at: Optional[str] = None


class AuditRisk(BaseModel):
    """RACM risk row (Mongo-aligned; nested racm_procedures preferred over flat audit_procedures strings)."""

    model_config = ConfigDict(extra="allow")
    id: str
    engagement_id: str
    risk_title: str
    risk_description: str
    process_area: str
    financial_statement_area: str
    risk_category: RiskCategory
    likelihood_score: int
    impact_score: int
    control_effectiveness_score: Optional[int] = None
    linked_controls: List[str] = Field(default_factory=list)
    audit_procedures: List[str] = Field(default_factory=list)
    racm_procedures: List[AuditProcedure] = Field(default_factory=list)
    owner: str
    status: str = "open"
    inherent_risk_score: int = 0
    residual_risk_score: int = 0
    risk_rating: str = "low"


class RiskProcedureIn(BaseModel):
    id: Optional[str] = None
    title: str
    description: Optional[str] = None
    source: Literal["manual", "high_risk_auto"] = "manual"


class RiskControlLink(BaseModel):
    control_id: str


class AuditRiskCreate(BaseModel):
    risk_title: str
    risk_description: str
    process_area: str
    financial_statement_area: str
    risk_category: RiskCategory
    likelihood_score: int = Field(ge=1, le=5)
    impact_score: int = Field(ge=1, le=5)
    control_effectiveness_score: Optional[int] = Field(default=None, ge=1, le=5)
    linked_controls: List[str] = Field(default_factory=list)
    audit_procedures: List[str] = Field(default_factory=list, description="Legacy: procedure titles only")
    procedures: List[RiskProcedureIn] = Field(default_factory=list, description="Structured audit procedures")
    owner: str
    status: Literal["open", "mitigated", "accepted", "closed"] = "open"


class AuditRiskUpdate(BaseModel):
    risk_title: Optional[str] = None
    risk_description: Optional[str] = None
    process_area: Optional[str] = None
    financial_statement_area: Optional[str] = None
    risk_category: Optional[RiskCategory] = None
    likelihood_score: Optional[int] = Field(default=None, ge=1, le=5)
    impact_score: Optional[int] = Field(default=None, ge=1, le=5)
    control_effectiveness_score: Optional[int] = Field(default=None, ge=1, le=5)
    linked_controls: Optional[List[str]] = None
    audit_procedures: Optional[List[str]] = None
    owner: Optional[str] = None
    status: Optional[str] = None


class TrialBalanceUploadMeta(BaseModel):
    currency: str = "INR"
    period_label: Optional[str] = None


class TrialBalanceLine(BaseModel):
    """Single GL row on a trial balance upload."""

    id: str
    trial_balance_id: str
    engagement_id: str
    account_code: str
    account_name: str
    debit: float = 0.0
    credit: float = 0.0
    opening_debit: Optional[float] = None
    opening_credit: Optional[float] = None
    closing_debit: Optional[float] = None
    closing_credit: Optional[float] = None
    classification_override: Optional[str] = Field(
        default=None, description="Optional: assets|liabilities|equity|revenue|expenses"
    )


class TrialBalance(BaseModel):
    """Trial balance header stored per upload."""

    id: str
    engagement_id: str
    filename: Optional[str] = None
    rows: int = 0
    total_debit: float = 0.0
    total_credit: float = 0.0
    balanced: bool = False
    uploaded_by: Optional[str] = None
    uploaded_at: Optional[str] = None
    validation_warnings: List[str] = Field(default_factory=list)
    currency: str = "INR"
    period_label: Optional[str] = None


class FinancialStatementMapping(BaseModel):
    """Maps a trial balance account to FS bucket and primary statement."""

    id: str
    trial_balance_line_id: Optional[str] = None
    account_code: str
    account_name: str
    net_amount: float
    mapped_bucket: str
    statement: str
    mapping_rule: str


class BalanceSheetLine(BaseModel):
    """Aggregated balance sheet line with optional child GL for drilldown."""

    id: str
    line: str
    bucket: str
    amount: float
    prior_amount: float = 0.0
    variance: float = 0.0
    materiality_flag: str = "none"
    child_accounts: List[Dict[str, Any]] = Field(default_factory=list)


class ProfitLossLine(BaseModel):
    id: str
    line: str
    bucket: str
    amount: float
    prior_amount: float = 0.0
    variance: float = 0.0
    materiality_flag: str = "none"
    child_accounts: List[Dict[str, Any]] = Field(default_factory=list)


class CashFlowLine(BaseModel):
    id: str
    line: str
    amount: float
    section: str


class FinancialSchedule(BaseModel):
    id: str
    title: str
    schedule_type: str
    account_codes: List[str] = Field(default_factory=list)


class FinancialGenerateIn(BaseModel):
    mapping_profile: str = "default_ind_as"


AuditAdjustmentStatus = Literal["proposed", "accepted", "rejected", "posted"]


class AuditAdjustmentCreate(BaseModel):
    account_code: str
    account_name: str
    debit: float = 0.0
    credit: float = 0.0
    narrative: str
    status: AuditAdjustmentStatus = "proposed"


class AuditAdjustmentCreateRoot(BaseModel):
    """Top-level POST /audit-adjustments — includes engagement scope."""

    engagement_id: str
    account_code: str
    account_name: str
    debit: float = 0.0
    credit: float = 0.0
    narrative: str
    status: AuditAdjustmentStatus = "proposed"


class AuditAdjustmentUpdate(BaseModel):
    debit: Optional[float] = None
    credit: Optional[float] = None
    narrative: Optional[str] = None
    status: Optional[str] = None


class AuditAdjustment(BaseModel):
    """Stored audit adjustment (journal proposal / posting workflow)."""

    id: str
    engagement_id: str
    account_code: str
    account_name: str
    debit: float = 0.0
    credit: float = 0.0
    narrative: str
    status: str = "proposed"
    created_at: Optional[str] = None


class ScheduleConclusionIn(BaseModel):
    """Conclusion narrative and reviewer sign-off for a schedule workbook."""

    conclusion: str
    preparer_email: Optional[str] = None
    reviewer_email: Optional[str] = None
    signed_off: bool = False
    reviewer_signed_at: Optional[str] = None


class ScheduleExceptionIn(BaseModel):
    title: str
    description: str
    amount: Optional[float] = None
    severity: RiskLevel = "medium"
    create_case: bool = True
    exception_flag: Optional[str] = Field(default=None, description="Machine-readable flag e.g. CUTOFF_RISK")


class ScheduleEvidenceAttachIn(BaseModel):
    label: str
    reference: str = Field(..., description="Filename, URL, WP ref, or case id")
    ref_type: Literal["file", "url", "wp", "case"] = "file"


class ScheduleProcedureStatusIn(BaseModel):
    status: Literal["pending", "in_progress", "completed", "waived"]


class ScheduleAuditDocument(BaseModel):
    """Persisted statutory schedule audit module (per engagement + schedule type)."""

    id: str
    engagement_id: str
    schedule_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    audit_procedures: List[Dict[str, Any]] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    exceptions: List[Dict[str, Any]] = Field(default_factory=list)
    conclusion: Optional[Dict[str, Any]] = None
    exception_flags: Dict[str, Any] = Field(default_factory=dict)
    updated_at: Optional[str] = None


class ControlObjective(BaseModel):
    """COSO-style objective for a control in the library."""

    id: str
    statement: str


class ControlActivity(BaseModel):
    """Key control activity (what actually happens)."""

    id: str
    description: str
    frequency: Optional[str] = None


class ControlOwner(BaseModel):
    """Process / control owner accountable for operation."""

    email: str
    name: Optional[str] = None
    role: Optional[str] = None


class ControlObjectiveIn(BaseModel):
    statement: str
    id: Optional[str] = None


class ControlActivityIn(BaseModel):
    description: str
    id: Optional[str] = None
    frequency: Optional[str] = None


class ControlOwnerIn(BaseModel):
    email: str
    name: Optional[str] = None
    role: Optional[str] = None


class ControlLibraryItemIn(BaseModel):
    code: str
    name: str
    control_type: ControlType
    process: str
    description: str
    objectives: List[ControlObjectiveIn] = Field(default_factory=list)
    activities: List[ControlActivityIn] = Field(default_factory=list)
    owners: List[ControlOwnerIn] = Field(default_factory=list)


class ControlLibrary(BaseModel):
    """Control library entry (IFC design baseline)."""

    id: str
    code: str
    name: str
    control_type: ControlType
    process: str
    description: str
    objectives: List[Dict[str, Any]] = Field(default_factory=list)
    activities: List[Dict[str, Any]] = Field(default_factory=list)
    owners: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class ControlTestCreate(BaseModel):
    control_library_id: Optional[str] = None
    control_id: Optional[str] = None
    test_type: TestType
    period: str
    tester_email: str


class ControlTest(BaseModel):
    """Planned or completed IFC test for an engagement."""

    id: str
    engagement_id: str
    test_type: TestType
    period: str
    tester_email: str
    control_library_id: Optional[str] = None
    control_id: Optional[str] = None
    process: Optional[str] = None
    result: Optional[str] = None
    effectiveness_score: Optional[str] = None
    evidence_refs: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class ControlTestResultIn(BaseModel):
    """Record design / operating effectiveness outcome."""

    effectiveness_score: Optional[ControlEffectivenessScore] = None
    result: Optional[Literal["effective", "partially_effective", "ineffective", "deficient", "not_tested", "pending"]] = None
    evidence_refs: List[str] = Field(default_factory=list)
    notes: Optional[str] = None

    @model_validator(mode="after")
    def normalize_effectiveness(self) -> "ControlTestResultIn":
        if self.effectiveness_score is None and self.result == "deficient":
            self.effectiveness_score = "ineffective"
        if self.effectiveness_score is None and self.result in ("effective", "partially_effective", "ineffective"):
            self.effectiveness_score = self.result  # type: ignore[assignment]
        if self.result is None and self.effectiveness_score is not None:
            self.result = self.effectiveness_score  # type: ignore[assignment]
        return self


class ControlDeficiencyCreate(BaseModel):
    engagement_id: str
    control_test_id: str
    severity: RiskLevel
    description: str
    create_case: bool = True
    status: DeficiencyStatus = "open"


class ControlDeficiencyUpdate(BaseModel):
    status: Optional[DeficiencyStatus] = None
    description: Optional[str] = None
    closure_notes: Optional[str] = None


class ControlDeficiency(BaseModel):
    id: str
    engagement_id: str
    control_test_id: str
    severity: RiskLevel
    description: str
    status: DeficiencyStatus = "open"
    create_case: bool = True
    management_response: Optional[Dict[str, Any]] = None
    closure_notes: Optional[str] = None
    case_id: Optional[str] = None
    created_at: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class ManagementResponse(BaseModel):
    response_text: str
    owner_email: str
    at: Optional[str] = None


class ManagementResponseIn(BaseModel):
    response_text: str
    owner_email: str


class ControlCertificationIn(BaseModel):
    engagement_id: str
    owner_email: str
    certification_text: str
    scope: str
    control_library_id: Optional[str] = None


class WorkingPaperFolderIn(BaseModel):
    name: str
    parent_id: Optional[str] = None


class WorkingPaperFolder(BaseModel):
    """Folder in the engagement WP file (Planning, FS, etc.)."""

    id: str
    name: str
    parent_id: Optional[str] = None
    engagement_id: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class WorkingPaperReferenceIn(BaseModel):
    ref_code: str = Field(..., description="Cross-ref e.g. TB-AR-03, JE-445")
    description: Optional[str] = None


class WorkingPaperReference(BaseModel):
    ref_code: str
    description: Optional[str] = None


class AuditEvidenceIn(BaseModel):
    label: str
    reference: str = Field(..., description="Filename, URL, or evidence id")
    ref_type: Literal["file", "url", "scan"] = "file"


class AuditEvidence(BaseModel):
    id: str
    working_paper_id: str
    engagement_id: str
    label: str
    reference: str
    ref_type: str = "file"
    uploaded_by: Optional[str] = None
    created_at: Optional[str] = None


class WorkingPaperCreate(BaseModel):
    engagement_id: str
    folder_id: str
    title: str
    reference: Optional[str] = None
    body: Optional[str] = None
    linked_risk_ids: List[str] = Field(default_factory=list)
    linked_control_ids: List[str] = Field(default_factory=list)
    linked_case_ids: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    references: List[WorkingPaperReferenceIn] = Field(default_factory=list, description="Cross-reference index")


class WorkingPaper(BaseModel):
    id: str
    engagement_id: str
    folder_id: str
    title: str
    reference: str
    body: Optional[str] = None
    references: List[Dict[str, Any]] = Field(default_factory=list)
    prepared_by: Optional[str] = None
    reviewed_by: Optional[str] = None
    approved_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class WorkingPaperUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    folder_id: Optional[str] = None
    linked_risk_ids: Optional[List[str]] = None
    linked_control_ids: Optional[List[str]] = None
    linked_case_ids: Optional[List[str]] = None
    evidence_ids: Optional[List[str]] = None
    references: Optional[List[WorkingPaperReferenceIn]] = None
    prepared_by: Optional[str] = None
    reviewed_by: Optional[str] = None
    approved_by: Optional[str] = None


class SamplingPlanCreate(BaseModel):
    engagement_id: str
    working_paper_id: Optional[str] = None
    method: SamplingMethod
    population_size: int
    sample_size: int
    seed: Optional[int] = None


class SamplingPlan(BaseModel):
    id: str
    engagement_id: str
    working_paper_id: Optional[str] = None
    method: SamplingMethod
    population_size: int
    sample_size: int
    seed: Optional[int] = None
    created_at: Optional[str] = None
    generated_at: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class SampleTransaction(BaseModel):
    id: str
    sampling_plan_id: str
    idx: int
    amount: float
    transaction_ref: Optional[str] = None
    document_ref: Optional[str] = None
    selection_reason: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class VouchingItemCreate(BaseModel):
    engagement_id: str
    working_paper_id: str
    transaction_ref: str
    amount: Optional[float] = None
    tick_mark: TickMark = "pending clarification"
    notes: Optional[str] = None
    evidence_reference: Optional[str] = None
    conclusion: Optional[str] = None


class VouchingItemUpdate(BaseModel):
    tick_mark: Optional[TickMark] = None
    notes: Optional[str] = None
    evidence_reference: Optional[str] = None
    conclusion: Optional[str] = None
    transaction_ref: Optional[str] = None


class VouchingItem(BaseModel):
    id: str
    engagement_id: str
    working_paper_id: str
    transaction_ref: str
    amount: Optional[float] = None
    tick_mark: str = "pending clarification"
    notes: Optional[str] = None
    evidence_reference: Optional[str] = None
    conclusion: Optional[str] = None
    created_at: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class ReviewNoteIn(BaseModel):
    note: str
    author_email: str
    note_type: Literal["review", "clearing", "query"] = "review"


class ReviewNote(BaseModel):
    id: str
    working_paper_id: str
    note: str
    author_email: str
    note_type: str = "review"
    created_at: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class SignOffIn(BaseModel):
    role: Literal["preparer", "reviewer", "partner"]
    signer_email: str


PenaltyRisk = Literal["low", "medium", "high", "critical"]


class ComplianceSection(BaseModel):
    """Statutory section or form line under a law."""

    code: str
    title: str


class ComplianceLaw(BaseModel):
    """India regulatory law bucket (Companies Act, GST, etc.)."""

    code: str
    name: str
    short_name: str
    sections: List[ComplianceSection] = Field(default_factory=list)


class ComplianceRequirement(BaseModel):
    """Single checklist line persisted under a ComplianceChecklist / results doc."""

    id: str
    law_code: str
    section: str
    title: str
    status: Literal["compliant", "non-compliant", "pending evidence", "not applicable"] = "pending evidence"
    penalty_risk: PenaltyRisk = "medium"
    evidence_uri: Optional[str] = None
    notes: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class ComplianceChecklist(BaseModel):
    """Engagement compliance checklist aggregate (stored as ca_compliance_results)."""

    id: str
    engagement_id: str
    requirements: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class ComplianceFindingIn(BaseModel):
    requirement_id: Optional[str] = None
    law_code: str
    title: str
    severity: PenaltyRisk = "medium"
    notes: Optional[str] = None


class ComplianceFinding(BaseModel):
    id: str
    engagement_id: str
    requirement_id: Optional[str] = None
    law_code: str
    title: str
    severity: str = "medium"
    notes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class FilingDueDate(BaseModel):
    id: str
    law_code: str
    form_code: str
    title: str
    due_date: str
    penalty_risk: PenaltyRisk = "medium"


class ComplianceChecklistCreate(BaseModel):
    law_codes: List[str] = Field(default_factory=list)


class ComplianceResultUpdate(BaseModel):
    requirement_id: str
    status: Literal["compliant", "non-compliant", "pending evidence", "not applicable"]
    evidence_uri: Optional[str] = None
    notes: Optional[str] = None


class GstReconciliationIn(BaseModel):
    gstr1_sales: float
    gstr3b_sales: float
    gstr2b_purchases: float
    purchase_register: float
    itc_claimed: float
    itc_eligible: float
    gstr3b_output_tax_liability: Optional[float] = Field(
        default=None, description="Output tax per GSTR-3B (for liability mismatch)"
    )
    books_output_tax_liability: Optional[float] = Field(
        default=None, description="Output tax per GL / trial balance"
    )


class GstReconciliationWithEngagement(GstReconciliationIn):
    engagement_id: str


class TdsReconciliationIn(BaseModel):
    ledger_tds: float
    challan_tds: float
    delayed_payment_days: int = 0
    expected_deduction_rate_pct: Optional[float] = Field(default=None, description="Statutory / expected TDS %")
    applied_deduction_rate_pct: Optional[float] = Field(default=None, description="Rate applied in books / ERP")


class TdsReconciliationWithEngagement(TdsReconciliationIn):
    engagement_id: str


class CaroChecklistIn(BaseModel):
    clause_ids: List[str] = Field(default_factory=list)


class CaroChecklistWithEngagement(CaroChecklistIn):
    engagement_id: str


class CaroClauseUpdate(BaseModel):
    clause_id: str
    status: Literal["compliant", "non-compliant", "pending evidence", "not applicable"]
    evidence_uri: Optional[str] = None
    notes: Optional[str] = None


class TaxAudit44abIn(BaseModel):
    clause_ids: List[str] = Field(default_factory=list)


class Tax44ClauseUpdate(BaseModel):
    clause_id: str
    status: Literal["compliant", "non-compliant", "pending evidence", "not applicable"]
    evidence_uri: Optional[str] = None
    notes: Optional[str] = None


class AuditObservationCreate(BaseModel):
    title: str
    description: str
    severity: RiskLevel
    material: bool = False
    pervasive: bool = False
    source: Literal["case", "control", "compliance", "fs", "schedule", "manual"] = "manual"
    source_id: Optional[str] = None


class AuditObservation(BaseModel):
    """Stored audit observation (KAM / misstatement / other)."""

    id: str
    engagement_id: str
    title: str
    description: str
    severity: str
    material: bool = False
    pervasive: bool = False
    source: str = "manual"
    source_id: Optional[str] = None
    resolved: bool = False
    created_at: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class AuditObservationUpdate(BaseModel):
    resolved: Optional[bool] = None
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[RiskLevel] = None
    material: Optional[bool] = None
    pervasive: Optional[bool] = None


class AuditFindingIn(BaseModel):
    title: str
    description: Optional[str] = None
    severity: RiskLevel = "medium"
    related_observation_id: Optional[str] = None


class AuditFinding(BaseModel):
    id: str
    engagement_id: str
    title: str
    description: Optional[str] = None
    severity: str = "medium"
    related_observation_id: Optional[str] = None
    created_at: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class AuditQualification(BaseModel):
    """Narrative qualification segment (e.g. scope limitation wording)."""

    area: str
    nature: str
    impact: Literal["immaterial", "material_not_pervasive", "material_pervasive"] = "material_not_pervasive"


class AuditOpinion(BaseModel):
    """Structured opinion recommendation from the engine."""

    suggested_opinion: str
    opinion_display: str
    rationale: str
    counts: Dict[str, Any] = Field(default_factory=dict)
    signals_summary: Dict[str, Any] = Field(default_factory=dict)
    generated_at: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class CAROClauseResponse(BaseModel):
    clause_id: str
    response: str
    status: Optional[str] = None


class ManagementRepresentation(BaseModel):
    id: str
    engagement_id: str
    text: str
    signed_by: str
    at: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class FinalAuditReport(BaseModel):
    id: str
    engagement_id: str
    sections: Dict[str, Any] = Field(default_factory=dict)
    approval_status: str = "draft"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class ManagementRepresentationIn(BaseModel):
    text: str
    signed_by: str


class FinalReportStatusIn(BaseModel):
    status: Literal["draft", "partner review", "management response", "final issued"]

