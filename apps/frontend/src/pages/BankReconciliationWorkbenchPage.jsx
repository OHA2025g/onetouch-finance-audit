import React, { useEffect, useMemo, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { buildDashboardFilterParams } from "../lib/mastersDashboardParams";
import { StatCard } from "../components/StatCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";

export default function BankReconciliationWorkbenchPage() {
  const { entityCode, periodYm, periodExplicit, departmentId, costCenterId } = useMastersFilters();
  const [items, setItems] = useState(null);

  const params = useMemo(
    () =>
      buildDashboardFilterParams({
        entityCode,
        periodYm,
        periodExplicit,
        departmentId,
        costCenterId,
      }),
    [entityCode, periodYm, periodExplicit, departmentId, costCenterId],
  );

  useEffect(() => {
    const qp = { entity_code: params.entity_code, limit: 50 };
    http
      .get("/bank-recon/statements", { params: qp })
      .then((r) => setItems(r.data?.items || []))
      .catch(() => toast.error("Failed to load bank statements"));
  }, [params.entity_code]);

  if (items === null) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="bank-recon-loading">
        Loading bank reconciliation…
      </div>
    );
  }

  const notSignedOff = items.filter((s) => String(s.status || "").toLowerCase() !== "signed_off").length;

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="bank-recon-workbench-page" data-bank-recon-surface="true">
        <PageHeader
          kicker="BANK RECON · PHASE 18"
          title="Bank reconciliation automation"
          subtitle="Uploaded statements · auto-match · unmatched · classify · sign-off — /bank-recon/* APIs."
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <StatCard label="Statements" value={items.length} testId="br-kpi-statements" />
          <StatCard label="Not signed off" value={notSignedOff} testId="br-kpi-pending-signoff" />
        </div>

        <SectionCard kicker="STATEMENTS" title="Bank statement uploads">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[62vh]" testId="br-statements-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Statement</DataTableTh>
                <DataTableTh>Account</DataTableTh>
                <DataTableTh>Period</DataTableTh>
                <DataTableTh>Entity</DataTableTh>
                <DataTableTh>Status</DataTableTh>
                <DataTableTh align="right">Matched</DataTableTh>
                <DataTableTh align="right">Unmatched</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                    No bank statements in scope.
                  </td>
                </tr>
              ) : null}
              {items.map((st) => (
                <DataTableRow key={st.id} testId={`br-row-${st.id}`}>
                  <DataTableTd className="crt-num text-xs font-mono text-muted-foreground">{st.id}</DataTableTd>
                  <DataTableTd className="text-sm text-foreground">{st.bank_account_id || "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{st.statement_period || "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{st.entity || "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-xs uppercase text-muted-foreground">{st.status || "—"}</DataTableTd>
                  <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                    {st.matched_count ?? "—"}
                  </DataTableTd>
                  <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                    {st.unmatched_count ?? "—"}
                  </DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>
      </div>
    </PageShell>
  );
}
