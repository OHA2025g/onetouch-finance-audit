import React, { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { StatCard } from "../components/StatCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { fmtUSD, fmtDate } from "../lib/format";

export default function WorkingCapitalPage() {
  const { pathname } = useLocation();
  const isPhase10PayablesRoute = pathname.includes("/working-capital/payables");
  const isPhase9ReceivablesRoute = pathname.includes("/working-capital/receivables");
  const [d, setD] = useState(null);
  const { entityCode, periodExplicit, departmentId, costCenterId } = useMastersFilters();

  const params = useDashboardFilterParams();
  useEffect(() => {
    http
      .get("/dashboard/working-capital", { params })
      .then((r) => setD(r.data))
      .catch(() => toast.error("Failed to load working capital dashboard"));
  }, [params]);

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="working-capital-loading">
        Loading working capital…
      </div>
    );
  }

  const k = d.kpis || {};

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div
        data-testid="working-capital-page"
        {...(isPhase10PayablesRoute ? { "data-ap-payables-surface": "true" } : {})}
        {...(isPhase9ReceivablesRoute && !isPhase10PayablesRoute ? { "data-ar-receivables-surface": "true" } : {})}
      >
        <PageHeader
          kicker={
            isPhase10PayablesRoute ? "PAYABLES · PHASE 10" : isPhase9ReceivablesRoute ? "RECEIVABLES · PHASE 9" : "WORKING CAPITAL"
          }
          title={
            isPhase10PayablesRoute
              ? "AP ageing & payment-run context"
              : isPhase9ReceivablesRoute
                ? "AR ageing & collections context"
                : "Cash conversion view"
          }
          subtitle={
            isPhase10PayablesRoute
              ? "Payables deep-link alias — APIs: /working-capital/ap-ageing · /ap/* (Phase 10 payables contracts)."
              : isPhase9ReceivablesRoute
                ? "Receivables deep-link alias — APIs: /working-capital/ar-ageing · /ar/* (Phase 9 AR contracts)."
                : "AR/AP ageing, overdue exposure, and close-impacting exceptions (Slice 5)."
          }
        />

        <MastersFilterStrip className="mb-6" />
        {(entityCode || periodExplicit || departmentId || costCenterId) && (
          <p className="crt-num mb-4 text-[10px] uppercase tracking-wider text-muted-foreground">
            AR/AP are scoped by entity + period when provided; department/cost center currently scope exception-derived metrics only.
          </p>
        )}

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
          <StatCard label="AR open" value={fmtUSD(k.ar_open_amount)} testId="kpi-ar-open" />
          <StatCard label="AR overdue" value={fmtUSD(k.ar_overdue_amount)} severity="warning" testId="kpi-ar-overdue" />
          <StatCard label="AR overdue count" value={k.ar_overdue_count} testId="kpi-ar-overdue-count" />
          <StatCard label="AP open" value={fmtUSD(k.ap_open_amount)} testId="kpi-ap-open" />
          <StatCard label="AP overdue" value={fmtUSD(k.ap_overdue_amount)} severity="warning" testId="kpi-ap-overdue" />
          <StatCard label="WC exceptions open" value={k.wc_exception_open} severity="critical" testId="kpi-wc-exc" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <SectionCard kicker="ACCOUNTS RECEIVABLE" title="Top overdue AR">
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[55vh]" testId="wc-ar-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>Customer</DataTableTh>
                  <DataTableTh>Invoice</DataTableTh>
                  <DataTableTh>Due</DataTableTh>
                  <DataTableTh align="right">Amount</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {(d.top_overdue_ar || []).length === 0 ? (
                  <tr>
                    <td colSpan={4} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                      No overdue AR matches the current scope.
                    </td>
                  </tr>
                ) : null}
                {(d.top_overdue_ar || []).map((r) => (
                  <DataTableRow key={r.id} testId={`ar-${r.id}`}>
                    <DataTableTd className="text-sm text-foreground">{r.customer_name || r.customer_id || "—"}</DataTableTd>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{r.invoice_number || r.id}</DataTableTd>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{fmtDate(r.due_date)}</DataTableTd>
                    <DataTableTd align="right" className="crt-num tabular-nums text-[hsl(var(--destructive))]">
                      {fmtUSD(r.amount)}
                    </DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          </SectionCard>

          <SectionCard kicker="ACCOUNTS PAYABLE" title="Top overdue AP">
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[55vh]" testId="wc-ap-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>Vendor</DataTableTh>
                  <DataTableTh>Invoice</DataTableTh>
                  <DataTableTh>Due</DataTableTh>
                  <DataTableTh align="right">Amount</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {(d.top_overdue_ap || []).length === 0 ? (
                  <tr>
                    <td colSpan={4} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                      No overdue AP matches the current scope.
                    </td>
                  </tr>
                ) : null}
                {(d.top_overdue_ap || []).map((r) => (
                  <DataTableRow key={r.id} testId={`ap-${r.id}`}>
                    <DataTableTd className="text-sm text-foreground">{r.vendor_name || r.vendor_id || "—"}</DataTableTd>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{r.invoice_number || r.id}</DataTableTd>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{fmtDate(r.due_date)}</DataTableTd>
                    <DataTableTd align="right" className="crt-num tabular-nums text-[hsl(var(--destructive))]">
                      {fmtUSD(r.amount)}
                    </DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          </SectionCard>
        </div>
      </div>
    </PageShell>
  );
}

