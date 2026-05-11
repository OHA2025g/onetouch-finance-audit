import React, { useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Toaster } from "sonner";
import "@/index.css";
import { AuthProvider, useAuth } from "./lib/auth";
import { ThemeProvider, useTheme } from "./lib/theme";
import Layout from "./components/Layout";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import CFOCockpit from "./pages/CFOCockpit";
import ProcessReadinessPage from "./pages/ProcessReadinessPage";
import ControllerDashboard from "./pages/ControllerDashboard";
import AuditWorkspace from "./pages/AuditWorkspace";
import ComplianceDashboard from "./pages/ComplianceDashboard";
import MyCases from "./pages/MyCases";
import CasesList from "./pages/CasesList";
import CaseDetail from "./pages/CaseDetail";
import EvidenceExplorer from "./pages/EvidenceExplorer";
import Copilot from "./pages/Copilot";
import Copilot2WorkbenchPage from "./pages/Copilot2WorkbenchPage";
import IntegrationHubWorkbenchPage from "./pages/IntegrationHubWorkbenchPage";
import BoardReportingWorkbenchPage from "./pages/BoardReportingWorkbenchPage";
import EnterpriseHardeningWorkbenchPage from "./pages/EnterpriseHardeningWorkbenchPage";
import AdminConsole from "./pages/AdminConsole";
import AdminSecurityPage from "./pages/AdminSecurityPage";
import AdminSystemHealthPage from "./pages/AdminSystemHealthPage";
import AdminAuditLogsPage from "./pages/AdminAuditLogsPage";
import AdminOrgBackfillPage from "./pages/AdminOrgBackfillPage";
import AdminMasterAuditTrailPage from "./pages/AdminMasterAuditTrailPage";
import AdminMasterDataQualityPage from "./pages/AdminMasterDataQualityPage";
import AuditLogEvent from "./pages/AuditLogEvent";
import Upload from "./pages/Upload";
import AuditorPortal from "./pages/AuditorPortal";
import DrillView from "./pages/DrillView";
import EntityRollup from "./pages/EntityRollup";
import GovernanceConsole from "./pages/GovernanceConsole";
import ConnectorsConsole from "./pages/ConnectorsConsole";
import ApprovalsQueue from "./pages/ApprovalsQueue";
import AuditEngagementList from "./pages/AuditEngagementList";
import AuditEngagementNew from "./pages/AuditEngagementNew";
import AuditEngagementDetail from "./pages/AuditEngagementDetail";
import RacmBuilderPage from "./pages/RacmBuilderPage";
import FinancialStatementAuditPage from "./pages/FinancialStatementAuditPage";
import ScheduleAuditPage from "./pages/ScheduleAuditPage";
import IfcEngagementPage from "./pages/IfcEngagementPage";
import ControlLibraryPage from "./pages/ControlLibraryPage";
import AuditCalendarPage from "./pages/AuditCalendarPage";
import AuditTeamPage from "./pages/AuditTeamPage";
import CaCommandCenter from "./pages/CaCommandCenter";
import CfoAuditCommitteeDashboard from "./pages/CfoAuditCommitteeDashboard";
import WorkingPapersLayout from "./pages/WorkingPapersLayout";
import WorkingPapersHubPage from "./pages/WorkingPapersHubPage";
import WorkingPaperDetailPage from "./pages/WorkingPaperDetailPage";
import SamplingEnginePage from "./pages/SamplingEnginePage";
import VouchingWorkbenchPage from "./pages/VouchingWorkbenchPage";
import IndiaComplianceLayout from "./pages/india-compliance/IndiaComplianceLayout";
import IndiaComplianceDashboard from "./pages/india-compliance/IndiaComplianceDashboard";
import IndiaCompaniesActPage from "./pages/india-compliance/IndiaCompaniesActPage";
import IndiaGstAuditPage from "./pages/india-compliance/IndiaGstAuditPage";
import IndiaTdsAuditPage from "./pages/india-compliance/IndiaTdsAuditPage";
import IndiaTax44Page from "./pages/india-compliance/IndiaTax44Page";
import IndiaCaroPage from "./pages/india-compliance/IndiaCaroPage";
import IndiaComplianceCalendarPage from "./pages/india-compliance/IndiaComplianceCalendarPage";
import ReportStudioLayout from "./pages/report-studio/ReportStudioLayout";
import ReportStudioDashboard from "./pages/report-studio/ReportStudioDashboard";
import ObservationBuilderPage from "./pages/report-studio/ObservationBuilderPage";
import OpinionPage from "./pages/report-studio/OpinionPage";
import CaroAnnexurePage from "./pages/report-studio/CaroAnnexurePage";
import FinalReportPreviewPage from "./pages/report-studio/FinalReportPreviewPage";
import ExecutiveReviewPage from "./pages/ExecutiveReviewPage";
import FsHubPage from "./pages/auditor/FsHubPage";
import FsAuditShortcutPage from "./pages/auditor/FsAuditShortcutPage";
import ScheduleShortcutPage from "./pages/auditor/ScheduleShortcutPage";
import IfcShortcutPage from "./pages/auditor/IfcShortcutPage";
import IndiaComplianceShortcutPage from "./pages/auditor/IndiaComplianceShortcutPage";
import WorkingPapersShortcutPage from "./pages/auditor/WorkingPapersShortcutPage";
import ReportingStudioShortcutPage from "./pages/auditor/ReportingStudioShortcutPage";
import ReportingTabShortcutPage from "./pages/auditor/ReportingTabShortcutPage";
import SuperAdminPage from "./pages/SuperAdminPage";
import ReconciliationDetailPage from "./pages/ReconciliationDetailPage";
import ModuleHubPage from "./pages/ModuleHubPage";
import RiskIntelligencePage from "./pages/RiskIntelligencePage";
import MonthEndClosePage from "./pages/MonthEndClosePage";
import WorkingCapitalPage from "./pages/WorkingCapitalPage";
import ReceivablesArAgeingPage from "./pages/ReceivablesArAgeingPage";
import PayablesApAgeingPage from "./pages/PayablesApAgeingPage";
import TreasuryPage from "./pages/TreasuryPage";
import CashForecast13WeekPage from "./pages/CashForecast13WeekPage";
import FpaPage from "./pages/FpaPage";
import BudgetMasterPage from "./pages/BudgetMasterPage";
import BudgetVsActualPage from "./pages/BudgetVsActualPage";
import ForecastAccuracyPage from "./pages/ForecastAccuracyPage";
import FinanceTeamPerformancePage from "./pages/FinanceTeamPerformancePage";
import GlAuditWorkbenchPage from "./pages/GlAuditWorkbenchPage";
import JournalRiskWorkbenchPage from "./pages/JournalRiskWorkbenchPage";
import ReconciliationsWorkbenchPage from "./pages/ReconciliationsWorkbenchPage";
import BankReconciliationWorkbenchPage from "./pages/BankReconciliationWorkbenchPage";
import VendorRiskWorkbenchPage from "./pages/VendorRiskWorkbenchPage";
import ThreeWayMatchWorkbenchPage from "./pages/ThreeWayMatchWorkbenchPage";
import O2cAuditWorkbenchPage from "./pages/O2cAuditWorkbenchPage";
import CreditNotesWorkbenchPage from "./pages/CreditNotesWorkbenchPage";
import InventoryAuditWorkbenchPage from "./pages/InventoryAuditWorkbenchPage";
import PhysicalVerificationWorkbenchPage from "./pages/PhysicalVerificationWorkbenchPage";
import FixedAssetsCapexWorkbenchPage from "./pages/FixedAssetsCapexWorkbenchPage";
import TreasuryDebtInvestmentsWorkbenchPage from "./pages/TreasuryDebtInvestmentsWorkbenchPage";
import ForexExposureWorkbenchPage from "./pages/ForexExposureWorkbenchPage";
import RelatedPartyWorkbenchPage from "./pages/RelatedPartyWorkbenchPage";
import LegalNoticesLitigationWorkbenchPage from "./pages/LegalNoticesLitigationWorkbenchPage";
import DoaWorkbenchPage from "./pages/DoaWorkbenchPage";
import PolicyComplianceWorkbenchPage from "./pages/PolicyComplianceWorkbenchPage";
import AccessSodWorkbenchPage from "./pages/AccessSodWorkbenchPage";
import MasterDataQualityWorkbenchPage from "./pages/MasterDataQualityWorkbenchPage";
import EvidenceIntelligenceWorkbenchPage from "./pages/EvidenceIntelligenceWorkbenchPage";
import ContinuousAuditRulesWorkbenchPage from "./pages/ContinuousAuditRulesWorkbenchPage";
import RiskScoringWorkbenchPage from "./pages/RiskScoringWorkbenchPage";
import CashConversionPage from "./pages/CashConversionPage";
import KpiDrilldownPage from "./pages/KpiDrilldownPage";
import CfoActionQueuePage from "./pages/CfoActionQueuePage";

