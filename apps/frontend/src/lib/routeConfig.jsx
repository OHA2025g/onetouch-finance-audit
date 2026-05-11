/**
 * Phase 1 — CFO-first navigation & route metadata.
 * Role keys must match backend seed: CFO, Controller, Internal Auditor, External Auditor,
 * Compliance Head, Process Owner, Super Admin.
 */
import {
  Gauge,
  ChartPieSlice,
  Scales,
  ShieldCheck,
  Briefcase,
  ListChecks,
  ChatCircleDots,
  GearSix,
  TreeStructure,
  Gavel,
  Plug,
  CalendarBlank,
  Command,
  ClipboardText,
  FileText,
  Users,
  SquaresFour,
  Factory,
  Infinity as InfinityIcon,
  Wallet,
  ChartLineUp,
  WarningCircle,
  PresentationChart,
  Sparkle,
  LinkSimple,
  ListBullets,
  Kanban,
  Table,
  Desktop,
  IdentificationCard,
  Coins,
  ChartBar,
  TrendUp,
  SlidersHorizontal,
  Package,
  Scan,
  Buildings,
  FolderOpen,
  SealCheck,
  GitBranch,
  ShoppingCart,
  Receipt,
  CurrencyDollar,
  ArrowsClockwise,
  Bank,
  Clock,
  Globe,
  Handshake,
  Newspaper,
  Database,
  ShieldWarning,
  UsersFour,
  NotePencil,
  Robot,
  Student,
  Tabs,
  Binoculars,
  Folders,
  ChatText,
  Crosshair,
  Eye,
  CloudArrowUp,
  BookOpenText,
  Cpu,
  MagnifyingGlass,
  Target,
  Scroll,
  Key,
  Notebook,
  FileMagnifyingGlass,
  Calendar,
  ClockCountdown,
  CheckCircle,
  Flag,
  ArrowsDownUp,
  House,
  Vault,
  Hexagon,
  FileLock,
  ShieldPlus,
} from "@phosphor-icons/react";

/** null = all authenticated roles for that nav mode */
export const ROLES = {
  SUPER_ADMIN_ONLY: ["Super Admin"],
  CFO_LIKE: ["CFO"],
  AUDITOR_BUNDLE: [
    "External Auditor",
    "Internal Auditor",
    "Controller",
    "Compliance Head",
    "Process Owner",
  ],
};

function roleAllowed(userRole, allowed) {
  if (!allowed) return true;
  return allowed.includes(userRole);
}

function filterItems(user, items) {
  return items.filter((it) => roleAllowed(user.role, it.roles));
}

function filterGroups(user, groups) {
  return groups
    .map((g) => ({
      ...g,
      items: filterItems(user, g.items),
    }))
    .filter((g) => g.items.length > 0);
}

/** CFO default navigation (CFO role only in practice). */
const CFO_GROUPS = [
  {
    id: "cfo-command-center",
    title: "CFO Command Center",
    items: [
      { to: "/app/cfo", label: "CFO Cockpit", icon: Gauge, roles: ROLES.CFO_LIKE },
      { to: "/app/cfo-action-queue", label: "Action queue", icon: Kanban, roles: ROLES.CFO_LIKE },
      { to: "/app/readiness", label: "Process readiness matrix", icon: Table, roles: ROLES.CFO_LIKE },
      { to: "/app/controller", label: "Controller dashboard", icon: Desktop, roles: ROLES.CFO_LIKE },
      { to: "/app/rollups", label: "Entity rollups", icon: TreeStructure, roles: ROLES.CFO_LIKE },
      { to: "/app/executive-review", label: "Executive review", icon: IdentificationCard, roles: ROLES.CFO_LIKE },
    ],
  },
  {
    id: "finance-operations",
    title: "Finance Operations",
    items: [
      { to: "/app/finance-operations/month-end-close", label: "Month-end close", icon: ClockCountdown, roles: ROLES.CFO_LIKE },
      { to: "/app/finance-operations/team-performance", label: "Finance team", icon: Users, roles: ROLES.CFO_LIKE },
      { to: "/app/finance-operations/budget-master", label: "Budget master", icon: Coins, roles: ROLES.CFO_LIKE },
      { to: "/app/finance-operations/budget-vs-actual-dashboard", label: "Budget vs actual", icon: ChartBar, roles: ROLES.CFO_LIKE },
      { to: "/app/finance-operations/forecast-accuracy-dashboard", label: "Forecast accuracy", icon: TrendUp, roles: ROLES.CFO_LIKE },
      { to: "/app/finance-operations/fpa", label: "FP&A snapshot", icon: SlidersHorizontal, roles: ROLES.CFO_LIKE },
      { to: "/app/audit", label: "Audit workspace", icon: Scales, roles: ROLES.CFO_LIKE },
    ],
  },
  {
    id: "financial-audit",
    title: "Financial Audit",
    items: [
      { to: "/app/financial-audit/gl-audit-dashboard", label: "GL audit workbench", icon: BookOpenText, roles: ROLES.CFO_LIKE },
      { to: "/app/financial-audit/journal-risk-dashboard", label: "Journal risk", icon: WarningCircle, roles: ROLES.CFO_LIKE },
      { to: "/app/financial-audit/reconciliations-dashboard", label: "Reconciliations", icon: ListChecks, roles: ROLES.CFO_LIKE },
      { to: "/app/financial-audit/bank-reconciliation-dashboard", label: "Bank reconciliation", icon: Wallet, roles: ROLES.CFO_LIKE },
      { to: "/app/financial-audit/inventory-audit-dashboard", label: "Inventory audit", icon: Package, roles: ROLES.CFO_LIKE },
      { to: "/app/financial-audit/physical-verification-dashboard", label: "Physical verification", icon: Scan, roles: ROLES.CFO_LIKE },
      { to: "/app/financial-audit/fixed-assets-capex-dashboard", label: "Fixed assets · CAPEX", icon: Buildings, roles: ROLES.CFO_LIKE },
      { to: "/app/audit-planning", label: "Audit planning", icon: CalendarBlank, roles: ROLES.CFO_LIKE },
      { to: "/app/evidence", label: "Evidence explorer", icon: FolderOpen, roles: ROLES.CFO_LIKE },
    ],
  },
  {
    id: "continuous-audit",
    title: "Continuous Audit",
    items: [
      { to: "/app/executive-review?tab=assurance", label: "Continuous assurance", icon: SealCheck, roles: ROLES.CFO_LIKE },
      { to: "/app/continuous-audit/rules-engine-dashboard", label: "Rules engine", icon: Command, roles: ROLES.CFO_LIKE },
      { to: "/app/continuous-audit/vendor-risk-dashboard", label: "Vendor risk", icon: WarningCircle, roles: ROLES.CFO_LIKE },
      { to: "/app/continuous-audit/three-way-match-dashboard", label: "Three-way match", icon: GitBranch, roles: ROLES.CFO_LIKE },
      { to: "/app/continuous-audit/o2c-audit-dashboard", label: "O2C audit", icon: ShoppingCart, roles: ROLES.CFO_LIKE },
      { to: "/app/continuous-audit/credit-notes-dashboard", label: "Credit notes", icon: Receipt, roles: ROLES.CFO_LIKE },
      { to: "/app/audit", label: "Controls & tests", icon: ListBullets, roles: ROLES.CFO_LIKE },
    ],
  },
  {
    id: "working-capital",
    title: "Working Capital",
    items: [
      { to: "/app/working-capital", label: "WC dashboard", icon: Wallet, roles: ROLES.CFO_LIKE },
      { to: "/app/working-capital/receivables", label: "Receivables · AR ageing", icon: CurrencyDollar, roles: ROLES.CFO_LIKE },
      { to: "/app/working-capital/payables", label: "Payables · AP ageing", icon: ArrowsDownUp, roles: ROLES.CFO_LIKE },
      { to: "/app/working-capital/cash-conversion", label: "Cash conversion cycle", icon: ArrowsClockwise, roles: ROLES.CFO_LIKE },
    ],
  },
  {
    id: "treasury",
    title: "Treasury",
    items: [
      { to: "/app/treasury", label: "Treasury hub", icon: Bank, roles: ROLES.CFO_LIKE },
      { to: "/app/treasury/cash-forecast", label: "Cash forecast · 13-week", icon: Clock, roles: ROLES.CFO_LIKE },
      { to: "/app/treasury/debt-investments-dashboard", label: "Debt & investments", icon: ChartLineUp, roles: ROLES.CFO_LIKE },
      { to: "/app/treasury/forex-exposure-dashboard", label: "Forex exposure", icon: Globe, roles: ROLES.CFO_LIKE },
      { to: "/app/connectors", label: "Bank / ERP connectors", icon: Plug, roles: ROLES.CFO_LIKE },
    ],
  },
  {
    id: "compliance",
    title: "Compliance",
    items: [
      { to: "/app/compliance", label: "Compliance dashboard", icon: ShieldCheck, roles: ROLES.CFO_LIKE },
      { to: "/app/compliance/rpt-dashboard", label: "Related party transactions", icon: Handshake, roles: ROLES.CFO_LIKE },
      { to: "/app/compliance/legal-dashboard", label: "Legal notices & litigation", icon: Newspaper, roles: ROLES.CFO_LIKE },
    ],
  },
  {
    id: "risk-intelligence",
    title: "Risk Intelligence",
    items: [
      { to: "/app/risk-intelligence", label: "Risk intelligence", icon: WarningCircle, roles: ROLES.CFO_LIKE },
      { to: "/app/risk-intelligence/risk-scoring-dashboard", label: "Risk scoring", icon: Target, roles: ROLES.CFO_LIKE },
      { to: "/app/risk-intelligence/doa-dashboard", label: "Delegation of authority", icon: Scroll, roles: ROLES.CFO_LIKE },
      { to: "/app/risk-intelligence/policy-compliance-dashboard", label: "Policy compliance", icon: Notebook, roles: ROLES.CFO_LIKE },
      { to: "/app/risk-intelligence/user-access-sod-dashboard", label: "Access & SoD", icon: Key, roles: ROLES.CFO_LIKE },
      { to: "/app/risk-intelligence/master-data-quality-dashboard", label: "Master data quality", icon: Database, roles: ROLES.CFO_LIKE },
    ],
  },
  {
    id: "evidence-cases",
    title: "Evidence & Cases",
    items: [
      { to: "/app/my-cases", label: "My cases", icon: Briefcase, roles: ROLES.CFO_LIKE },
      { to: "/app/cases", label: "All cases", icon: ListChecks, roles: ROLES.CFO_LIKE },
      { to: "/app/evidence/evidence-intelligence-dashboard", label: "Evidence intelligence", icon: Cpu, roles: ROLES.CFO_LIKE },
      { to: "/app/evidence", label: "Evidence explorer", icon: MagnifyingGlass, roles: ROLES.CFO_LIKE },
    ],
  },
  {
    id: "board-reporting",
    title: "Board Reporting",
    items: [
      { to: "/app/executive-review", label: "CFO & Committee hub", icon: UsersFour, roles: ROLES.CFO_LIKE },
      { to: "/app/audit-committee", label: "Audit committee", icon: Gavel, roles: ROLES.CFO_LIKE },
      { to: "/app/board-reporting/report-automation-dashboard", label: "Report automation", icon: PresentationChart, roles: ROLES.CFO_LIKE },
      { to: "/app/reporting-studio", label: "Reporting studio", icon: NotePencil, roles: ROLES.CFO_LIKE },
    ],
  },
  {
    id: "ai-copilot",
    title: "AI Copilot",
    items: [
      { to: "/app/copilot", label: "Copilot workspace", icon: ChatCircleDots, roles: ROLES.CFO_LIKE },
      { to: "/app/copilot/copilot-2-dashboard", label: "Copilot 2.0", icon: Robot, roles: ROLES.CFO_LIKE },
    ],
  },
];

