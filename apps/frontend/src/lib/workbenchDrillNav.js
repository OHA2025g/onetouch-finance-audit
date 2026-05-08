import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useMastersFilters } from "./MastersFilterContext";
import { pathForRelatedType } from "./drillPaths";

/** @typedef {{ type: string, id: string } | null} DrillTarget */

/**
 * Map finance txn id prefixes to canonical drill types (matches seeded ids).
 * @param {unknown} transactionId
 * @returns {DrillTarget}
 */
export function drillTargetFromTxnId(transactionId) {
  const id = transactionId == null ? "" : String(transactionId).trim();
  if (!id) return null;
  if (id.startsWith("PAY-")) return { type: "payment", id };
  if (id.startsWith("INV-")) return { type: "invoice", id };
  if (id.startsWith("JE-")) return { type: "journal", id };
  if (id.startsWith("BT-")) return { type: "bank_transaction", id };
  if (id.startsWith("AR-")) return { type: "ar_invoice", id };
  if (id.startsWith("SO-")) return { type: "sales_order", id };
  return null;
}

/**
 * Use exception.source_record_* style fields when present.
 * @param {Record<string, unknown>} row
 * @returns {DrillTarget}
 */
export function drillTargetFromSourceRecord(row) {
  const t = row?.source_record_type;
  const id = row?.source_record_id;
  if (!t || id == null || String(id).trim() === "") return null;
  const typ = String(t).trim().toLowerCase().replace(/-/g, "_");
  if (typ === "access_event") return { type: "user", id: String(id) };
  const skipEntity = new Set(["continuous_audit_rule", "inventory_item", "three_way_match_exception", "rpt_transaction"]);
  if (skipEntity.has(typ)) return null;
  const path = pathForRelatedType(typ, id);
  if (!path) return null;
  return { type: typ, id: String(id) };
}

/**
 * Rows from `exceptions` (continuous audit, control findings, etc.): prefer source-record drill, else evidence exception.
 * Skips policy breach rows (they carry `breach_type` / `policy_id`).
 * @param {Record<string, unknown>} row
 * @returns {DrillTarget}
 */
export function drillTargetExceptionListRow(row) {
  if (!row?.id) return null;
  if (row.policy_id != null || row.policy_title != null) return null;
  const sr = drillTargetFromSourceRecord(row);
  if (sr) return sr;
  if (row.control_code != null || row.title != null) return { type: "exception", id: String(row.id) };
  return { type: "exception", id: String(row.id) };
}

/** Policy breach document → underlying record when typed. */
export function drillTargetPolicyBreach(row) {
  return drillTargetFromSourceRecord(row);
}

/** Master DQ vendor/customer/employee finding → master entity drill. */
export function drillTargetMdqFinding(row) {
  const mt = row?.master_type;
  const oid = row?.object_id;
  if (!oid) return null;
  if (mt === "vendor") return { type: "vendor", id: String(oid) };
  if (mt === "customer") return { type: "customer", id: String(oid) };
  if (mt === "employee") return { type: "employee", id: String(oid) };
  return null;
}

/** Risk intelligence score row → drill when object_type maps to a builder. */
export function drillTargetRiskScoreRow(row) {
  const ot = row?.object_type;
  const oid = row?.object_id;
  if (!ot || oid == null || String(oid).trim() === "") return null;
  const t = String(ot).toLowerCase().replace(/-/g, "_");
  if (t === "gl_account" || t === "unknown") return null;
  const path = pathForRelatedType(t, oid);
  if (!path) return null;
  return { type: t, id: String(oid) };
}

/** Three-way match variance row → invoice when linked. */
export function drillTargetThreeWayMatchRow(row) {
  const inv = row?.invoice_id;
  if (inv) return { type: "invoice", id: String(inv) };
  const vid = row?.vendor_id;
  if (vid) return { type: "vendor", id: String(vid) };
  return null;
}

/** Credit note row → invoice, else vendor. */
export function drillTargetCreditNoteRow(row) {
  const inv = row?.invoice_id;
  if (inv) return { type: "invoice", id: String(inv) };
  const invLabel = row?.invoice_number;
  if (invLabel) {
    const fromRef = drillTargetFromTxnId(invLabel);
    if (fromRef) return fromRef;
  }
  const vid = row?.vendor_id;
  if (vid) return { type: "vendor", id: String(vid) };
  return null;
}

/** SoD conflict → user drill by email when available. */
export function drillTargetAccessConflictRow(row) {
  const email = row?.user_email || row?.user_id;
  if (email && String(email).includes("@")) return { type: "user", id: String(email) };
  return null;
}

/** Enterprise audit log row when object_type is a known drill entity. */
export function drillTargetAuditLogObject(row) {
  const ot = row?.object_type;
  const oid = row?.object_id;
  if (oid != null && String(oid).trim() !== "") {
    const idStr = String(oid).trim();
    if (ot) {
      const t = String(ot).toLowerCase().replace(/-/g, "_");
      const path = pathForRelatedType(t, idStr);
      if (path) return { type: t, id: idStr };
    }
    const txn = drillTargetFromTxnId(idStr);
    if (txn) return txn;
  }
  return null;
}

/** Evidence quality issue → exception when API links one. */
export function drillTargetEvidenceQiRow(row) {
  const ex = row?.exception_id ?? row?.linked_exception_id ?? row?.exceptionId;
  if (ex) return { type: "exception", id: String(ex) };
  const doc = row?.document_id;
  if (doc) return { type: "evidence_document", id: String(doc) };
  return null;
}

export function useWorkbenchRowDrill() {
  const navigate = useNavigate();
  const { hrefWithMasterParams } = useMastersFilters();

  const drillNavigate = useCallback(
    (type, id) => {
      if (id == null || String(id).trim() === "") {
        toast.message("Nothing to drill for this row.");
        return;
      }
      const path = pathForRelatedType(type, id);
      if (!path) {
        toast.message("No drill path for this record type.");
        return;
      }
      navigate(hrefWithMasterParams(path));
    },
    [hrefWithMasterParams, navigate],
  );

  const drillToTarget = useCallback(
    (target) => {
      if (!target?.type || target.id == null) {
        toast.message("No drill target for this row.");
        return;
      }
      drillNavigate(target.type, target.id);
    },
    [drillNavigate],
  );

  return { drillNavigate, drillToTarget };
}