const THEME_STORAGE_KEY = "theme";

/** Syncs `localStorage` + Tailwind `dark` class on `<html>` from ThemeProvider context. */
function ThemeBootstrap() {
  const { theme } = useTheme();
  useEffect(() => {
    const root = document.documentElement;
    root.removeAttribute("data-theme");
    if (theme === "dark") root.classList.add("dark");
    else root.classList.remove("dark");
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      /* ignore */
    }
  }, [theme]);
  return null;
}

function Protected({ children }) {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return null;
  if (!user) return <Navigate to="/login" state={{ from: loc }} replace />;
  return children;
}

export function roleToPath(role) {
  if (role === "Super Admin") return "/app/super-admin";
  if (role === "Controller") return "/app/controller";
  if (role === "Internal Auditor") return "/app/audit";
  if (role === "Compliance Head") return "/app/compliance";
  if (role === "Process Owner") return "/app/my-cases";
  if (role === "External Auditor") return "/app/auditor";
  return "/app/cfo";
}

function RoleHome() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={roleToPath(user.role)} replace />;
}

function LandingOrAppHome() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to={roleToPath(user.role)} replace />;
  return <Landing />;
}

function LoginOrRedirect() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to={roleToPath(user.role)} replace />;
  return <Login />;
}

export default function App() {
  return (
    <ThemeProvider>
      <ThemeBootstrap />
      <AuthProvider>
        <BrowserRouter>
          <ThemedToaster />
          <Routes>
            <Route path="/" element={<LandingOrAppHome />} />
            <Route path="/login" element={<LoginOrRedirect />} />
            <Route path="/app" element={<Protected><Layout /></Protected>}>
              <Route index element={<RoleHome />} />
              {/* Phase 1 — CFO-first module hubs (placeholders + deep links) */}
              <Route path="cfo-command-center" element={<ModuleHubPage hubKey="cfo-command-center" />} />
              <Route path="finance-operations" element={<ModuleHubPage hubKey="finance-operations" />} />
              <Route path="financial-audit" element={<ModuleHubPage hubKey="financial-audit" />} />
              <Route path="continuous-audit" element={<ModuleHubPage hubKey="continuous-audit" />} />
              <Route path="working-capital-command-center" element={<ModuleHubPage hubKey="working-capital" />} />
              <Route path="treasury-command-center" element={<ModuleHubPage hubKey="treasury" />} />
              <Route path="compliance-command-center" element={<ModuleHubPage hubKey="compliance" />} />
              <Route path="working-capital" element={<WorkingCapitalPage />} />
              <Route path="working-capital/cash-conversion" element={<CashConversionPage />} />
              {/* Roadmap aliases (Phase 9-14) — thin wrappers until dedicated pages ship */}
              <Route path="working-capital/receivables" element={<ReceivablesArAgeingPage />} />
              <Route path="working-capital/payables" element={<PayablesApAgeingPage />} />
              <Route path="treasury" element={<TreasuryPage />} />
              {/* Roadmap aliases (Phase 11/26/27) */}
              <Route path="treasury/dashboard" element={<TreasuryPage />} />
              <Route path="treasury/cash-forecast" element={<CashForecast13WeekPage />} />
              <Route path="treasury/forex-exposure" element={<ForexExposureWorkbenchPage />} />
              <Route path="treasury/forex-exposure-dashboard" element={<ForexExposureWorkbenchPage />} />
              <Route path="treasury/debt-investments-dashboard" element={<TreasuryDebtInvestmentsWorkbenchPage />} />
              <Route path="risk-intelligence-command-center" element={<ModuleHubPage hubKey="risk-intelligence" />} />
              <Route path="risk-intelligence" element={<RiskIntelligencePage />} />
              <Route path="finance-operations/month-end-close" element={<MonthEndClosePage />} />
              <Route path="finance-operations/month-end-close/:cycleId" element={<MonthEndClosePage />} />
              <Route path="finance-operations/fpa" element={<FpaPage />} />
              <Route path="finance-operations/budget-master" element={<BudgetMasterPage />} />
              <Route path="finance-operations/budget-vs-actual-dashboard" element={<BudgetVsActualPage />} />
              <Route path="finance-operations/forecast-accuracy-dashboard" element={<ForecastAccuracyPage />} />
              <Route path="finance-operations/team-performance" element={<FinanceTeamPerformancePage />} />
              {/* Roadmap aliases (Phase 12-14) */}
              <Route path="finance-operations/budget" element={<BudgetMasterPage />} />
              <Route path="finance-operations/budget-vs-actual" element={<BudgetVsActualPage />} />
              <Route path="finance-operations/forecast-accuracy" element={<ForecastAccuracyPage />} />
              <Route path="evidence-cases" element={<ModuleHubPage hubKey="evidence-cases" />} />
              <Route path="board-reporting/report-automation-dashboard" element={<BoardReportingWorkbenchPage />} />
              <Route path="board-reporting" element={<ModuleHubPage hubKey="board-reporting" />} />
              <Route path="ai-copilot" element={<ModuleHubPage hubKey="ai-copilot" />} />
              <Route path="integrations/integration-hub-dashboard" element={<IntegrationHubWorkbenchPage />} />
              <Route path="integrations" element={<ModuleHubPage hubKey="integrations" />} />
              <Route path="enterprise-hardening/enterprise-hardening-dashboard" element={<EnterpriseHardeningWorkbenchPage />} />
              <Route path="enterprise-hardening" element={<ModuleHubPage hubKey="enterprise-hardening" />} />
              <Route path="cfo" element={<CFOCockpit />} />
              <Route path="cfo-action-queue" element={<CfoActionQueuePage />} />
              <Route path="kpi/:kpiId" element={<KpiDrilldownPage />} />
              <Route path="readiness" element={<ProcessReadinessPage />} />
              <Route path="controller" element={<ControllerDashboard />} />
              <Route path="reconciliations/:reconciliationId" element={<ReconciliationDetailPage />} />
              <Route path="audit" element={<AuditWorkspace />} />
              <Route path="compliance" element={<ComplianceDashboard />} />
              <Route path="compliance/rpt-dashboard" element={<RelatedPartyWorkbenchPage />} />
              <Route path="compliance/legal-dashboard" element={<LegalNoticesLitigationWorkbenchPage />} />
              {/* Roadmap aliases (Phase 28/29) */}
              <Route path="compliance/related-party-transactions" element={<RelatedPartyWorkbenchPage />} />
              <Route path="compliance/notices-litigation" element={<LegalNoticesLitigationWorkbenchPage />} />
              <Route path="my-cases" element={<MyCases />} />
              <Route path="cases" element={<CasesList />} />
              <Route path="cases/:caseId" element={<CaseDetail />} />
              <Route path="evidence" element={<EvidenceExplorer />} />
              <Route path="evidence/:exceptionId" element={<EvidenceExplorer />} />
              {/* Roadmap aliases (Phase 34) */}
              <Route path="evidence/evidence-intelligence-dashboard" element={<EvidenceIntelligenceWorkbenchPage />} />
              <Route path="evidence/document-intelligence" element={<EvidenceIntelligenceWorkbenchPage />} />
              <Route path="copilot/copilot-2-dashboard" element={<Copilot2WorkbenchPage />} />
              <Route path="copilot" element={<Copilot />} />
              <Route path="admin" element={<AdminConsole />} />
              <Route path="admin/security" element={<AdminSecurityPage />} />
              <Route path="admin/system-health" element={<AdminSystemHealthPage />} />
              <Route path="admin/audit-logs" element={<AdminAuditLogsPage />} />
              <Route path="admin/org-backfill" element={<AdminOrgBackfillPage />} />
              <Route path="admin/master-audit" element={<AdminMasterAuditTrailPage />} />
              <Route path="admin/master-dq" element={<AdminMasterDataQualityPage />} />
              <Route path="audit-log/:logId" element={<AuditLogEvent />} />
              <Route path="rollups" element={<EntityRollup />} />
              <Route path="governance" element={<GovernanceConsole />} />
              <Route path="connectors" element={<ConnectorsConsole />} />
              <Route path="approvals" element={<ApprovalsQueue />} />
              <Route path="super-admin" element={<SuperAdminPage />} />
              <Route path="audit-planning" element={<AuditEngagementList />} />
              <Route path="audit-planning/new" element={<AuditEngagementNew />} />
              <Route path="audit-planning/calendar" element={<AuditCalendarPage />} />
              <Route path="audit-planning/engagements/:engagementId" element={<AuditEngagementDetail />} />
              <Route path="audit-planning/engagements/:engagementId/team" element={<AuditTeamPage />} />
              <Route path="audit-planning/engagements/:engagementId/racm" element={<RacmBuilderPage />} />
              <Route path="audit-planning/engagements/:engagementId/fs-audit" element={<FinancialStatementAuditPage />} />
              <Route path="audit-planning/engagements/:engagementId/schedules-audit" element={<ScheduleAuditPage />} />
              <Route path="audit-planning/engagements/:engagementId/ifc-engine" element={<IfcEngagementPage />} />
              <Route path="audit-planning/engagements/:engagementId/working-papers" element={<WorkingPapersLayout />}>
                <Route index element={<WorkingPapersHubPage />} />
                <Route path="sampling" element={<SamplingEnginePage />} />
                <Route path="vouching" element={<VouchingWorkbenchPage />} />
                <Route path=":paperId" element={<WorkingPaperDetailPage />} />
              </Route>
              <Route path="audit-planning/engagements/:engagementId/india-compliance" element={<IndiaComplianceLayout />}>
                <Route index element={<IndiaComplianceDashboard />} />
                <Route path="companies-act" element={<IndiaCompaniesActPage />} />
                <Route path="gst" element={<IndiaGstAuditPage />} />
                <Route path="tds" element={<IndiaTdsAuditPage />} />
                <Route path="tax-44ab" element={<IndiaTax44Page />} />
                <Route path="caro" element={<IndiaCaroPage />} />
                <Route path="calendar" element={<IndiaComplianceCalendarPage />} />
              </Route>
              <Route path="audit-planning/engagements/:engagementId/report-studio" element={<ReportStudioLayout />}>
                <Route index element={<ReportStudioDashboard />} />
                <Route path="observations" element={<ObservationBuilderPage />} />
                <Route path="opinion" element={<OpinionPage />} />
                <Route path="caro" element={<CaroAnnexurePage />} />
                <Route path="preview" element={<FinalReportPreviewPage />} />
              </Route>
              <Route path="audit-planning/control-library" element={<ControlLibraryPage />} />
              <Route path="ca-command-center" element={<CaCommandCenter />} />
              <Route path="executive-review" element={<ExecutiveReviewPage />} />
              <Route path="audit-committee" element={<CfoAuditCommitteeDashboard />} />
              <Route path="fs-hub" element={<FsHubPage />} />
              <Route path="fs-audit" element={<FsAuditShortcutPage />} />
              <Route path="schedule" element={<ScheduleShortcutPage />} />
              <Route path="ifc" element={<IfcShortcutPage />} />
              <Route path="india-compliance" element={<IndiaComplianceShortcutPage />} />
              <Route path="working-papers" element={<WorkingPapersShortcutPage />} />
              <Route path="reporting-studio" element={<ReportingStudioShortcutPage />} />
              <Route path="reporting-tab" element={<ReportingTabShortcutPage />} />
              <Route path="upload" element={<Upload />} />
              <Route path="auditor" element={<AuditorPortal />} />
              <Route path="drill/:type/:id" element={<DrillView />} />

              {/* Roadmap aliases (Phase 15-25, 30-35) — route existence without changing backend */}
              <Route path="financial-audit/gl-audit-dashboard" element={<GlAuditWorkbenchPage />} />
              <Route path="financial-audit/gl-audit" element={<ModuleHubPage hubKey="financial-audit" />} />
              <Route path="financial-audit/journal-risk-dashboard" element={<JournalRiskWorkbenchPage />} />
              <Route path="financial-audit/journal-risk" element={<ModuleHubPage hubKey="financial-audit" />} />
              <Route path="financial-audit/reconciliations-dashboard" element={<ReconciliationsWorkbenchPage />} />
              <Route path="financial-audit/reconciliations" element={<ModuleHubPage hubKey="financial-audit" />} />
              <Route path="financial-audit/bank-reconciliation-dashboard" element={<BankReconciliationWorkbenchPage />} />
              <Route path="financial-audit/bank-reconciliation" element={<ModuleHubPage hubKey="financial-audit" />} />
              <Route path="financial-audit/inventory-audit-dashboard" element={<InventoryAuditWorkbenchPage />} />
              <Route path="financial-audit/inventory-audit" element={<ModuleHubPage hubKey="financial-audit" />} />
              <Route path="financial-audit/physical-verification-dashboard" element={<PhysicalVerificationWorkbenchPage />} />
              <Route path="financial-audit/physical-verification" element={<ModuleHubPage hubKey="financial-audit" />} />
              <Route path="financial-audit/fixed-assets-capex-dashboard" element={<FixedAssetsCapexWorkbenchPage />} />
              <Route path="financial-audit/fixed-assets-capex" element={<ModuleHubPage hubKey="financial-audit" />} />

              <Route path="continuous-audit/vendor-risk-dashboard" element={<VendorRiskWorkbenchPage />} />
              <Route path="continuous-audit/vendor-risk" element={<ModuleHubPage hubKey="continuous-audit" />} />
              <Route path="continuous-audit/three-way-match-dashboard" element={<ThreeWayMatchWorkbenchPage />} />
              <Route path="continuous-audit/three-way-match" element={<ModuleHubPage hubKey="continuous-audit" />} />
              <Route path="continuous-audit/o2c-audit-dashboard" element={<O2cAuditWorkbenchPage />} />
              <Route path="continuous-audit/credit-notes-dashboard" element={<CreditNotesWorkbenchPage />} />
              <Route path="continuous-audit/revenue-audit" element={<O2cAuditWorkbenchPage />} />
              <Route path="continuous-audit/credit-note-analytics" element={<CreditNotesWorkbenchPage />} />
              <Route path="continuous-audit/rules-engine-dashboard" element={<ContinuousAuditRulesWorkbenchPage />} />
              <Route path="continuous-audit/rules-engine" element={<ModuleHubPage hubKey="continuous-audit" />} />

              <Route path="risk-intelligence/doa-dashboard" element={<DoaWorkbenchPage />} />
              <Route path="risk-intelligence/policy-compliance-dashboard" element={<PolicyComplianceWorkbenchPage />} />
              <Route path="risk-intelligence/user-access-sod-dashboard" element={<AccessSodWorkbenchPage />} />
              <Route path="risk-intelligence/master-data-quality-dashboard" element={<MasterDataQualityWorkbenchPage />} />
              <Route path="risk-intelligence/risk-scoring-dashboard" element={<RiskScoringWorkbenchPage />} />
              <Route path="risk-intelligence/delegation-of-authority" element={<DoaWorkbenchPage />} />
              <Route path="risk-intelligence/policy-compliance" element={<PolicyComplianceWorkbenchPage />} />
              <Route path="risk-intelligence/user-access-sod" element={<AccessSodWorkbenchPage />} />
              <Route path="risk-intelligence/master-data-quality" element={<MasterDataQualityWorkbenchPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}

function ThemedToaster() {
  const { theme } = useTheme();
  return (
    <Toaster
      theme={theme}
      position="top-right"
      toastOptions={{
        style: {
          background: theme === "light" ? "hsl(0 0% 100%)" : "hsl(240 4% 10%)",
          border: `1px solid ${theme === "light" ? "hsl(240 6% 90%)" : "hsl(240 4% 16%)"}`,
          borderRadius: "0.125rem",
          color: theme === "light" ? "hsl(240 6% 6%)" : "hsl(0 0% 98%)",
          fontFamily: "'IBM Plex Sans', system-ui, sans-serif",
        },
      }}
    />
  );
}