function dedupeNavItems(items) {
  const seen = new Set();
  const out = [];
  for (const it of items) {
    const base = it.to.split("?")[0];
    if (seen.has(base)) continue;
    seen.add(base);
    out.push(it);
  }
  return out;
}

/** Statutory / extended audit roles — preserves prior links, grouped by Phase 1 architecture. */
function auditorNavGroups(user) {
  const pin = [];
  if (user.role === "Internal Auditor" || user.role === "External Auditor") {
    pin.push({ to: "/app/audit", label: "Audit workspace", icon: Scales, roles: ROLES.AUDITOR_BUNDLE });
  } else if (user.role === "Controller") {
    pin.push({ to: "/app/controller", label: "Controller", icon: Desktop, roles: ROLES.AUDITOR_BUNDLE });
  } else if (user.role === "Compliance Head") {
    pin.push({ to: "/app/compliance", label: "Compliance", icon: ShieldCheck, roles: ROLES.AUDITOR_BUNDLE });
  } else if (user.role === "Process Owner") {
    pin.push({ to: "/app/my-cases", label: "My cases", icon: Briefcase, roles: ROLES.AUDITOR_BUNDLE });
  }

  const cfoCc = [
    { to: "/app/cfo-command-center", label: "CFO overview", icon: SquaresFour, roles: ROLES.AUDITOR_BUNDLE },
    { to: "/app/cfo", label: "CFO Cockpit", icon: Gauge, roles: ROLES.AUDITOR_BUNDLE },
    { to: "/app/cfo-action-queue", label: "Action queue", icon: Kanban, roles: ROLES.AUDITOR_BUNDLE },
    { to: "/app/readiness", label: "Process readiness matrix", icon: Table, roles: ROLES.AUDITOR_BUNDLE },
  ];

  const finAudit = [
    { to: "/app/financial-audit", label: "Financial audit hub", icon: Scales, roles: ROLES.AUDITOR_BUNDLE },
    { to: "/app/audit-planning", label: "Audit planning", icon: CalendarBlank, roles: ROLES.AUDITOR_BUNDLE },
    { to: "/app/fs-hub", label: "FS Hub", icon: Table, roles: ROLES.AUDITOR_BUNDLE },
    { to: "/app/fs-audit", label: "FS Audit", icon: ChartPieSlice, roles: ROLES.AUDITOR_BUNDLE },
    { to: "/app/schedule", label: "Schedule", icon: Calendar, roles: ROLES.AUDITOR_BUNDLE },
    { to: "/app/working-papers", label: "Working papers", icon: FileText, roles: ROLES.AUDITOR_BUNDLE },
  ];

  const complianceIfc = [
    { to: "/app/ifc", label: "IFC", icon: ShieldPlus, roles: ROLES.AUDITOR_BUNDLE },
    { to: "/app/india-compliance", label: "Indian compliance", icon: Flag, roles: ROLES.AUDITOR_BUNDLE },
    { to: "/app/compliance-command-center", label: "Compliance hub", icon: SquaresFour, roles: ROLES.AUDITOR_BUNDLE },
    { to: "/app/compliance", label: "Compliance dashboard", icon: ShieldWarning, roles: ROLES.AUDITOR_BUNDLE },
  ];

  const continuous = [
    { to: "/app/continuous-audit", label: "Continuous audit hub", icon: InfinityIcon, roles: ROLES.AUDITOR_BUNDLE },
    { to: "/app/executive-review?tab=assurance", label: "Continuous assurance", icon: SealCheck, roles: ROLES.AUDITOR_BUNDLE },
  ];

  const board = [
    { to: "/app/board-reporting", label: "Board reporting hub", icon: PresentationChart, roles: ROLES.AUDITOR_BUNDLE },
    { to: "/app/audit-committee", label: "Audit committee", icon: UsersFour, roles: ROLES.AUDITOR_BUNDLE },
    { to: "/app/reporting-studio", label: "Reporting studio", icon: NotePencil, roles: ROLES.AUDITOR_BUNDLE },
    { to: "/app/reporting-tab", label: "Reporting tab", icon: Tabs, roles: ROLES.AUDITOR_BUNDLE },
    { to: "/app/ca-command-center", label: "CA command center", icon: Student, roles: ROLES.AUDITOR_BUNDLE },
  ];

  const evidenceCases = [
    { to: "/app/evidence-cases", label: "Evidence & cases hub", icon: Binoculars, roles: ROLES.AUDITOR_BUNDLE },
    { to: "/app/cases", label: "All cases", icon: Folders, roles: ROLES.AUDITOR_BUNDLE },
    { to: "/app/evidence", label: "Evidence explorer", icon: FileMagnifyingGlass, roles: ROLES.AUDITOR_BUNDLE },
  ];

  const ai = [
    { to: "/app/ai-copilot", label: "AI hub", icon: Sparkle, roles: ROLES.AUDITOR_BUNDLE },
    { to: "/app/copilot", label: "Copilot", icon: ChatText, roles: ROLES.AUDITOR_BUNDLE },
  ];

  const wcTreasuryRisk = [
    { to: "/app/finance-operations", label: "Finance operations hub", icon: Factory, roles: ROLES.AUDITOR_BUNDLE },
    { to: "/app/working-capital-command-center", label: "WC overview", icon: House, roles: ROLES.AUDITOR_BUNDLE },
    { to: "/app/working-capital", label: "WC dashboard", icon: Wallet, roles: ROLES.AUDITOR_BUNDLE },
    { to: "/app/treasury-command-center", label: "Treasury overview", icon: Vault, roles: ROLES.AUDITOR_BUNDLE },
    { to: "/app/treasury", label: "Treasury hub", icon: Bank, roles: ROLES.AUDITOR_BUNDLE },
    { to: "/app/risk-intelligence-command-center", label: "Risk hub", icon: Hexagon, roles: ROLES.AUDITOR_BUNDLE },
    { to: "/app/risk-intelligence", label: "Risk intelligence", icon: Crosshair, roles: ROLES.AUDITOR_BUNDLE },
  ];

  const groups = [];
  if (pin.length) {
    groups.push({ id: "pinned", title: "Your workspace", items: dedupeNavItems(filterItems(user, pin)) });
  }
  groups.push(
    { id: "cfo-cc", title: "CFO Command Center", items: dedupeNavItems(filterItems(user, cfoCc)) },
    { id: "fin-audit", title: "Financial Audit", items: dedupeNavItems(filterItems(user, [...pin, ...finAudit])) },
    { id: "compliance-ifc", title: "Compliance", items: dedupeNavItems(filterItems(user, complianceIfc)) },
    { id: "continuous", title: "Continuous Audit", items: dedupeNavItems(filterItems(user, continuous)) },
    { id: "board", title: "Board Reporting", items: dedupeNavItems(filterItems(user, board)) },
    { id: "evidence", title: "Evidence & Cases", items: dedupeNavItems(filterItems(user, evidenceCases)) },
    { id: "ai", title: "AI Copilot", items: dedupeNavItems(filterItems(user, ai)) },
    { id: "wc-treasury-risk", title: "Finance Ops · WC · Treasury · Risk", items: dedupeNavItems(filterItems(user, wcTreasuryRisk)) }
  );

  return groups.filter((g) => g.items.length > 0);
}

