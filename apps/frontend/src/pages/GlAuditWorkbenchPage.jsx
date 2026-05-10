import React, { useCallback, useEffect, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { useWorkbenchRowDrill } from "../lib/workbenchDrillNav";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { StatCard } from "../components/StatCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { fmtUSD, fmtDate } from "../lib/format";

/** Resolve a journal id for `/app/drill/journal/:id` from `/gl/transactions` rows (journals vs generic transactions). */
function journalDrillIdFromGlTxn(row, source) {
  if (!row) return null;
  if (source === "journals") return row.id || null;
  const linked =
    row.journal_id ||
    row.journalId ||
    row.linked_journal_id ||
    row.ref_journal_id ||
    row.reference_journal_id ||
    null;
  if (linked) return linked;
  const id = row.id;
  if (typeof id === "string" && id.startsWith("JE-")) return id;
  return null;
}

export default function GlAuditWorkbenchPage() {
  const { drillNavigate } = useWorkbenchRowDrill();
  const { entityCode, periodExplicit } = useMastersFilters();
  const [d, setD] = useState(null);

  const params = useDashboardFilterParams();
  useEffect(() => {
    const acctParams = { ...params, limit: 20, offset: 0 };
    const txnParams = { ...params, limit: 25, offset: 0 };
    Promise.all([
      http.get("/gl/summary", { params }),
      http.get("/gl/accounts", { params: acctParams }),
      http.get("/gl/transactions", { params: txnParams }),
    ])
      .then(([s, a, tx]) =>
        setD({
          summary: s.data,
          accounts: a.data?.items || [],
          transactions: tx.data?.items || [],
          txnSource: tx.data?.source || "journals",
        }),
      )
      .catch(() => toast.error("Failed to load GL audit workbench"));
  }, [params]);

  const onTxnRowClick = useCallback(
    (row) => {
      const jid = journalDrillIdFromGlTxn(row, d?.txnSource);
      if (!jid) {
        toast.message("No journal drill target for this row.");
        return;
      }
      drillNavigate("journal", jid);
    },
    [d?.txnSource, drillNavigate],
  );

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="gl-audit-loading">
        Loading GL audit workbench…
      </div>
    );
  }

  const k = d.summary?.kpis || {};

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="gl-audit-page" data-gl-audit-surface="true">
        <PageHeader
          kicker="GENERAL LEDGER · PHASE 15"
          title="GL audit workbench"
          subtitle="Summary + account sample — APIs: /gl/summary · /gl/accounts · /gl/transactions · /gl/anomalies · /gl/movement-analysis."
        />

        <MastersFilterStrip className="mb-6" />
        {(entityCode || periodExplicit) && (
          <p className="crt-num mb-4 text-[10px] uppercase tracking-wider text-muted-foreground">
            GL scope follows entity and period when pinned in masters.
          </p>
        )}

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <StatCard label="GL txns (sample)" value={k.txn_count} testId="gl-kpi-txn-count" />
          <StatCard label="GL amount (sample)" value={fmtUSD(k.total_amount)} testId="gl-kpi-total-amount" />
        </div>

        <SectionCard kicker="MASTER DATA" title="GL accounts (seeded sample)">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[40vh]" testId="gl-accounts-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Code</DataTableTh>
                <DataTableTh>Name</DataTableTh>
                <DataTableTh>Entity</DataTableTh>
                <DataTableTh>Type</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {d.accounts.length === 0 ? (
                <tr>
                  <td colSpan={4} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                    No GL accounts in scope.
                  </td>
                </tr>
              ) : null}
              {d.accounts.map((r) => (
                <DataTableRow key={r.id || r.account_code} testId={`gl-acct-${r.account_code || r.id}`}>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{r.account_code || "—"}</DataTableTd>
                  <DataTableTd className="text-sm text-foreground">{r.account_name || "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{r.entity_code || "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-xs uppercase text-muted-foreground">{r.account_type || "—"}</DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>

        <div id="gl-journal-lines" className="mt-6">
          <SectionCard kicker="POSTINGS" title="GL postings / journal lines (sample)">
            <p className="crt-num mb-3 text-[10px] uppercase tracking-wider text-muted-foreground">
              Row click opens journal drill when a journal id is available (source: {d.txnSource || "—"}).
            </p>
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[48vh]" testId="gl-txns-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>Ref / id</DataTableTh>
                  <DataTableTh>Entity</DataTableTh>
                  <DataTableTh>Date</DataTableTh>
                  <DataTableTh align="right">Amount</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {(d.transactions || []).length === 0 ? (
                  <tr>
                    <td colSpan={4} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                      No postings in scope.
                    </td>
                  </tr>
                ) : null}
                {(d.transactions || []).map((t) => {
                  const ref = t.journal_number || t.reference || t.id || "—";
                  const amt = t.total_amount ?? t.amount;
                  const dt = t.posting_date || t.txn_date;
                  const drillable = Boolean(journalDrillIdFromGlTxn(t, d.txnSource));
                  return (
                    <DataTableRow
                      key={t.id || ref}
                      testId={`gl-txn-${encodeURIComponent(String(t.id || ref))}`}
                      onClick={drillable ? () => onTxnRowClick(t) : undefined}
                    >
                      <DataTableTd className="text-sm text-foreground">{ref}</DataTableTd>
                      <DataTableTd className="crt-num text-xs text-muted-foreground">{t.entity || t.entity_code || "—"}</DataTableTd>
                      <DataTableTd className="crt-num text-xs text-muted-foreground">{fmtDate(dt)}</DataTableTd>
                      <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                        {fmtUSD(amt)}
                      </DataTableTd>
                    </DataTableRow>
                  );
                })}
              </DataTableBody>
            </DataTable>
          </SectionCard>
        </div>
      </div>
    </PageShell>
  );
}
