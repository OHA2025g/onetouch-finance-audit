import React, { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { StatCard } from "../components/StatCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { fmtUSD, fmtDate } from "../lib/format";

export default function FpaPage() {
  const { pathname } = useLocation();
  const isPhase12BudgetMasterRoute = pathname.includes("/finance-operations/budget-master");
  const isPhase13BudgetVsActualRoute = pathname.includes("/finance-operations/budget-vs-actual-dashboard");
  const isPhase14ForecastAccuracyRoute = pathname.includes("/finance-operations/forecast-accuracy-dashboard");
  const [d, setD] = useState(null);

  const params = useDashboardFilterParams();
  useEffect(() => {
    http
      .get("/dashboard/fpa", { params })
      .then((r) => setD(r.data))
      .catch(() => toast.error("Failed to load FP&A dashboard"));
  }, [params]);

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="fpa-loading">
        Loading FP&A…
      </div>
    );
  }

  const k = d.kpis || {};

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div
        data-testid="fpa-page"
        {...(isPhase12BudgetMasterRoute ? { "data-budget-master-surface": "true" } : {})}
        {...(isPhase13BudgetVsActualRoute ? { "data-budget-vs-actual-surface": "true" } : {})}
        {...(isPhase14ForecastAccuracyRoute ? { "data-forecast-accuracy-surface": "true" } : {})}
      >
        <PageHeader
          kicker={
            isPhase12BudgetMasterRoute
              ? "BUDGET MASTER · PHASE 12"
              : isPhase13BudgetVsActualRoute
                ? "BUDGET VS ACTUAL · PHASE 13"
                : isPhase14ForecastAccuracyRoute
                  ? "FORECAST ACCURACY · PHASE 14"
                  : "FINANCE OPERATIONS"
          }
          title={
            isPhase12BudgetMasterRoute
              ? "Budget master & variance context"
              : isPhase13BudgetVsActualRoute
                ? "Variance lines & explanation gates"
                : isPhase14ForecastAccuracyRoute
                  ? "Forecast vs actual & accuracy signals"
                  : "FP&A snapshot"
          }
          subtitle={
            isPhase12BudgetMasterRoute
              ? "Budget deep-link — FP&A snapshot + APIs: /budget upload, list, approve, lock/unlock."
              : isPhase13BudgetVsActualRoute
                ? "BvA deep-link — FP&A snapshot + APIs: /budget/budget-vs-actual · /budget/variance (comment, approve explanation)."
                : isPhase14ForecastAccuracyRoute
                  ? "Forecast deep-link — FP&A snapshot + APIs: /forecast upload · /forecast/vs-actual · /forecast/accuracy."
                  : "Budget vs actual (CapEx portfolio) + spend proxy (journals) — Slice 7."
          }
        />

        <MastersFilterStrip className="mb-6" />
        <p className="crt-num mb-4 text-[10px] uppercase tracking-wider text-muted-foreground">{d.note}</p>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
          <StatCard label="CapEx budget" value={fmtUSD(k.capex_total_budget)} testId="kpi-capex-budget" />
          <StatCard label="CapEx actual" value={fmtUSD(k.capex_total_actual)} testId="kpi-capex-actual" />
          <StatCard label="CapEx variance" value={fmtUSD(k.capex_total_variance)} severity="warning" testId="kpi-capex-var" />
          <StatCard label="Over-budget projects" value={k.capex_over_budget_count} severity="critical" testId="kpi-capex-over" />
          <StatCard label="Journal spend" value={fmtUSD(k.journal_spend_total)} testId="kpi-je-total" />
          <StatCard label="Manual JE spend" value={fmtUSD(k.manual_journal_total)} severity="warning" testId="kpi-manual-je" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <SectionCard kicker="CAPEX" title="Top over-budget projects">
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[55vh]" testId="fpa-capex-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>Project</DataTableTh>
                  <DataTableTh>Entity</DataTableTh>
                  <DataTableTh align="right">Budget</DataTableTh>
                  <DataTableTh align="right">Actual</DataTableTh>
                  <DataTableTh align="right">Variance</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {(d.top_over_budget_projects || []).length === 0 ? (
                  <tr>
                    <td colSpan={5} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                      No over-budget projects in scope.
                    </td>
                  </tr>
                ) : null}
                {(d.top_over_budget_projects || []).map((p) => {
                  const budget = Number(p.budget_amount || 0);
                  const actual = Number(p.actual_amount || 0);
                  const variance = actual - budget;
                  return (
                    <DataTableRow key={p.id} testId={`capex-${p.id}`}>
                      <DataTableTd className="text-sm text-foreground">{p.project_name || p.project_code || p.id}</DataTableTd>
                      <DataTableTd className="crt-num text-xs text-muted-foreground">{p.entity || "—"}</DataTableTd>
                      <DataTableTd align="right" className="crt-num tabular-nums text-muted-foreground">
                        {fmtUSD(budget)}
                      </DataTableTd>
                      <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                        {fmtUSD(actual)}
                      </DataTableTd>
                      <DataTableTd align="right" className="crt-num tabular-nums text-[hsl(var(--destructive))]">
                        {fmtUSD(variance)}
                      </DataTableTd>
                    </DataTableRow>
                  );
                })}
              </DataTableBody>
            </DataTable>
          </SectionCard>

          <SectionCard kicker="SPEND" title="Recent journal entries (proxy)">
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[55vh]" testId="fpa-je-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>JE</DataTableTh>
                  <DataTableTh>Entity</DataTableTh>
                  <DataTableTh>Date</DataTableTh>
                  <DataTableTh align="right">Amount</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {(d.recent_journals || []).length === 0 ? (
                  <tr>
                    <td colSpan={4} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                      No journals in scope.
                    </td>
                  </tr>
                ) : null}
                {(d.recent_journals || []).slice(0, 40).map((j) => (
                  <DataTableRow key={j.id} testId={`je-${j.id}`}>
                    <DataTableTd className="text-sm text-foreground">{j.journal_number || j.id}</DataTableTd>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{j.entity || "—"}</DataTableTd>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{fmtDate(j.posting_date)}</DataTableTd>
                    <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                      {fmtUSD(j.total_amount)}
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