const SUPER_ADMIN_GROUPS = [
  {
    id: "admin-integrations",
    title: "Admin & Integrations",
    items: [
      { to: "/app/super-admin", label: "User management", icon: Users, roles: ROLES.SUPER_ADMIN_ONLY },
      { to: "/app/admin", label: "Admin & governance", icon: GearSix, roles: ROLES.SUPER_ADMIN_ONLY },
      { to: "/app/admin/master-audit", label: "Master audit trail", icon: ClipboardText, roles: ROLES.SUPER_ADMIN_ONLY },
      { to: "/app/admin/master-dq", label: "Master data quality", icon: Database, roles: ROLES.SUPER_ADMIN_ONLY },
      { to: "/app/integrations", label: "Integrations hub", icon: LinkSimple, roles: ROLES.SUPER_ADMIN_ONLY },
      { to: "/app/connectors", label: "Connectors", icon: Plug, roles: ROLES.SUPER_ADMIN_ONLY },
      { to: "/app/approvals", label: "Approvals", icon: CheckCircle, roles: ROLES.SUPER_ADMIN_ONLY },
      { to: "/app/upload", label: "Ingest CSV", icon: CloudArrowUp, roles: ROLES.SUPER_ADMIN_ONLY },
    ],
  },
  {
    id: "platform",
    title: "Platform",
    items: [
      { to: "/app/rollups", label: "Entity rollups", icon: TreeStructure, roles: ROLES.SUPER_ADMIN_ONLY },
      { to: "/app/governance", label: "Retention & legal hold", icon: FileLock, roles: ROLES.SUPER_ADMIN_ONLY },
    ],
  },
  {
    id: "smoke-views",
    title: "Command previews",
    items: [
      { to: "/app/cfo-command-center", label: "CFO module map", icon: SquaresFour, roles: ROLES.SUPER_ADMIN_ONLY },
      { to: "/app/cfo", label: "CFO cockpit (preview)", icon: Gauge, roles: ROLES.SUPER_ADMIN_ONLY },
      { to: "/app/readiness", label: "Readiness matrix (preview)", icon: Table, roles: ROLES.SUPER_ADMIN_ONLY },
      { to: "/app/risk-intelligence", label: "Risk intelligence (preview)", icon: Eye, roles: ROLES.SUPER_ADMIN_ONLY },
      { to: "/app/controller", label: "Controller (preview)", icon: Desktop, roles: ROLES.SUPER_ADMIN_ONLY },
    ],
  },
];

export function getSidebarNavGroups(user) {
  const u = user || { role: "CFO", full_name: "", email: "" };
  if (u.role === "Super Admin") return filterGroups(u, SUPER_ADMIN_GROUPS);
  if (ROLES.AUDITOR_BUNDLE.includes(u.role)) return auditorNavGroups(u);
  return filterGroups(u, CFO_GROUPS);
}

