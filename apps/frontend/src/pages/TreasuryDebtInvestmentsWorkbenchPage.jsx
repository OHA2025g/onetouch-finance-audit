import React, { useEffect, useMemo, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { buildDashboardFilterParams } from "../lib/mastersDashboardParams";
import { StatCard } from "../components/StatCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { fmtUSD } from "../lib/format";

function ratePct(rate) {
  const r = Number(rate);
  if (Number.isNaN(r)) return "—";
  return `${(r <= 1 ? r * 100 : r).toFixed(2)}%`;
}

export default function TreasuryDebtInvestmentsWorkbenchPage() {
  const { entityCode, periodYm, periodExplicit, departmentId, costCenterId } = useMastersFilters();
  const [d, setD] = useState(null);

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
    const listParams = { ...params, limit: 35, offset: 0 };
    Promise.all([http.get("/treasury/summary", { params }), http.get("/treasury/debt", { params: listParams })])
      .then(([s, debt]) =>
        setD({
          summary: s.data || {},
          debts: debt.data?.items || [],
        }),
      )
      .catch(() => toast.error("Failed to load treasury debt & investments workbench"));
  }, [params]);

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="treasury-debt-inv-workbench-loading">
        Loading treasury debt & investments workbench…
      </div>
    );
  }

  const p26 = d.summary?.data?.phase26 || {};

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="treasury-debt-inv-workbench-page" data-treasury-phase26-surface="true">
        <PageHeader
          kicker="TREASURY · PHASE 26"
          title="Debt · investments · covenants"
          subtitle="Treasury summary + debt register — APIs: /treasury/summary · /treasury/debt · repayment-schedule · investments · covenants · bank-signatories."
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-8">
          <StatCard label="Debt facilities" value={p26.debt_count} testId="treasury26-kpi-debt-count" />
          <StatCard label="Investments" value={p26.investment_count} testId="treasury26-kpi-investment-count" />
          <StatCard label="Covenant breaches" value={p26.covenant_breaches} testId="treasury26-kpi-covenant-breaches" />
        </div>

        <SectionCard kicker="DEBT REGISTER" title="Facilities (scoped)">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[58vh]" testId="treasury-debt-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Facility</DataTableTh>
                <DataTableTh>Lender</DataTableTh>
                <DataTableTh align="right">Principal</DataTableTh>
                <DataTableTh align="right">Rate</DataTableTh>
                <DataTableTh>Maturity</DataTableTh>
                <DataTableTh>Status</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {d.debts.length === 0 ? (
                <tr>
                  <td colSpan={6} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                    No debt facilities in scope.
                  </td>
                </tr>
              ) : null}
              {d.debts.map((row) => (
                <DataTableRow key={row.id} testId={`treasury-debt-${row.id}`}>
                  <DataTableTd className="text-sm text-foreground">{row.facility_name || row.id}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{row.lender || "—"}</DataTableTd>
                  <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                    {fmtUSD(row.principal_amount)}
                  </DataTableTd>
                  <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                    {ratePct(row.interest_rate)}
                  </DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">
                    {row.maturity_date ? String(row.maturity_date).slice(0, 10) : "—"}
                  </DataTableTd>
                  <DataTableTd className="text-xs text-foreground">{row.status || "—"}</DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>
      </div>
    </PageShell>
  );
}
