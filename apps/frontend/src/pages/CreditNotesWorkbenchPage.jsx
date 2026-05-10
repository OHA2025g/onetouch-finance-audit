import React, { useEffect, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { drillTargetCreditNoteRow, useWorkbenchRowDrill } from "../lib/workbenchDrillNav";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { StatCard } from "../components/StatCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { fmtUSD } from "../lib/format";

export default function CreditNotesWorkbenchPage() {
  const { drillToTarget } = useWorkbenchRowDrill();
  const [d, setD] = useState(null);

  const params = useDashboardFilterParams();
  useEffect(() => {
    const listParams = { ...params, limit: 35, offset: 0 };
    Promise.all([http.get("/credit-notes/summary", { params }), http.get("/credit-notes", { params: listParams })])
      .then(([s, list]) =>
        setD({
          summary: s.data || {},
          items: list.data?.items || [],
        }),
      )
      .catch(() => toast.error("Failed to load credit notes workbench"));
  }, [params]);

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="credit-notes-workbench-loading">
        Loading credit notes workbench…
      </div>
    );
  }

  const k = d.summary?.kpis || {};

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="credit-notes-workbench-page" data-credit-notes-workbench-surface="true">
        <PageHeader
          kicker="CREDIT NOTES · PHASE 22"
          title="Credit note & reversal signals"
          subtitle="Summary + register — APIs: /credit-notes/summary · /credit-notes · high-risk · revenue-reversals."
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <StatCard label="Credit notes" value={k.credit_note_count} testId="credit-notes-kpi-count" />
          <StatCard label="Open" value={k.open_credit_notes} testId="credit-notes-kpi-open" />
          <StatCard label="Unapproved" value={k.unapproved_credit_notes} testId="credit-notes-kpi-unapproved" />
          <StatCard label="Total amount" value={fmtUSD(k.total_credit_amount)} testId="credit-notes-kpi-total-amount" />
        </div>

        <SectionCard kicker="REGISTER" title="Credit notes (scoped)">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[58vh]" testId="credit-notes-table">
            <DataTableHead>
              <tr>
                <DataTableTh>#</DataTableTh>
                <DataTableTh>Invoice</DataTableTh>
                <DataTableTh>Entity</DataTableTh>
                <DataTableTh align="right">Amount</DataTableTh>
                <DataTableTh>Status</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {d.items.length === 0 ? (
                <tr>
                  <td colSpan={5} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                    No credit notes in scope.
                  </td>
                </tr>
              ) : null}
              {d.items.map((cn) => (
                <DataTableRow key={cn.id} testId={`credit-notes-cn-${cn.id}`} onClick={() => drillToTarget(drillTargetCreditNoteRow(cn))}>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{cn.credit_note_number || cn.id}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{cn.invoice_number || cn.invoice_id || "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{cn.entity || "—"}</DataTableTd>
                  <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                    {fmtUSD(cn.amount)}
                  </DataTableTd>
                  <DataTableTd className="text-xs text-foreground">{cn.status || "—"}</DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>
      </div>
    </PageShell>
  );
}