/** Longest-prefix match for breadcrumb titles (more specific paths must win via length sort in labelForPath). */
export const ROUTE_LABELS = [
  { prefix: "/app/audit-planning/engagements", label: "Engagement" },
  { prefix: "/app/audit-planning/new", label: "New engagement" },
  { prefix: "/app/audit-planning/calendar", label: "Calendar" },
  { prefix: "/app/audit-planning/control-library", label: "Control library" },
  { prefix: "/app/audit-planning", label: "Audit planning" },

  { prefix: "/app/finance-operations/month-end-close", label: "Month-end close" },
  { prefix: "/app/finance-operations/team-performance", label: "Finance team performance" },
  { prefix: "/app/finance-operations/budget-vs-actual-dashboard", label: "Budget vs actual" },
  { prefix: "/app/finance-operations/budget-vs-actual", label: "Budget vs actual" },
  { prefix: "/app/finance-operations/forecast-accuracy-dashboard", label: "Forecast accuracy" },
  { prefix: "/app/finance-operations/forecast-accuracy", label: "Forecast accuracy" },
  { prefix: "/app/finance-operations/budget-master", label: "Budget master" },
  { prefix: "/app/finance-operations/budget", label: "Budget master" },
  { prefix: "/app/finance-operations/fpa", label: "FP&A snapshot" },
  { prefix: "/app/finance-operations", label: "Finance operations" },

  { prefix: "/app/financial-audit/gl-audit-dashboard", label: "GL audit workbench" },
  { prefix: "/app/financial-audit/journal-risk-dashboard", label: "Journal risk" },
  { prefix: "/app/financial-audit/reconciliations-dashboard", label: "Reconciliations workbench" },
  { prefix: "/app/financial-audit/bank-reconciliation-dashboard", label: "Bank reconciliation" },
  { prefix: "/app/financial-audit/inventory-audit-dashboard", label: "Inventory audit" },
  { prefix: "/app/financial-audit/physical-verification-dashboard", label: "Physical verification" },
  { prefix: "/app/financial-audit/fixed-assets-capex-dashboard", label: "Fixed assets & CAPEX" },
  { prefix: "/app/financial-audit/gl-audit", label: "GL audit (hub)" },
  { prefix: "/app/financial-audit/journal-risk", label: "Journal risk (hub)" },
  { prefix: "/app/financial-audit/reconciliations", label: "Reconciliations (hub)" },
  { prefix: "/app/financial-audit/bank-reconciliation", label: "Bank reconciliation (hub)" },
  { prefix: "/app/financial-audit/inventory-audit", label: "Inventory audit (hub)" },
  { prefix: "/app/financial-audit/physical-verification", label: "Physical verification (hub)" },
  { prefix: "/app/financial-audit/fixed-assets-capex", label: "Fixed assets & CAPEX (hub)" },
  { prefix: "/app/financial-audit", label: "Financial audit" },

  { prefix: "/app/continuous-audit/rules-engine-dashboard", label: "Continuous audit rules" },
  { prefix: "/app/continuous-audit/vendor-risk-dashboard", label: "Vendor risk" },
  { prefix: "/app/continuous-audit/three-way-match-dashboard", label: "Three-way match" },
  { prefix: "/app/continuous-audit/o2c-audit-dashboard", label: "Order-to-cash audit" },
  { prefix: "/app/continuous-audit/credit-notes-dashboard", label: "Credit note analytics" },
  { prefix: "/app/continuous-audit/revenue-audit", label: "Revenue assurance audit" },
  { prefix: "/app/continuous-audit/credit-note-analytics", label: "Credit note analytics" },
  { prefix: "/app/continuous-audit/rules-engine", label: "Rules engine (hub)" },
  { prefix: "/app/continuous-audit/vendor-risk", label: "Vendor risk (hub)" },
  { prefix: "/app/continuous-audit/three-way-match", label: "Three-way match (hub)" },
  { prefix: "/app/continuous-audit", label: "Continuous audit" },

  { prefix: "/app/working-capital/cash-conversion", label: "Cash conversion cycle" },
  { prefix: "/app/working-capital/receivables", label: "Receivables · AR ageing" },
  { prefix: "/app/working-capital/payables", label: "Payables · AP ageing" },
  { prefix: "/app/working-capital-command-center", label: "Working capital · Command center" },
  { prefix: "/app/working-capital", label: "Working capital" },

  { prefix: "/app/treasury/cash-forecast", label: "Cash forecast · 13-week" },
  { prefix: "/app/treasury/forex-exposure-dashboard", label: "Forex exposure workbench" },
  { prefix: "/app/treasury/debt-investments-dashboard", label: "Debt & investments" },
  { prefix: "/app/treasury/forex-exposure", label: "Forex exposure" },
  { prefix: "/app/treasury/dashboard", label: "Treasury dashboard" },
  { prefix: "/app/treasury-command-center", label: "Treasury · Command center" },
  { prefix: "/app/treasury", label: "Treasury" },

  { prefix: "/app/compliance/rpt-dashboard", label: "Related party transactions" },
  { prefix: "/app/compliance/legal-dashboard", label: "Legal notices & litigation" },
  { prefix: "/app/compliance/related-party-transactions", label: "Related party transactions" },
  { prefix: "/app/compliance/notices-litigation", label: "Legal notices & litigation" },
  { prefix: "/app/compliance-command-center", label: "Compliance · Command center" },
  { prefix: "/app/compliance", label: "Compliance" },

  { prefix: "/app/risk-intelligence-command-center", label: "Risk Intelligence Command Center" },
  { prefix: "/app/risk-intelligence/policy-compliance-dashboard", label: "Policy compliance" },
  { prefix: "/app/risk-intelligence/user-access-sod-dashboard", label: "User access & SoD" },
  { prefix: "/app/risk-intelligence/master-data-quality-dashboard", label: "Master data quality" },
  { prefix: "/app/risk-intelligence/risk-scoring-dashboard", label: "Risk scoring" },
  { prefix: "/app/risk-intelligence/doa-dashboard", label: "Delegation of authority" },
  { prefix: "/app/risk-intelligence/delegation-of-authority", label: "Delegation of authority (overview)" },
  { prefix: "/app/risk-intelligence/policy-compliance", label: "Policy compliance (overview)" },
  { prefix: "/app/risk-intelligence/user-access-sod", label: "Access & SoD (overview)" },
  { prefix: "/app/risk-intelligence/master-data-quality", label: "Master data quality (overview)" },
  { prefix: "/app/risk-intelligence", label: "Risk intelligence" },

  { prefix: "/app/cfo-command-center", label: "CFO Command Center" },
  { prefix: "/app/cfo-action-queue", label: "CFO action queue" },
  { prefix: "/app/kpi", label: "KPI drill-down" },
  { prefix: "/app/readiness", label: "Process readiness" },
  { prefix: "/app/evidence-cases", label: "Evidence & cases" },
  { prefix: "/app/board-reporting/report-automation-dashboard", label: "Report automation" },
  { prefix: "/app/board-reporting", label: "Board reporting" },
  { prefix: "/app/ai-copilot", label: "AI Copilot" },
  { prefix: "/app/integrations/integration-hub-dashboard", label: "Integration hub" },
  { prefix: "/app/integrations", label: "Integrations" },
  { prefix: "/app/enterprise-hardening/enterprise-hardening-dashboard", label: "Enterprise hardening" },
  { prefix: "/app/enterprise-hardening", label: "Enterprise hardening hub" },
  { prefix: "/app/reconciliations", label: "Reconciliation" },
  { prefix: "/app/cfo", label: "CFO cockpit" },
  { prefix: "/app/controller", label: "Controller dashboard" },
  { prefix: "/app/audit", label: "Audit workspace" },
  { prefix: "/app/my-cases", label: "My cases" },
  { prefix: "/app/cases", label: "Cases" },
  { prefix: "/app/evidence/evidence-intelligence-dashboard", label: "Evidence intelligence" },
  { prefix: "/app/evidence/document-intelligence", label: "Document intelligence" },
  { prefix: "/app/evidence", label: "Evidence explorer" },
  { prefix: "/app/copilot/copilot-2-dashboard", label: "Copilot 2.0" },
  { prefix: "/app/copilot", label: "Copilot workspace" },
  { prefix: "/app/admin/security", label: "Security" },
  { prefix: "/app/admin/system-health", label: "System health" },
  { prefix: "/app/admin/audit-logs", label: "Audit logs" },
  { prefix: "/app/admin/org-backfill", label: "Org backfill" },
  { prefix: "/app/admin/master-audit", label: "Master audit trail" },
  { prefix: "/app/admin/master-dq", label: "Master data quality (admin)" },
  { prefix: "/app/admin", label: "Admin console" },
  { prefix: "/app/audit-log", label: "Audit log" },
  { prefix: "/app/executive-review", label: "Executive review" },
  { prefix: "/app/audit-committee", label: "Audit committee" },
  { prefix: "/app/drill", label: "Drill-down" },
  // Drill types (used by global Breadcrumbs; `labelForPath` further customizes leaf nodes)
  { prefix: "/app/drill/user", label: "User" },
  { prefix: "/app/drill/vendor", label: "Vendor" },
  { prefix: "/app/drill/customer", label: "Customer" },
  { prefix: "/app/drill/invoice", label: "Invoice" },
  { prefix: "/app/drill/payment", label: "Payment" },
  { prefix: "/app/drill/journal", label: "Journal entry" },
  { prefix: "/app/drill/control", label: "Control" },
  { prefix: "/app/drill/ar_invoice", label: "AR invoice" },
  { prefix: "/app/drill/sales_order", label: "Sales order" },
  { prefix: "/app/drill/employee", label: "Employee" },
  { prefix: "/app/drill/payroll_entry", label: "Payroll entry" },
  { prefix: "/app/drill/bank_transaction", label: "Bank transaction" },
  { prefix: "/app/drill/fixed_asset", label: "Fixed asset" },
  { prefix: "/app/drill/capex_project", label: "Capex project" },
  { prefix: "/app/fs-hub", label: "FS Hub" },
  { prefix: "/app/fs-audit", label: "FS audit" },
  { prefix: "/app/schedule", label: "Schedule" },
  { prefix: "/app/ifc", label: "IFC" },
  { prefix: "/app/india-compliance", label: "India compliance" },
  { prefix: "/app/working-papers", label: "Working papers" },
  { prefix: "/app/reporting-studio", label: "Reporting studio" },
  { prefix: "/app/reporting-tab", label: "Reporting tab" },
  { prefix: "/app/ca-command-center", label: "CA command center" },
  { prefix: "/app/super-admin", label: "Super admin" },
  { prefix: "/app/rollups", label: "Entity rollups" },
  { prefix: "/app/governance", label: "Governance" },
  { prefix: "/app/connectors", label: "Connectors" },
  { prefix: "/app/approvals", label: "Approvals" },
  { prefix: "/app/upload", label: "Upload" },
  { prefix: "/app/auditor", label: "Auditor portal" },
  { prefix: "/app", label: "Workspace" },
];

