/**
 * Canonical in-app paths for cross-surface drill-down (insights, evidence graph, dashboards).
 * Keep in sync with DrillView route `/app/drill/:type/:id` and backend GET /api/drill/{type}/{id}.
 */

export const DRILL_PATH_BUILDERS = {
  exception: (id) => `/app/evidence/${encodeURIComponent(id)}`,
  /** Open Evidence Intelligence workbench; optional `?document=` deep-link handled there. */
  evidence_document: (id) =>
    `/app/evidence/evidence-intelligence-dashboard?document=${encodeURIComponent(String(id))}`,
  /** Legacy / aggregate finance_risk_scores rows keyed by entity code only. */
  entity: (_entityCode) => `/app/risk-intelligence`,
  case: (id) => `/app/cases/${encodeURIComponent(id)}`,
  reconciliation: (id) => `/app/reconciliations/${encodeURIComponent(id)}`,
  control: (code) => `/app/drill/control/${encodeURIComponent(code)}`,
  invoice: (id) => `/app/drill/invoice/${encodeURIComponent(id)}`,
  vendor: (id) => `/app/drill/vendor/${encodeURIComponent(id)}`,
  customer: (id) => `/app/drill/customer/${encodeURIComponent(id)}`,
  payment: (id) => `/app/drill/payment/${encodeURIComponent(id)}`,
  journal: (id) => `/app/drill/journal/${encodeURIComponent(id)}`,
  user: (id) => `/app/drill/user/${encodeURIComponent(id)}`,
  fixed_asset: (id) => `/app/drill/fixed_asset/${encodeURIComponent(id)}`,
  capex_project: (id) => `/app/drill/capex_project/${encodeURIComponent(id)}`,
  payroll_entry: (id) => `/app/drill/payroll_entry/${encodeURIComponent(id)}`,
  ar_invoice: (id) => `/app/drill/ar_invoice/${encodeURIComponent(id)}`,
  sales_order: (id) => `/app/drill/sales_order/${encodeURIComponent(id)}`,
  employee: (id) => `/app/drill/employee/${encodeURIComponent(id)}`,
  bank_transaction: (id) => `/app/drill/bank_transaction/${encodeURIComponent(id)}`,
};

/**
 * @param {string} relatedType - key of DRILL_PATH_BUILDERS
 * @param {string} relatedId
 * @returns {string|null}
 */
export function pathForRelatedType(relatedType, relatedId) {
  if (!relatedType || relatedId == null || relatedId === "") return null;
  const key = String(relatedType).trim().toLowerCase().replace(/-/g, "_");
  const fn = DRILL_PATH_BUILDERS[key];
  return fn ? fn(String(relatedId)) : null;
}

/** Map exception.source_record_* to evidence drill path (access_event → user drill; id may be UA-* or email). */
export function exceptionSourceDrillPath(ex) {
  if (!ex) return null;
  const t = ex.source_record_type;
  const id = ex.source_record_id;
  if (!t || id == null || id === "") return null;
  const typ = String(t).trim().toLowerCase().replace(/-/g, "_");
  if (typ === "access_event") {
    const sid = String(id).trim();
    const email = ex.source_record_user_email || ex.user_email;
    if (email && String(email).includes("@")) return DRILL_PATH_BUILDERS.user(String(email).trim());
    return DRILL_PATH_BUILDERS.user(sid);
  }
  return pathForRelatedType(typ, id);
}

/**
 * Evidence graph node → app path (matches legacy EvidenceExplorer graph behavior).
 * @param {{ type: string, id: string, meta?: Record<string, unknown> }} node
 * @returns {string|null}
 */
/** Maps exception / evidence-graph source_record_type → drill builder key (see analytics.evidence_graph). */
const EVIDENCE_SOURCE_TO_DRILL = {
  invoice: "invoice",
  payment: "payment",
  journal: "journal",
  bank_transaction: "bank_transaction",
  customer: "customer",
  ar_invoice: "ar_invoice",
  sales_order: "sales_order",
  payroll_entry: "payroll_entry",
  employee: "employee",
  fixed_asset: "fixed_asset",
  depreciation: null,
  capex_project: "capex_project",
  fx_rate: null,
  withholding: null,
  reconciliation: "reconciliation",
  access_event: null, // handled via user_email on meta
  user: "user",
};

export function graphNodeDrillPath(node) {
  if (!node) return null;
  const { type, id } = node;
  const uid = String(id);
  const up = uid.toUpperCase();

  if (type === "transaction") {
    const rawSt = node.meta && node.meta.evidence_source_type;
    const st = rawSt != null ? String(rawSt).trim().toLowerCase().replace(/-/g, "_") : "";
    const drillKey = EVIDENCE_SOURCE_TO_DRILL[st];
    if (drillKey && DRILL_PATH_BUILDERS[drillKey]) {
      return DRILL_PATH_BUILDERS[drillKey](uid);
    }
    if (st === "access_event") {
      const email = node.meta && (node.meta.user_email || node.meta.email);
      if (email) return DRILL_PATH_BUILDERS.user(String(email));
      return null;
    }
    // Prefix heuristics (seed data + legacy graphs without evidence_source_type)
    if (up.startsWith("INV-")) return DRILL_PATH_BUILDERS.invoice(uid);
    if (up.startsWith("PAY-")) return DRILL_PATH_BUILDERS.payment(uid);
    if (up.startsWith("JE-")) return DRILL_PATH_BUILDERS.journal(uid);
    if (up.startsWith("BT-")) return DRILL_PATH_BUILDERS.bank_transaction(uid);
    if (up.startsWith("AR-")) return DRILL_PATH_BUILDERS.ar_invoice(uid);
    if (up.startsWith("SO-")) return DRILL_PATH_BUILDERS.sales_order(uid);
    if (up.startsWith("PO-") || up.startsWith("GRN-")) return null;
  }
  if (type === "control") return DRILL_PATH_BUILDERS.control(id);
  if (type === "case") return DRILL_PATH_BUILDERS.case(id);
  if (type === "working_paper") {
    const eng = node.meta?.engagement_id;
    if (eng) return `/app/audit-planning/engagements/${encodeURIComponent(eng)}?tab=wp`;
  }
  if (type === "user") {
    const em = id.startsWith("user::") ? id.slice(6) : id;
    return DRILL_PATH_BUILDERS.user(em);
  }
  if (type === "exception") return DRILL_PATH_BUILDERS.exception(id);
  return null;
}
