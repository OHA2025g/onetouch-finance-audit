import React, { useEffect, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { StatCard } from "../components/StatCard";
import { fmtUSD } from "../lib/format";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";

function safeStr(v) {
  if (v == null) return "";
  return String(v);
}

export default function CashForecast13WeekPage() {
  const { entityCode } = useMastersFilters();
  const dashboardParams = useDashboardFilterParams();
  const [pos, setPos] = useState(null);
  const [fc, setFc] = useState(null);
  const [alerts, setAlerts] = useState({ items: [], count: 0 });
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [forecastFailed, setForecastFailed] = useState(false);
  const [scenarioName, setScenarioName] = useState("");
  const [scenarioNote, setScenarioNote] = useState("");
  const [savingScenario, setSavingScenario] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setLoadError(null);
    setForecastFailed(false);

    Promise.allSettled([
      http.get("/treasury/cash-position", { params: dashboardParams }),
      http.get("/treasury/forecast-13-week", { params: dashboardParams }),
      http.get("/treasury/shortfall-alerts", { params: dashboardParams }),
    ]).then((results) => {
      if (!alive) return;
      const labels = ["Cash position", "13-week forecast", "Shortfall alerts"];
      const failures = [];

      const [r0, r1, r2] = results;
      if (r0.status === "fulfilled") setPos(r0.value.data);
      else {
        setPos(null);
        failures.push(labels[0]);
      }
      if (r1.status === "fulfilled") {
        setFc(r1.value.data);
        setForecastFailed(false);
      } else {
        setFc(null);
        setForecastFailed(true);
        failures.push(labels[1]);
      }
      if (r2.status === "fulfilled") {
        const d = r2.value.data;
        setAlerts({ items: d?.items || [], count: d?.count || 0 });
      } else {
        setAlerts({ items: [], count: 0 });
        failures.push(labels[2]);
      }

      if (failures.length) {
        const msg = `Could not load: ${failures.join(", ")}.`;
        setLoadError(msg);
        toast.error(msg);
      }
      setLoading(false);
    });

    return () => {
      alive = false;
    };
  }, [dashboardParams]);

  const saveScenario = async () => {
    const name = safeStr(scenarioName).trim();
    if (!name) {
      toast.error("Scenario name is required");
      return;
    }
    try {
      setSavingScenario(true);
      await http.post("/treasury/scenario", {
        name,
        entity: dashboardParams.entity_code || entityCode || undefined,
        note: safeStr(scenarioNote).trim() || undefined,
      });
      toast.success("Scenario saved");
      setScenarioName("");
      setScenarioNote("");
    } catch {
      toast.error("Failed to save scenario");
    } finally {
      setSavingScenario(false);
    }
  };

  if (loading) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="cash-forecast-loading">
        Loading cash forecast…
      </div>
    );
  }

  const cashBalance = Number(pos?.cash_balance ?? 0);
  const weeks = fc?.weeks || [];

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="cash-forecast-page">
        <PageHeader
          kicker="CASH FORECAST · PHASE 11"
          title="13-week runway & liquidity watch"
          subtitle="Uses /treasury/cash-position, /treasury/forecast-13-week, /treasury/shortfall-alerts. Forecast is a proxy until the full cash engine is modeled."
        />

        {loadError ? (
          <div
            className="mb-4 rounded-sm border border-[hsl(var(--destructive)/0.35)] bg-[hsl(var(--destructive)/0.06)] px-4 py-3 text-sm text-foreground"
            data-testid="cash-forecast-load-warning"
          >
            {loadError} Partial data may still appear below.
          </div>
        ) : null}

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
          <StatCard
            label="Cash balance"
            value={pos ? fmtUSD(cashBalance) : "—"}
            testId="cf-cash-balance"
          />
          <StatCard label="Weeks" value={forecastFailed ? "—" : weeks.length} testId="cf-weeks" />
          <StatCard label="Shortfall alerts" value={alerts.count} severity={alerts.count ? "critical" : null} testId="cf-alerts" />
          <StatCard label="Entity scope" value={entityCode || "All"} testId="cf-entity" />
          <StatCard label="Source" value={fc?.source || "—"} testId="cf-source" />
          <StatCard label="Assumption" value="Inflow=0" severity="warning" testId="cf-assumption" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <SectionCard kicker="FORECAST" title="13-week schedule">
            {forecastFailed ? (
              <div className="crt-num px-2 py-8 text-center text-sm text-muted-foreground" data-testid="cf-forecast-error">
                Forecast data unavailable. Check treasury APIs and try again.
              </div>
            ) : (
              <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[55vh]" testId="cf-weeks-table">
                <DataTableHead>
                  <tr>
                    <DataTableTh>Week</DataTableTh>
                    <DataTableTh>Start</DataTableTh>
                    <DataTableTh>End</DataTableTh>
                    <DataTableTh align="right">Inflows</DataTableTh>
                    <DataTableTh align="right">Outflows</DataTableTh>
                    <DataTableTh align="right">Ending cash</DataTableTh>
                  </tr>
                </DataTableHead>
                <DataTableBody>
                  {weeks.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                        No forecast weeks returned.
                      </td>
                    </tr>
                  ) : null}
                  {weeks.map((w) => (
                    <DataTableRow key={w.week_index}>
                      <DataTableTd className="crt-num text-xs text-muted-foreground">{w.week_index}</DataTableTd>
                      <DataTableTd className="crt-num text-xs text-muted-foreground">{w.start_date}</DataTableTd>
                      <DataTableTd className="crt-num text-xs text-muted-foreground">{w.end_date}</DataTableTd>
                      <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                        {fmtUSD(w.inflows)}
                      </DataTableTd>
                      <DataTableTd align="right" className="crt-num tabular-nums text-foreground">
                        {fmtUSD(w.outflows)}
                      </DataTableTd>
                      <DataTableTd
                        align="right"
                        className={`crt-num tabular-nums ${Number(w.ending_cash) < 0 ? "text-[hsl(var(--destructive))]" : "text-foreground"}`}
                      >
                        {fmtUSD(w.ending_cash)}
                      </DataTableTd>
                    </DataTableRow>
                  ))}
                </DataTableBody>
              </DataTable>
            )}
          </SectionCard>

          <SectionCard kicker="SCENARIOS" title="Create scenario (placeholder persistence)">
            <div className="space-y-3">
              <div>
                <div className="crt-num mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">Scenario name</div>
                <input
                  value={scenarioName}
                  onChange={(e) => setScenarioName(safeStr(e.target.value))}
                  placeholder="e.g., Delay vendor payments by 2 weeks"
                  className="w-full rounded-sm border border-zinc-200 bg-white px-3 py-2 text-sm text-foreground outline-none dark:border-zinc-800 dark:bg-zinc-950"
                  data-testid="cf-scenario-name"
                />
              </div>
              <div>
                <div className="crt-num mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">Note (optional)</div>
                <input
                  value={scenarioNote}
                  onChange={(e) => setScenarioNote(safeStr(e.target.value))}
                  placeholder="What changed in this scenario?"
                  className="w-full rounded-sm border border-zinc-200 bg-white px-3 py-2 text-sm text-foreground outline-none dark:border-zinc-800 dark:bg-zinc-950"
                  data-testid="cf-scenario-note"
                />
              </div>
              <button
                type="button"
                disabled={savingScenario}
                onClick={saveScenario}
                className="crt-num w-full rounded-sm border border-zinc-200 bg-zinc-50 px-3 py-2 text-[10px] uppercase tracking-wider text-foreground hover:bg-zinc-100 disabled:opacity-60 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:bg-zinc-800"
                data-testid="cf-save-scenario"
              >
                {savingScenario ? "Saving…" : "Save scenario"}
              </button>

              <DividerNote items={alerts.items} />
            </div>
          </SectionCard>
        </div>
      </div>
    </PageShell>
  );
}

function DividerNote({ items }) {
  if (!items || items.length === 0) {
    return <div className="crt-num text-xs text-muted-foreground">No projected shortfalls in the next 13 weeks.</div>;
  }
  return (
    <div className="rounded-sm border border-[hsl(var(--destructive)/0.35)] bg-[hsl(var(--destructive)/0.06)] p-3">
      <div className="crt-num text-[10px] uppercase tracking-wider text-[hsl(var(--destructive))]">Shortfall alerts</div>
      <div className="mt-2 space-y-1 text-sm">
        {items.slice(0, 8).map((a) => (
          <div key={`${a.week_index}-${a.start_date}`} className="flex items-center justify-between gap-3">
            <div className="crt-num text-xs text-muted-foreground">
              Week {a.week_index} · {a.start_date}–{a.end_date}
            </div>
            <div className="crt-num tabular-nums text-[hsl(var(--destructive))]">{fmtUSD(a.ending_cash)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
