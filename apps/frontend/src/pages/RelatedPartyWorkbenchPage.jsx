import React, { useEffect, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { StatCard } from "../components/StatCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { fmtUSD } from "../lib/format";

export default function RelatedPartyWorkbenchPage() {
  const [d, setD] = useState(null);

  const params = useDashboardFilterParams();
  useEffect(() => {
    const listParams = { ...params, limit: 35, offset: 0 };
    Promise.all([
      http.get("/rpt/audit-committee-report", { params }),
      http.get("/rpt/transactions", { params: listParams }),
    ])
      .then(([rep, tx]) =>
        setD({
          report: rep.data || {},
          transactions: tx.data?.items || [],
        }),
      )
      .catch(() => toast.error("Failed to load related party transactions workbench"));
  }, [params]);

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="rpt-workbench-loading">
        Loading RPT workbench…
      </div>
    );
  }

  const h = d.report.headline || {};

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="rpt-workbench-page" data-rpt-phase28-surface="true">
        <PageHeader
          kicker="RELATED PARTY TRANSACTIONS · PHASE 28"
          title="Master · approvals · disclosures"
          subtitle="Committee headline + transaction register — APIs: /rpt/related-parties · /rpt/transactions · outstanding-balances · disclosure-checklist."
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <StatCard label="Related parties" value={h.related_parties} testId="rpt28-kpi-parties" />
          <StatCard label="Transactions" value={h.transaction_count} testId="rpt28-kpi-transactions" />
          <StatCard label="Pending approval" value={h.pending_approvals} testId="rpt28-kpi-pending" />
          <StatCard label="Total amount" value={fmtUSD(h.transaction_total_amount)} testId="rpt28-kpi-total-amount" />
        </div>

        <SectionCard kicker="REGISTER" title="Related party transactions (scoped)">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[58vh]" testId="rpt-transactions-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Party</DataTableTh>
                <DataTableTh>Type</DataTableTh>
                <DataTableTh>Direction</DataTableTh>
                <DataTableTh align="right">Amount</DataTableTh>
                <DataTableTh>Approval</DataTableTh>
                <DataTableTh>Settlement</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {d.transactions.length === 0 ? (
                <tr>
                  <td colSpan={6} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                    No transactions in scope.
                  </td>
                </tr>
              ) : null}
              {d.transactions.map((row) => (
                <DataTableRow key={row.id} testId={`rpt-tx-${row.id}`}>
                  <DataTableTd className="text-sm text-foreground">{row.related_party_name || row.related_party_id || "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{row.transaction_type || "—"}</DataTableTd>
                  <DataTableTd className="text-xs text-foreground">{row.direction || "—"}</DataTableTd>
                  <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                    {fmtUSD(row.amount)}
                  </DataTableTd>
                  <DataTableTd className="text-xs text-foreground">{row.approval_status || "—"}</DataTableTd>
                  <DataTableTd className="text-xs text-foreground">{row.settlement_status || "—"}</DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>
      </div>
    </PageShell>
  );
}
