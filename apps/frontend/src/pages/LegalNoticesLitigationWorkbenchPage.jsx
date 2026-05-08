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

export default function LegalNoticesLitigationWorkbenchPage() {
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
    Promise.all([http.get("/legal/exposure-report", { params }), http.get("/legal/notices", { params: listParams })])
      .then(([ex, n]) =>
        setD({
          exposure: ex.data || {},
          notices: n.data?.items || [],
        }),
      )
      .catch(() => toast.error("Failed to load legal notices & litigation workbench"));
  }, [params]);

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="legal-workbench-loading">
        Loading legal notices & litigation workbench…
      </div>
    );
  }

  const h = d.exposure.headline || {};

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="legal-workbench-page" data-legal-phase29-surface="true">
        <PageHeader
          kicker="LEGAL · PHASE 29"
          title="Notices · litigation · exposure"
          subtitle="Exposure headline + notice register — APIs: /legal/notices · litigations · hearings · exposure-report."
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <StatCard label="Notices" value={h.notice_count} testId="legal29-kpi-notice-count" />
          <StatCard label="Litigations" value={h.litigation_count} testId="legal29-kpi-litigation-count" />
          <StatCard label="Overdue notices" value={h.overdue_notices} testId="legal29-kpi-overdue-notices" />
          <StatCard label="High-risk cases" value={h.high_risk_litigations} testId="legal29-kpi-high-risk-lit" />
        </div>

        <SectionCard kicker="NOTICES" title="Regulatory & tax notices (scoped)">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[58vh]" testId="legal-notices-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Type</DataTableTh>
                <DataTableTh>Authority</DataTableTh>
                <DataTableTh>Entity</DataTableTh>
                <DataTableTh align="right">Disputed</DataTableTh>
                <DataTableTh>Due</DataTableTh>
                <DataTableTh>Status</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {d.notices.length === 0 ? (
                <tr>
                  <td colSpan={6} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                    No notices in scope.
                  </td>
                </tr>
              ) : null}
              {d.notices.map((row) => (
                <DataTableRow key={row.id} testId={`legal-ntc-${row.id}`}>
                  <DataTableTd className="text-sm text-foreground">{row.notice_type || row.id}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{row.authority || "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{row.entity || "—"}</DataTableTd>
                  <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                    {fmtUSD(row.disputed_amount)}
                  </DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">
                    {row.response_due_date ? String(row.response_due_date).slice(0, 10) : "—"}
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
