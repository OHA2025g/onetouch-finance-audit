import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { buildDashboardFilterParams } from "../lib/mastersDashboardParams";
import { StatCard } from "../components/StatCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { fmtUSD, fmtDate } from "../lib/format";

export default function ReconciliationsWorkbenchPage() {
  const navigate = useNavigate();
  const { entityCode, periodYm, periodExplicit, departmentId, costCenterId, hrefWithMasterParams } = useMastersFilters();
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
    const qp = { ...params, limit: 50, offset: 0 };
    http
      .get("/reconciliations", { params: qp })
      .then((r) => setItems(r.data?.items || []))
      .catch(() => toast.error("Failed to load reconciliations"));
  }, [params]);

  const openRecon = useCallback(
    (rec) => {
      if (!rec?.id) return;
      navigate(hrefWithMasterParams(`/app/reconciliations/${encodeURIComponent(rec.id)}`));
    },
    [hrefWithMasterParams, navigate],
  );

  if (items === null) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="recon-workbench-loading">
        Loading reconciliation suite…
      </div>
    );
  }

  const openCount = items.filter((x) => (x.status || "open").toLowerCase() === "open").length;

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="recon-workbench-page" data-reconciliation-suite-surface="true">
        <PageHeader
          kicker="RECONCILIATIONS · PHASE 17"
          title="Reconciliation management suite"
          subtitle="List & drill-down (row click) — APIs: /reconciliations CRUD · evidence · submit · approve · reopen · create-case."
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <StatCard label="In scope" value={items.length} testId="recon-kpi-total" />
          <StatCard label="Open status" value={openCount} testId="recon-kpi-open" />
        </div>

        <SectionCard kicker="QUEUE" title="Reconciliations">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[62vh]" testId="recon-list-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Type</DataTableTh>
                <DataTableTh>Entity</DataTableTh>
                <DataTableTh>Period</DataTableTh>
                <DataTableTh>Status</DataTableTh>
                <DataTableTh>Due</DataTableTh>
                <DataTableTh align="right">Variance</DataTableTh>
                <DataTableTh />
              </tr>
            </DataTableHead>
            <DataTableBody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={7} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                    No reconciliations in scope.
                  </td>
                </tr>
              ) : null}
              {items.map((rec) => (
                <DataTableRow key={rec.id} testId={`recon-row-${rec.id}`} onClick={() => openRecon(rec)}>
                  <DataTableTd className="text-sm text-foreground">{rec.reconciliation_type || "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{rec.entity || "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{rec.period || "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-xs uppercase text-muted-foreground">{rec.status || "—"}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{fmtDate(rec.due_date)}</DataTableTd>
                  <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                    {fmtUSD(rec.variance_amount)}
                  </DataTableTd>
                  <DataTableTd className="w-[120px]">
                    {rec.id ? (
                      <span className="crt-num text-[10px] uppercase tracking-wider text-primary">Open →</span>
                    ) : (
                      "—"
                    )}
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