function shortBreadcrumbRef(segment, maxLen = 22) {
  if (!segment) return "";
  const d = decodeURIComponent(segment);
  return d.length > maxLen ? `${d.slice(0, maxLen)}…` : d;
}

const EVIDENCE_STATIC_SLUGS = new Set(["evidence-intelligence-dashboard", "document-intelligence"]);

/**
 * Paths that include dynamic IDs or query-sensitive titles — evaluated before ROUTE_LABELS prefix match.
 */
function dynamicBreadcrumbLabel(pathWithOptionalQuery) {
  const qIdx = pathWithOptionalQuery.indexOf("?");
  const path = qIdx >= 0 ? pathWithOptionalQuery.slice(0, qIdx) : pathWithOptionalQuery;
  const query = qIdx >= 0 ? pathWithOptionalQuery.slice(qIdx + 1) : "";
  const params = new URLSearchParams(query ? `?${query}` : "");

  if (path === "/app/executive-review") {
    const tab = params.get("tab");
    if (tab === "assurance") return "Executive review · Continuous assurance";
    if (tab === "committee") return "Executive review · Committee";
    if (tab) return `Executive review · ${shortBreadcrumbRef(tab, 24)}`;
  }

  const kpiLeaf = path.match(/^\/app\/kpi\/([^/]+)$/);
  if (kpiLeaf) {
    const raw = kpiLeaf[1].replace(/-/g, " ").replace(/_/g, " ");
    return `KPI · ${shortBreadcrumbRef(raw, 36)}`;
  }

  const caseLeaf = path.match(/^\/app\/cases\/([^/]+)$/);
  if (caseLeaf) return `Case · ${shortBreadcrumbRef(caseLeaf[1])}`;

  const reconLeaf = path.match(/^\/app\/reconciliations\/([^/]+)$/);
  if (reconLeaf) return `Reconciliation · ${shortBreadcrumbRef(reconLeaf[1])}`;

  const auditLogLeaf = path.match(/^\/app\/audit-log\/([^/]+)$/);
  if (auditLogLeaf) return `Audit log · ${shortBreadcrumbRef(auditLogLeaf[1])}`;

  const evidenceLeaf = path.match(/^\/app\/evidence\/([^/]+)$/);
  if (evidenceLeaf && !EVIDENCE_STATIC_SLUGS.has(evidenceLeaf[1])) {
    return `Evidence · ${shortBreadcrumbRef(evidenceLeaf[1])}`;
  }

  const engTeam = path.match(/^\/app\/audit-planning\/engagements\/([^/]+)\/team$/);
  if (engTeam) return `Engagement team · ${shortBreadcrumbRef(engTeam[1])}`;
  const engRacm = path.match(/^\/app\/audit-planning\/engagements\/([^/]+)\/racm$/);
  if (engRacm) return `RACM builder · ${shortBreadcrumbRef(engRacm[1])}`;
  const engFs = path.match(/^\/app\/audit-planning\/engagements\/([^/]+)\/fs-audit$/);
  if (engFs) return `Financial statement audit · ${shortBreadcrumbRef(engFs[1])}`;
  const engSch = path.match(/^\/app\/audit-planning\/engagements\/([^/]+)\/schedules-audit$/);
  if (engSch) return `Schedules audit · ${shortBreadcrumbRef(engSch[1])}`;
  const engIfc = path.match(/^\/app\/audit-planning\/engagements\/([^/]+)\/ifc-engine$/);
  if (engIfc) return `IFC engine · ${shortBreadcrumbRef(engIfc[1])}`;

  if (/^\/app\/audit-planning\/engagements\/[^/]+\/working-papers\/sampling$/.test(path)) return "Sampling engine";
  if (/^\/app\/audit-planning\/engagements\/[^/]+\/working-papers\/vouching$/.test(path)) return "Vouching workbench";
  const wpPaper = path.match(/^\/app\/audit-planning\/engagements\/([^/]+)\/working-papers\/([^/]+)$/);
  if (wpPaper && wpPaper[2] !== "sampling" && wpPaper[2] !== "vouching") {
    return `Working paper · ${shortBreadcrumbRef(wpPaper[2])}`;
  }
  if (/^\/app\/audit-planning\/engagements\/[^/]+\/working-papers$/.test(path)) return "Working papers";

  const indiaLeaf = path.match(/^\/app\/audit-planning\/engagements\/([^/]+)\/india-compliance\/([^/]+)$/);
  if (indiaLeaf) {
    const leafMap = {
      "companies-act": "Companies Act",
      gst: "GST audit",
      tds: "TDS",
      "tax-44ab": "Tax 44AB",
      caro: "CARO",
      calendar: "Compliance calendar",
    };
    return leafMap[indiaLeaf[2]] || `India compliance · ${shortBreadcrumbRef(indiaLeaf[2])}`;
  }
  if (/^\/app\/audit-planning\/engagements\/[^/]+\/india-compliance$/.test(path)) return "India compliance";

  const rsLeaf = path.match(/^\/app\/audit-planning\/engagements\/([^/]+)\/report-studio\/([^/]+)$/);
  if (rsLeaf) {
    const rsMap = {
      observations: "Observations builder",
      opinion: "Audit opinion",
      caro: "CARO annexure",
      preview: "Report preview",
    };
    return rsMap[rsLeaf[2]] || `Report studio · ${shortBreadcrumbRef(rsLeaf[2])}`;
  }
  if (/^\/app\/audit-planning\/engagements\/[^/]+\/report-studio$/.test(path)) return "Report studio";

  const engOnly = path.match(/^\/app\/audit-planning\/engagements\/([^/]+)$/);
  if (engOnly) return `Engagement · ${shortBreadcrumbRef(engOnly[1])}`;

  return null;
}

