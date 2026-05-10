import React, { useCallback, useEffect, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { StatCard } from "../components/StatCard";
import { fmtUSD } from "../lib/format";
import { errorMessageFromAxios } from "../lib/apiErrorMessage";

function safeStr(v) {
  if (v == null) return "";
  return String(v);
}

function validateForecastDraft({ name, glAccount, amount, periodExplicit, periodYm }) {
  if (!safeStr(name).trim()) return "Forecast name is required.";
  if (!safeStr(glAccount).trim()) return "GL account is required for the line item.";
  const amt = Number(amount);
  if (!Number.isFinite(amt)) return "Amount must be a valid number.";
  if (periodExplicit) {
    const p = safeStr(periodYm).trim();
    if (!p || !/^\d{4}-\d{2}$/.test(p)) return "Select a valid period (YYYY-MM) in the master filter when period scope is explicit.";
  }
  return null;
}

export default function ForecastAccuracyPage() {
  const { entityCode, periodYm, periodExplicit } = useMastersFilters();
  const dashboardParams = useDashboardFilterParams();
  const [versions, setVersions] = useState({ items: [], count: 0 });
  const [accuracy, setAccuracy] = useState(null);
  const [vsActual, setVsActual] = useState({ items: [], count: 0 });
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("Forecast v1");
  const [glAccount, setGlAccount] = useState("4100");
  const [amount, setAmount] = useState("200000");

  const refresh = useCallback(() => {
    http
      .get("/forecast", { params: dashboardParams })
      .then((r) => setVersions({ items: r.data?.items || [], count: r.data?.count || 0 }))
      .catch((e) => toast.error(errorMessageFromAxios(e, "Failed to load forecasts")));

    http
      .get("/forecast/accuracy", { params: dashboardParams })
      .then((r) => setAccuracy(r.data))
      .catch((e) => toast.error(errorMessageFromAxios(e, "Failed to load forecast accuracy")));

    http
      .get("/forecast/vs-actual", { params: dashboardParams })
      .then((r) => setVsActual({ items: r.data?.items || [], count: r.data?.count || 0 }))
      .catch((e) => toast.error(errorMessageFromAxios(e, "Failed to load forecast vs actual")));
  }, [dashboardParams]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const createDraft = async () => {
    const v = validateForecastDraft({ name, glAccount, amount, periodExplicit, periodYm });
    if (v) {
      toast.error(v);
      return;
    }
    try {
      setCreating(true);
      const lines = [
        {
          period_ym: periodExplicit ? periodYm : undefined,
          gl_account: safeStr(glAccount).trim() || undefined,
          amount: Number(amount),
        },
      ];
      await http.post("/forecast/upload", {
        name: safeStr(name).trim() || "Forecast",
        entity: dashboardParams.entity_code || entityCode || undefined,
        status: "draft",
        lines,
      });
      toast.success("Forecast draft created");
      refresh();
    } catch (e) {
      toast.error(errorMessageFromAxios(e, "Failed to upload forecast"));
    } finally {
      setCreating(false);
    }
  };

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="forecast-accuracy-page">
        <PageHeader
          kicker="FORECAST ACCURACY · PHASE 14"
          title="Forecast vs actual, MAPE & bias"
          subtitle="Backed by /forecast upload/list + /forecast/vs-actual + /forecast/accuracy APIs."
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
          <StatCard label="Forecast versions" value={versions.count} testId="fc-versions" />
          <StatCard label="Rows compared" value={vsActual.items.length} testId="fc-rows" />
          <StatCard label="MAPE %" value={accuracy?.mape_pct ?? "—"} severity="warning" testId="fc-mape" />
          <StatCard label="Bias" value={fmtUSD(accuracy?.bias_amount ?? 0)} testId="fc-bias" />
          <StatCard label="Entity scope" value={entityCode || "All"} testId="fc-entity" />
          <StatCard label="Period" value={periodExplicit ? periodYm : "All"} testId="fc-period" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <SectionCard kicker="UPLOAD" title="Create forecast draft (JSON payload)">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <div className="crt-num mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">Name</div>
                <input
                  value={name}
                  onChange={(e) => setName(safeStr(e.target.value))}
                  className="w-full rounded-sm border border-zinc-200 bg-white px-3 py-2 text-sm text-foreground outline-none dark:border-zinc-800 dark:bg-zinc-950"
                />
              </div>
              <div>
                <div className="crt-num mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">GL account</div>
                <input
                  value={glAccount}
                  onChange={(e) => setGlAccount(safeStr(e.target.value))}
                  className="w-full rounded-sm border border-zinc-200 bg-white px-3 py-2 text-sm text-foreground outline-none dark:border-zinc-800 dark:bg-zinc-950"
                />
              </div>
              <div>
                <div className="crt-num mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">Amount</div>
                <input
                  value={amount}
                  onChange={(e) => setAmount(safeStr(e.target.value))}
                  className="w-full rounded-sm border border-zinc-200 bg-white px-3 py-2 text-sm text-foreground outline-none dark:border-zinc-800 dark:bg-zinc-950"
                />
              </div>
              <div className="flex items-end">
                <button
                  type="button"
                  disabled={creating}
                  onClick={createDraft}
                  className="crt-num w-full rounded-sm border border-zinc-200 bg-zinc-50 px-3 py-2 text-[10px] uppercase tracking-wider text-foreground hover:bg-zinc-100 disabled:opacity-60 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:bg-zinc-800"
                  data-testid="fc-create"
                >
                  {creating ? "Uploading…" : "Upload draft"}
                </button>
              </div>
            </div>
          </SectionCard>

          <SectionCard kicker="VERSIONS" title="Forecast versions (latest first)">
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[55vh]" testId="fc-versions-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>ID</DataTableTh>
                  <DataTableTh>Status</DataTableTh>
                  <DataTableTh>Entity</DataTableTh>
                  <DataTableTh align="right">Lines</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {versions.items.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                      No forecasts in scope.
                    </td>
                  </tr>
                ) : null}
                {versions.items.map((v) => (
                  <DataTableRow key={v.id}>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{v.id}</DataTableTd>
                    <DataTableTd className="text-sm text-foreground">{v.status || "—"}</DataTableTd>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{v.entity || "—"}</DataTableTd>
                    <DataTableTd align="right" className="crt-num tabular-nums text-muted-foreground">
                      {(v.lines || []).length}
                    </DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          </SectionCard>
        </div>

        <div className="mt-4">
          <SectionCard kicker="ACCURACY" title="Forecast vs actual (proxy)">
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[70vh]" testId="fc-vs-actual-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>Period</DataTableTh>
                  <DataTableTh>GL</DataTableTh>
                  <DataTableTh align="right">Forecast</DataTableTh>
                  <DataTableTh align="right">Actual</DataTableTh>
                  <DataTableTh align="right">Variance</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {vsActual.items.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                      No comparison rows in scope.
                    </td>
                  </tr>
                ) : null}
                {vsActual.items.slice(0, 200).map((r, idx) => (
                  <DataTableRow key={`${r.period_ym}-${r.gl_account}-${idx}`}>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{r.period_ym || "—"}</DataTableTd>
                    <DataTableTd className="text-sm text-foreground">{r.gl_account || "—"}</DataTableTd>
                    <DataTableTd align="right" className="crt-num tabular-nums text-muted-foreground">
                      {fmtUSD(r.forecast_amount)}
                    </DataTableTd>
                    <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                      {fmtUSD(r.actual_amount)}
                    </DataTableTd>
                    <DataTableTd
                      align="right"
                      className={`crt-num tabular-nums ${Number(r.variance) > 0 ? "text-[hsl(var(--destructive))]" : "text-foreground"}`}
                    >
                      {fmtUSD(r.variance)}
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

