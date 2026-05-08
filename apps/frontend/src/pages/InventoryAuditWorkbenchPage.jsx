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

export default function InventoryAuditWorkbenchPage() {
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
    const veParams = { ...params, limit: 35 };
    Promise.all([
      http.get("/inventory-audit/summary", { params }),
      http.get("/inventory-audit/valuation-exceptions", { params: veParams }),
    ])
      .then(([s, ve]) =>
        setD({
          summary: s.data || {},
          exceptions: ve.data?.items || [],
        }),
      )
      .catch(() => toast.error("Failed to load inventory audit workbench"));
  }, [params]);

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="inventory-audit-workbench-loading">
        Loading inventory audit workbench…
      </div>
    );
  }

  const k = d.summary?.kpis || {};

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="inventory-audit-workbench-page" data-inventory-audit-workbench-surface="true">
        <PageHeader
          kicker="INVENTORY AUDIT · PHASE 23"
          title="Valuation · ageing · slow-moving"
          subtitle="Summary + valuation exceptions — APIs: /inventory-audit/summary · ageing · slow-moving · valuation-exceptions."
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <StatCard label="SKUs tracked" value={k.item_count} testId="inventory-kpi-item-count" />
          <StatCard label="Inventory value" value={fmtUSD(k.inventory_value)} testId="inventory-kpi-value" />
          <StatCard label="Negative stock" value={k.negative_stock_items} testId="inventory-kpi-negative-stock" />
          <StatCard label="NRV vs cost" value={k.nrv_issues} testId="inventory-kpi-nrv-issues" />
        </div>

        <SectionCard kicker="VALUATION EXCEPTIONS" title="NRV & negative-stock flags (scoped)">
          <DataTable
            className="rounded-none border-0 bg-transparent"
            maxHeightClassName="max-h-[58vh]"
            testId="inventory-valuation-exceptions-table"
          >
            <DataTableHead>
              <tr>
                <DataTableTh>SKU</DataTableTh>
                <DataTableTh>Entity</DataTableTh>
                <DataTableTh align="right">Qty</DataTableTh>
                <DataTableTh align="right">Unit cost</DataTableTh>
                <DataTableTh align="right">NRV / u</DataTableTh>
                <DataTableTh>Issue</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {d.exceptions.length === 0 ? (
                <tr>
                  <td colSpan={6} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                    No valuation exceptions in scope.
                  </td>
                </tr>
              ) : null}
              {d.exceptions.map((row) => (
                <DataTableRow key={row.id} testId={`inventory-exc-${row.id}`}>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{row.sku || row.id}</DataTableTd>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{row.entity || "—"}</DataTableTd>
                  <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                    {row.qty_on_hand}
                  </DataTableTd>
                  <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                    {fmtUSD(row.unit_cost)}
                  </DataTableTd>
                  <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                    {fmtUSD(row.nrv_unit)}
                  </DataTableTd>
                  <DataTableTd className="text-xs text-foreground">{row.issue || "—"}</DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>
      </div>
    </PageShell>
  );
}