export function labelForPath(pathname) {
  const dynamic = dynamicBreadcrumbLabel(pathname);
  if (dynamic) return dynamic;

  const path = pathname.split("?")[0];
  // Special-case: avoid repeating "Drill-down" for nested drill routes like:
  // /app/drill/<type>/<id> → "User · UA-17" (instead of Drill-down → Drill-down → Drill-down)
  const m = path.match(/^\/app\/drill\/([^/]+)\/([^/]+)$/);
  if (m) {
    const type = decodeURIComponent(m[1] || "");
    const id = decodeURIComponent(m[2] || "");
    const prettyType = type
      .replace(/_/g, " ")
      .replace(/-/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());
    const shortId = id.length > 24 ? `${id.slice(0, 24)}…` : id;
    return `${prettyType} · ${shortId}`;
  }
  const sorted = [...ROUTE_LABELS].sort((a, b) => b.prefix.length - a.prefix.length);
  for (const row of sorted) {
    if (path === row.prefix || path.startsWith(`${row.prefix}/`)) return row.label;
  }
  const tail = path.split("/").filter(Boolean).pop();
  if (tail) return shortBreadcrumbRef(tail.replace(/-/g, " "), 40);
  return "Page";
}

/** Module hub card content — keys match `hubKey` on ModuleHubPage */
export const MODULE_HUBS = {
  "cfo-command-center": {
    kicker: "CFO Command Center",
    title: "Executive control tower",
    subtitle:
      "Jump to the CFO cockpit for scoped KPIs, process readiness matrix, entity rollups, and committee workflows — master selections travel with each link.",
    showMasterFilters: true,
    cards: [
      {
        to: "/app/cfo",
        title: "CFO Cockpit",
        body: "Hero KPI band, readiness heatmaps, trends, drill-down links, exports, and action queue.",
        badge: "Live",
        testId: "hub-card-cfo-cockpit",
      },
      {
        to: "/app/cfo-action-queue",
        title: "CFO Action Queue",
        body: "Full prioritized queue with refresh, filters, detail, and approve / escalate — scoped to master selections.",
        badge: "Live",
        testId: "hub-card-cfo-action-queue",
      },
      {
        to: "/app/readiness",
        title: "Process readiness",
        body: "Process maturity matrix scoped to reporting context.",
        badge: "Live",
        testId: "hub-card-process-readiness",
      },
      {
        to: "/app/rollups",
        title: "Entity rollups",
        body: "Hierarchy drill-down and consolidated KPIs.",
        badge: "Live",
        testId: "hub-card-entity-rollups",
      },
      {
        to: "/app/controller",
        title: "Controller dashboard",
        body: "Close blockers, reconciliations, and AP exceptions.",
        testId: "hub-card-controller",
      },
      {
        to: "/app/executive-review",
        title: "Executive review",
        body: "CFO & committee workflows.",
        testId: "hub-card-executive-review",
      },
    ],
  },
  "finance-operations": {
    kicker: "Finance Operations",
    title: "Month-end, FP&A, and operations",
    subtitle: "Month-end close cycles now live (Slice 4). Budget and forecast modules land next.",
    showMasterFilters: true,
    cards: [
      {
        to: "/app/finance-operations/month-end-close",
        title: "Month-end close",
        body: "Close cycles, tasks, evidence, and sign-off gates.",
        badge: "Live",
        testId: "hub-card-month-end-close",
      },
      {
        to: "/app/finance-operations/team-performance",
        title: "Finance team",
        body: "Close + controller + queue in one view.",
        badge: "Live",
        testId: "hub-card-finance-team",
      },
      {
        to: "/app/finance-operations/budget-master",
        title: "Budget master",
        body: "Phase 12 budget uploads & approvals — surfaced on FP&A KPIs (/budget/* APIs).",
        badge: "Live",
        testId: "hub-card-budget-master",
      },
      {
        to: "/app/finance-operations/budget-vs-actual-dashboard",
        title: "Budget vs actual",
        body: "Phase 13 BvA & variance workflow — /budget/budget-vs-actual + /budget/variance APIs.",
        badge: "Live",
        testId: "hub-card-budget-vs-actual",
      },
      {
        to: "/app/finance-operations/forecast-accuracy-dashboard",
        title: "Forecast accuracy",
        body: "Phase 14 forecast vs actual — /forecast · /forecast/vs-actual · /forecast/accuracy APIs.",
        badge: "Live",
        testId: "hub-card-forecast-accuracy",
      },
      {
        to: "/app/finance-operations/fpa",
        title: "FP&A snapshot",
        body: "Budget vs actual (CapEx) plus journal spend proxy for planning.",
        badge: "Live",
        testId: "hub-card-fpa-snapshot",
      },
      { to: "/app/controller", title: "Controller dashboard", body: "Operational close view, reconciliations, and AP exceptions.", badge: "Live" },
      { to: "/app/audit", title: "Audit workspace", body: "Control testing and exceptions feeding close quality.", badge: "Live" },
    ],
  },
  "financial-audit": {
    kicker: "Financial Audit",
    title: "Audit & substantive work",
    subtitle: "Bridge to statutory audit modules and internal audit workspace.",
    showMasterFilters: true,
    cards: [
      { to: "/app/audit", title: "Audit workspace", body: "Controls, tests, and exceptions.", badge: "Live" },
      {
        to: "/app/financial-audit/gl-audit-dashboard",
        title: "GL audit workbench",
        body: "Phase 15 GL summary, accounts & movement — /gl/* APIs.",
        badge: "Live",
        testId: "hub-card-gl-audit-workbench",
      },
      {
        to: "/app/financial-audit/journal-risk-dashboard",
        title: "Journal risk",
        body: "Phase 16 JE scoring, rules & reviews — /journals/* APIs.",
        badge: "Live",
        testId: "hub-card-journal-risk-workbench",
      },
      {
        to: "/app/financial-audit/reconciliations-dashboard",
        title: "Reconciliations",
        body: "Phase 17 rec workflow — /reconciliations list · detail · evidence · submit · approve.",
        badge: "Live",
        testId: "hub-card-reconciliations-workbench",
      },
      {
        to: "/app/financial-audit/bank-reconciliation-dashboard",
        title: "Bank reconciliation",
        body: "Phase 18 stmt upload · auto-match · classify · sign-off — /bank-recon/* APIs.",
        badge: "Live",
        testId: "hub-card-bank-recon-workbench",
      },
      {
        to: "/app/financial-audit/inventory-audit-dashboard",
        title: "Inventory audit",
        body: "Phase 23 ageing · slow-moving · NRV exceptions — /inventory-audit/* APIs.",
        badge: "Live",
        testId: "hub-card-inventory-audit-workbench",
      },
      {
        to: "/app/financial-audit/physical-verification-dashboard",
        title: "Physical verification",
        body: "Phase 24 count cycles · upload · variance · reason · approve — /physical-verification/* APIs.",
        badge: "Live",
        testId: "hub-card-physical-verification-workbench",
      },
      {
        to: "/app/financial-audit/fixed-assets-capex-dashboard",
        title: "Fixed assets · CAPEX",
        body: "Phase 25 register · depreciation exceptions · capex overrun — /fixed-assets-audit/* APIs.",
        badge: "Live",
        testId: "hub-card-fixed-assets-capex-workbench",
      },
      { to: "/app/audit-planning", title: "Audit planning", body: "Engagements, RACM, FS audit, IFC, WPs.", badge: "Live" },
      { to: "/app/evidence", title: "Evidence explorer", body: "Trace exceptions to evidence.", badge: "Live" },
    ],
  },
  "continuous-audit": {
    kicker: "Continuous Audit",
    title: "Always-on monitoring",
    subtitle: "Rules engine and exception workflows will extend from this hub.",
    showMasterFilters: true,
    cards: [
      { to: "/app/executive-review?tab=assurance", title: "Continuous assurance", body: "Assurance tab in executive review.", badge: "Live" },
      {
        to: "/app/continuous-audit/rules-engine-dashboard",
        title: "Rules engine",
        body: "Phase 35 rules · run · CA exceptions · rule performance — /continuous-audit/* APIs.",
        badge: "Live",
        testId: "hub-card-continuous-audit-rules-workbench",
      },
      {
        to: "/app/continuous-audit/vendor-risk-dashboard",
        title: "Vendor risk",
        body: "Phase 19 procurement & vendor hygiene — /vendor-risk/* APIs.",
        badge: "Live",
        testId: "hub-card-vendor-risk-workbench",
      },
      {
        to: "/app/continuous-audit/three-way-match-dashboard",
        title: "Three-way match",
        body: "Phase 20 PO·GRN·invoice engine — /three-way-match/* APIs.",
        badge: "Live",
        testId: "hub-card-three-way-match-workbench",
      },
      {
        to: "/app/continuous-audit/o2c-audit-dashboard",
        title: "O2C audit",
        body: "Phase 21 customers · AR · revenue/credit signals — /o2c/* APIs.",
        badge: "Live",
        testId: "hub-card-o2c-audit-workbench",
      },
      {
        to: "/app/continuous-audit/credit-notes-dashboard",
        title: "Credit notes",
        body: "Phase 22 credit note register · high-risk · revenue reversals — /credit-notes/* APIs.",
        badge: "Live",
        testId: "hub-card-credit-notes-workbench",
      },
      {
        to: "/app/continuous-audit/revenue-audit",
        title: "Revenue audit (SRS path)",
        body: "SRS alias — order-to-cash / revenue cycle monitoring (O2C audit workbench).",
        badge: "Live",
      },
      {
        to: "/app/continuous-audit/credit-note-analytics",
        title: "Credit note analytics (SRS path)",
        body: "SRS alias — credit note concentration & reversal signals (credit notes workbench).",
        badge: "Live",
      },
      { to: "/app/audit", title: "Controls & tests", body: "Re-run controls and monitor exceptions.", badge: "Live" },
    ],
  },
  "working-capital": {
    kicker: "Working Capital",
    title: "Cash conversion & liquidity levers",
    subtitle: "Slice 5–8 — AR/AP ageing + cash conversion cycle proxies (DSO/DPO/CCC).",
    showMasterFilters: true,
    cards: [
      {
        to: "/app/working-capital",
        title: "Working capital dashboard",
        body: "AR/AP ageing, overdue exposure, and WC exceptions.",
        badge: "Live",
        testId: "hub-card-wc-dashboard",
      },
      {
        to: "/app/working-capital/receivables",
        title: "Receivables · AR ageing",
        body: "Phase 9 AR surfaced on the WC dashboard slice (customers, invoices, disputes — API-backed).",
        badge: "Live",
        testId: "hub-card-ar-receivables",
      },
      {
        to: "/app/working-capital/payables",
        title: "Payables · AP ageing",
        body: "Phase 10 AP on the WC slice (AP ageing, vendors, payment calendar — API-backed).",
        badge: "Live",
        testId: "hub-card-ap-payables",
      },
      { to: "/app/working-capital/cash-conversion", title: "Cash conversion cycle", body: "DSO/DPO/CCC proxies with exception signals.", badge: "Live" },
      { to: "/app/controller", title: "Controller", body: "Close-impacting reconciliations and AP exceptions.", badge: "Live" },
    ],
  },
  treasury: {
    kicker: "Treasury",
    title: "Cash, debt, and bank governance",
    subtitle: "Treasury tower, forex, and covenant tracking — core dashboards live; 13-week cash stub on API.",
    showMasterFilters: true,
    cards: [
      {
        to: "/app/treasury",
        title: "Treasury hub",
        body: "Bank accounts, cash movement, and treasury exceptions.",
        badge: "Live",
        testId: "hub-card-treasury-dashboard",
      },
      {
        to: "/app/treasury/cash-forecast",
        title: "Cash forecast · 13-week",
        body: "Phase 11 cash runway — APIs: /treasury/cash-position · /treasury/forecast-13-week · /treasury/shortfall-alerts.",
        badge: "Live",
        testId: "hub-card-cash-forecast",
      },
      {
        to: "/app/treasury/debt-investments-dashboard",
        title: "Debt & investments",
        body: "Phase 26 debt register · repayment · investments · covenants — /treasury/* Phase 26 APIs.",
        badge: "Live",
        testId: "hub-card-treasury-debt-investments-workbench",
      },
      {
        to: "/app/treasury/forex-exposure-dashboard",
        title: "Forex exposure",
        body: "Phase 27 exposures · hedges · unhedged risk — /forex/* APIs.",
        badge: "Live",
        testId: "hub-card-forex-exposure-workbench",
      },
      { to: "/app/working-capital/cash-conversion", title: "Cash conversion cycle", body: "DSO/DPO/CCC proxies with exception signals.", badge: "Live" },
      { to: "/app/controller", title: "Controller", body: "Bank recon-related tasks and close blockers.", badge: "Live" },
      { to: "/app/connectors", title: "Bank / ERP connectors", body: "Integration health for feeds driving treasury views.", badge: "Live" },
    ],
  },
  compliance: {
    kicker: "Compliance",
    title: "Policy, access & disclosures",
    subtitle: "RPT register, notices, and the live compliance KPI dashboard.",
    showMasterFilters: true,
    cards: [
      {
        to: "/app/compliance",
        title: "Compliance dashboard",
        body: "SoD, terminated users, policy breaches — /dashboard/compliance.",
        badge: "Live",
        testId: "hub-card-compliance-main",
      },
      {
        to: "/app/compliance/rpt-dashboard",
        title: "Related party transactions",
        body: "Phase 28 RPT master · txns · balances · checklist — /rpt/* APIs.",
        badge: "Live",
        testId: "hub-card-rpt-workbench",
      },
      {
        to: "/app/compliance/legal-dashboard",
        title: "Legal notices & litigation",
        body: "Phase 29 notices · litigations · hearings · exposure — /legal/* APIs.",
        badge: "Live",
        testId: "hub-card-legal-workbench",
      },
      {
        to: "/app/compliance/related-party-transactions",
        title: "Related party (SRS path)",
        body: "SRS alias to the RPT workbench — same screen as Related party transactions.",
        badge: "Live",
      },
      {
        to: "/app/compliance/notices-litigation",
        title: "Legal notices (SRS path)",
        body: "SRS alias to the legal & litigation workbench — same screen as Legal notices & litigation.",
        badge: "Live",
      },
    ],
  },
  "risk-intelligence": {
    kicker: "Risk Intelligence",
    title: "Cross-module risk signals",
    subtitle: "Phase 36–39 — Hub + consolidated API + scoped AI insights; committee-pack export; master/?process= links (CFO, compliance, readiness).",
    showMasterFilters: true,
    cards: [
      { to: "/app/risk-intelligence", title: "Risk intelligence hub", body: "Scoring, heatmap, top risks, master scores, AI insights, and one-click shareable links.", badge: "Live" },
      {
        to: "/app/risk-intelligence/risk-scoring-dashboard",
        title: "Finance risk scoring",
        body: "Phase 36 summary · scores · heatmap · recalculate — /risk-intelligence/* APIs.",
        badge: "Live",
        testId: "hub-card-risk-scoring-workbench",
      },
      {
        to: "/app/risk-intelligence/doa-dashboard",
        title: "Delegation of authority",
        body: "Phase 30 approval matrix · rules · breaches · validate — /doa/* APIs.",
        badge: "Live",
        testId: "hub-card-doa-workbench",
      },
      {
        to: "/app/risk-intelligence/policy-compliance-dashboard",
        title: "Policy compliance",
        body: "Phase 31 policies · attestations · breach-to-case — /policies/* APIs.",
        badge: "Live",
        testId: "hub-card-policy-compliance-workbench",
      },
      {
        to: "/app/risk-intelligence/user-access-sod-dashboard",
        title: "Access & SoD",
        body: "Phase 32 users · roles · SoD conflicts · dormant · certification — /access/* APIs.",
        badge: "Live",
        testId: "hub-card-access-sod-workbench",
      },
      {
        to: "/app/risk-intelligence/master-data-quality-dashboard",
        title: "Master data quality",
        body: "Phase 33 DQ summary · vendors · duplicates · change-audit · case-from-finding — /master-data-quality/* APIs.",
        badge: "Live",
        testId: "hub-card-master-dq-workbench",
      },
      { to: "/app/cfo", title: "CFO cockpit", body: "Full command center with trends and exports.", badge: "Live" },
      { to: "/app/compliance", title: "Compliance", body: "Policy and access risk snapshots.", badge: "Live" },
    ],
  },
  "board-reporting": {
    kicker: "Board Reporting",
    title: "Audit committee & board packs",
    subtitle: "Board-ready reporting and exports.",
    showMasterFilters: true,
    cards: [
      {
        to: "/app/board-reporting/report-automation-dashboard",
        title: "Report automation workbench",
        body: "Phase 39 templates · generate · versions — /reports/* APIs (board pack automation).",
        badge: "Live",
        testId: "hub-card-board-reporting-workbench",
      },
      { to: "/app/audit-committee", title: "Audit committee", body: "CFO audit committee dashboard.", badge: "Live" },
      { to: "/app/executive-review", title: "Executive review", body: "CFO & committee hub.", badge: "Live" },
      { to: "/app/reporting-studio", title: "Reporting studio", body: "CA reporting workflows.", badge: "Live" },
    ],
  },
  "ai-copilot": {
    kicker: "AI Copilot",
    title: "Finance-aware assistant",
    subtitle: "Copilot 2.0 will extend this surface.",
    showMasterFilters: true,
    cards: [
      { to: "/app/copilot", title: "Open Copilot", body: "Ask questions across audit, controls, and cases.", badge: "Live" },
      {
        to: "/app/copilot/copilot-2-dashboard",
        title: "Copilot 2.0 workbench",
        body: "Phase 37 sessions · index status · retrieval configs — GET /copilot/*; ask & generate on POST.",
        badge: "Live",
        testId: "hub-card-copilot-2-workbench",
      },
    ],
  },
  "enterprise-hardening": {
    kicker: "Enterprise hardening",
    title: "System health & security controls",
    subtitle: "Phase 40 — Super Admin surfaces for liveness, dependency health, audit logs, and security singleton.",
    showMasterFilters: true,
    cards: [
      {
        to: "/app/enterprise-hardening/enterprise-hardening-dashboard",
        title: "Enterprise hardening workbench",
        body: "GET /system/health/live (public) + /health, /audit-logs, /security-config (Super Admin).",
        badge: "Live",
        testId: "hub-card-enterprise-hardening-workbench",
      },
    ],
  },
  integrations: {
    kicker: "Integrations",
    title: "Production integration hub",
    subtitle: "Connect ERPs, banks, and document stores. Phase 38 SRS paths under /integrations/connectors.",
    showMasterFilters: true,
    cards: [
      {
        to: "/app/integrations/integration-hub-dashboard",
        title: "Integration hub workbench",
        body: "Phase 38 connectors · sync logs · matrix · health/runs — GET /integrations/connectors/*.",
        badge: "Live",
        testId: "hub-card-integration-hub-workbench",
      },
      { to: "/app/connectors", title: "Connectors console", body: "Legacy /connectors UI (same backend).", badge: "Live" },
    ],
  },
  "evidence-cases": {
    kicker: "Evidence & Cases",
    title: "Investigations & evidence",
    subtitle: "Single entry for case work and evidence traceability.",
    showMasterFilters: true,
    cards: [
      { to: "/app/my-cases", title: "My cases", body: "Owned open work.", badge: "Live" },
      { to: "/app/cases", title: "All cases", body: "Enterprise case register.", badge: "Live" },
      {
        to: "/app/evidence/evidence-intelligence-dashboard",
        title: "Evidence intelligence",
        body: "Phase 34 extract · quality issues · link · review — /evidence-intelligence/* APIs.",
        badge: "Live",
        testId: "hub-card-evidence-intelligence-workbench",
      },
      { to: "/app/evidence", title: "Evidence explorer", body: "Graph and drill to source records.", badge: "Live" },
    ],
  },
};
