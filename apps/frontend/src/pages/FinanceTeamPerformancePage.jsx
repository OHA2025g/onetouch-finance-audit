import React, { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { StatCard } from "../components/StatCard";
import { RC_TICK, rcTooltipStyle } from "../lib/rechartsTheme";

function shortLabel(s, max = 14) {
  if (!s || typeof s !== "string") return "—";
  return s.length > max ? `${s.slice(0, max - 1)}…` : s;
}

function pairsToChartData(pairs, keyName = "name") {
  if (!Array.isArray(pairs)) return [];
  return pairs.map(([name, count]) => ({
    [keyName]: shortLabel(String(name || "—")),
    fullName: String(name || "—"),
    count: Number(count) || 0,
  }));
}

const COCKPIT_KPI_ROWS = [
  {
    key: "audit_readiness_pct",
    label: "Audit readiness",
    unit: "%",
    fmt: (v) => (v == null ? "—" : Number(v).toFixed(1)),
  },
  {
    key: "evidence_completeness_pct",
    label: "Evidence completeness",
    unit: "%",
    fmt: (v) => (v == null ? "—" : Number(v).toFixed(1)),
  },
  {
    key: "remediation_sla_pct",
    label: "Remediation SLA (cases)",
    unit: "%",
    fmt: (v) => (v == null ? "—" : Number(v).toFixed(1)),
  },
  {
    key: "repeat_finding_rate_pct",
    label: "Repeat finding rate",
    unit: "%",
    fmt: (v) => (v == null ? "—" : Number(v).toFixed(1)),
    severity: "warning",
  },
  {
    key: "open_cases",
    label: "Open cases",
    fmt: (v) => (v == null ? "—" : String(v)),
  },
  {
    key: "high_critical_open_cases",
    label: "High / critical open cases",
    fmt: (v) => (v == null ? "—" : String(v)),
    severity: "warning",
  },
  {
    key: "total_cases",
    label: "Total cases (open + closed)",
    fmt: (v) => (v == null ? "—" : String(v)),
  },
  {
    key: "unresolved_high_risk_exposure",
    label: "High-risk exposure (open)",
    fmt: (v) => (v == null ? "—" : Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })),
    severity: "critical",
  },
];

export default function FinanceTeamPerformancePage() {
  const params = useDashboardFilterParams();
  const { hrefWithMasterParams } = useMastersFilters();
  const [summary, setSummary] = useState(null);
  const [extras, setExtras] = useState({
    slaTrend: null,
    workload: null,
    sla: null,
    rework: null,
    bottlenecks: null,
    scorecards: null,
  });
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [extrasLoading, setExtrasLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setSummary(null);
    setExtras({ slaTrend: null, workload: null, sla: null, rework: null, bottlenecks: null, scorecards: null });
    setSummaryLoading(true);
    setExtrasLoading(true);

    http
      .get("/finance-team/summary", { params })
      .then((r) => {
        if (alive) setSummary(r.data);
      })
      .catch(() => {
        toast.error("Failed to load finance team dashboard");
      })
      .finally(() => {
        if (alive) setSummaryLoading(false);
      });

    const extraPaths = ["sla-trend", "workload", "sla", "rework", "bottlenecks", "scorecards"];
    Promise.all(
      extraPaths.map((p) =>
        http.get(`/finance-team/${p}`, { params }).then((r) => r.data).catch(() => null)
      )
    )
      .then(([slaTrend, workload, sla, rework, bottlenecks, scorecards]) => {
        if (!alive) return;
        setExtras({ slaTrend, workload, sla, rework, bottlenecks, scorecards });
      })
      .finally(() => {
        if (alive) setExtrasLoading(false);
      });

    return () => {
      alive = false;
    };
  }, [params]);

  const d = summary;
  const ck = d?.cockpit_kpis || {};
  const ctrl = (d?.controller || {}).kpis || {};

  const workloadTableRows = useMemo(() => {
    const by = extras.workload?.by_owner;
    if (!by || typeof by !== "object") return [];
    const crit = extras.workload?.critical_by_owner || {};
    return Object.entries(by)
      .map(([owner, pending]) => ({
        owner: String(owner || "—"),
        pending: Number(pending) || 0,
        critical: Number(crit[owner]) || 0,
      }))
      .sort((a, b) => b.pending - a.pending || a.owner.localeCompare(b.owner));
  }, [extras.workload]);

  const slaTrendChartData = useMemo(() => {
    const s = extras.slaTrend?.series;
    if (!Array.isArray(s)) return [];
    return s.map((row) => ({
      ...row,
      label: row.period_ym || row.cycle_id || "—",
    }));
  }, [extras.slaTrend]);

  const workloadChart = useMemo(
    () => pairsToChartData(extras.workload?.top, "owner"),
    [extras.workload]
  );

  const bottleneckChart = useMemo(
    () => pairsToChartData(extras.bottlenecks?.top, "owner"),
    [extras.bottlenecks]
  );

  const cycles = Array.isArray(d?.cycles?.items) ? d.cycles.items : [];

  const placeholder = summaryLoading || !d;

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="finance-team-page">
        <PageHeader
          kicker="FINANCE OPERATIONS"
          title="Finance team performance"
          subtitle="Close cycles, controller signals, CFO cockpit KPIs, workload (chart + full owner table), SLA trend by close period, bottlenecks, and scorecards (Phase 7 BFF)."
        />
        <MastersFilterStrip className="mb-6" />

        {summaryLoading && (
          <p className="crt-overline mb-4 text-muted-foreground" data-testid="finance-team-loading">
            Loading finance team view…
          </p>
        )}

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <StatCard
            label="Close cycles"
            value={placeholder ? "—" : d.cycles?.count ?? 0}
            testId="ft-cycles"
          />
          <StatCard
            label="Open close tasks"
            value={placeholder ? "—" : d.close_tasks_open}
            testId="ft-tasks"
          />
          <StatCard
            label="Action queue (total)"
            value={placeholder ? "—" : d.action_queue_total}
            testId="ft-aq"
          />
          <StatCard
            label="Audit readiness %"
            value={placeholder ? "—" : ck.audit_readiness_pct}
            testId="ft-readiness"
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
          {COCKPIT_KPI_ROWS.filter((row) => row.key !== "audit_readiness_pct").map((row) => (
            <StatCard
              key={row.key}
              label={row.label}
              value={placeholder ? "—" : row.fmt(ck[row.key])}
              unit={row.unit}
              severity={row.severity}
              testId={`ft-ck-${row.key}`}
            />
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-8">
          <StatCard
            label="Close blockers (exceptions)"
            value={placeholder ? "—" : ctrl.close_blockers}
            severity="warning"
          />
          <StatCard label="AP exceptions" value={placeholder ? "—" : ctrl.ap_exception_count} />
          <StatCard
            label="Reconciliations overdue"
            value={placeholder ? "—" : ctrl.reconciliations_overdue}
            severity="critical"
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-8">
          <StatCard
            label="Close tasks approved % (proxy)"
            value={extrasLoading || extras.sla == null ? "—" : extras.sla.approved_pct}
            unit="%"
            subtle={extras.sla?.total_tasks != null ? `${extras.sla.total_tasks} tasks in scope` : undefined}
            testId="ft-sla-pct"
          />
          <StatCard
            label="Rework — reopened % (proxy)"
            value={extrasLoading || extras.rework == null ? "—" : extras.rework.reopened_pct}
            unit="%"
            subtle={
              extras.rework?.reopened_tasks != null
                ? `${extras.rework.reopened_tasks} reopened / ${extras.rework.total_tasks} total`
                : undefined
            }
            testId="ft-rework-pct"
          />
          <StatCard
            label="Bottleneck cycle — pending tasks"
            value={extrasLoading || extras.bottlenecks == null ? "—" : extras.bottlenecks.pending}
            subtle={
              extras.bottlenecks?.cycle_id
                ? `Cycle ${extras.bottlenecks.cycle_id}`
                : extras.bottlenecks?.note || undefined
            }
            testId="ft-bottleneck-pending"
          />
        </div>

        {!placeholder && cycles.length === 0 && (
          <SectionCard kicker="CLOSE" title="Close cycles" className="mb-8">
            <p className="text-sm text-muted-foreground">No close cycles for the selected entity / filters.</p>
          </SectionCard>
        )}

        {!placeholder && cycles.length > 0 && (
          <SectionCard kicker="CLOSE" title="Close cycles" className="mb-8">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {cycles.map((c) => (
                <div
                  key={c.id}
                  className="rounded-lg border border-border bg-card/50 p-4 flex flex-col gap-2"
                  data-testid={`ft-cycle-card-${c.id}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="text-sm font-medium text-foreground">{c.name || c.period_ym}</div>
                      <div className="crt-num text-xs text-muted-foreground">{c.period_ym}</div>
                    </div>
                    <span
                      className={clsx(
                        "text-[10px] uppercase tracking-wide px-2 py-0.5 rounded shrink-0",
                        c.status === "open"
                          ? "bg-amber-500/15 text-amber-700 dark:text-amber-400"
                          : "bg-muted text-muted-foreground"
                      )}
                    >
                      {c.status || "—"}
                    </span>
                  </div>
                  {c.entity_code && (
                    <div className="crt-num text-[11px] text-muted-foreground">Entity {c.entity_code}</div>
                  )}
                  <Link
                    className="text-primary text-sm hover:underline mt-auto"
                    to={hrefWithMasterParams(`/app/finance-operations/month-end-close/${encodeURIComponent(c.id)}`)}
                  >
                    Open in month-end close →
                  </Link>
                </div>
              ))}
            </div>
          </SectionCard>
        )}

        <SectionCard
          kicker="SLA TREND"
          title="Close-task approved % by close period"
          subtitle="One point per close cycle (newest window); complements the aggregate SLA tile."
          className="mb-8"
          data-testid="ft-sla-trend-section"
        >
          {extrasLoading || !extras.slaTrend ? (
            <p className="text-sm text-muted-foreground">Loading SLA trend…</p>
          ) : slaTrendChartData.length === 0 ? (
            <p className="text-sm text-muted-foreground">No close cycles in scope for a trend yet.</p>
          ) : (
            <div className="h-[220px] w-full" data-testid="ft-sla-trend-chart">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={slaTrendChartData} margin={{ top: 8, right: 12, left: 0, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                  <XAxis dataKey="label" tick={RC_TICK} interval={0} angle={-30} textAnchor="end" height={48} />
                  <YAxis domain={[0, 100]} tick={RC_TICK} width={40} />
                  <Tooltip
                    contentStyle={rcTooltipStyle()}
                    formatter={(value, name) => {
                      if (name === "approved_pct") return [`${value}%`, "Approved"];
                      return [value, name];
                    }}
                    labelFormatter={(_lab, payload) => {
                      const p0 = payload && payload[0] && payload[0].payload;
                      if (!p0) return "";
                      return [p0.cycle_name, p0.cycle_id].filter(Boolean).join(" · ");
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="approved_pct"
                    name="approved_pct"
                    stroke="hsl(var(--chart-2))"
                    strokeWidth={2}
                    dot={{ r: 3, fill: "hsl(var(--chart-2))" }}
                    activeDot={{ r: 5 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </SectionCard>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          <SectionCard kicker="WORKLOAD" title="Pending tasks by owner">
            {extrasLoading || !extras.workload ? (
              <p className="text-sm text-muted-foreground">Loading workload…</p>
            ) : workloadChart.length === 0 ? (
              <p className="text-sm text-muted-foreground">No pending close tasks in the current scope.</p>
            ) : (
              <>
                <div className="h-[240px] w-full mb-6">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={workloadChart} margin={{ top: 8, right: 8, left: 0, bottom: 48 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                      <XAxis dataKey="owner" tick={RC_TICK} interval={0} angle={-35} textAnchor="end" height={56} />
                      <YAxis tick={RC_TICK} allowDecimals={false} width={36} />
                      <Tooltip
                        contentStyle={rcTooltipStyle()}
                        formatter={(value) => [value, "Pending"]}
                        labelFormatter={(_label, payload) =>
                          payload && payload[0] ? payload[0].payload.fullName : ""
                        }
                      />
                      <Bar dataKey="count" fill="hsl(var(--chart-1))" radius={[4, 4, 0, 0]} name="Pending" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <div className="crt-overline mb-2 text-muted-foreground">All owners (pending)</div>
                <div className="max-h-64 overflow-auto rounded-md border border-border">
                  <table className="w-full text-sm tabular-nums" data-testid="ft-workload-owner-table">
                    <thead className="sticky top-0 bg-muted/80 backdrop-blur-sm border-b border-border">
                      <tr>
                        <th className="text-left font-medium px-3 py-2">Owner</th>
                        <th className="text-right font-medium px-3 py-2">Critical</th>
                        <th className="text-right font-medium px-3 py-2">Pending</th>
                      </tr>
                    </thead>
                    <tbody>
                      {workloadTableRows.map((row) => (
                        <tr key={row.owner} className="border-b border-border/60 last:border-0">
                          <td className="px-3 py-2 text-foreground break-all max-w-[220px]">{row.owner}</td>
                          <td className="px-3 py-2 text-right text-muted-foreground">{row.critical}</td>
                          <td className="px-3 py-2 text-right font-medium">{row.pending}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </SectionCard>

          <SectionCard kicker="BOTTLENECKS" title="Latest cycle — backlog by owner">
            {extrasLoading || !extras.bottlenecks ? (
              <p className="text-sm text-muted-foreground">Loading bottlenecks…</p>
            ) : extras.bottlenecks.note === "no_close_cycles" ? (
              <p className="text-sm text-muted-foreground">No close cycles for this entity; bottlenecks unavailable.</p>
            ) : bottleneckChart.length === 0 ? (
              <p className="text-sm text-muted-foreground">No pending tasks on the resolved bottleneck cycle.</p>
            ) : (
              <div className="h-[240px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={bottleneckChart} margin={{ top: 8, right: 8, left: 0, bottom: 48 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                    <XAxis dataKey="owner" tick={RC_TICK} interval={0} angle={-35} textAnchor="end" height={56} />
                    <YAxis tick={RC_TICK} allowDecimals={false} width={36} />
                    <Tooltip
                      contentStyle={rcTooltipStyle()}
                      formatter={(value) => [value, "Pending"]}
                      labelFormatter={(_label, payload) =>
                        payload && payload[0] ? payload[0].payload.fullName : ""
                      }
                    />
                    <Bar dataKey="count" fill="hsl(var(--chart-3))" radius={[4, 4, 0, 0]} name="Pending" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </SectionCard>
        </div>

        {extras.scorecards?.scorecards && (
          <SectionCard kicker="SCORECARDS" title="Role snapshot" className="mb-8">
            <ul className="text-sm space-y-2">
              {extras.scorecards.scorecards.map((s) => (
                <li key={s.role} className="flex justify-between gap-4 border-b border-border/60 pb-2 last:border-0">
                  <span className="font-medium text-foreground">{s.role}</span>
                  <span className="text-muted-foreground tabular-nums">
                    {s.role === "Controller" && s.open_close_tasks != null && (
                      <>Open close tasks: {s.open_close_tasks}</>
                    )}
                    {s.role === "CFO" && s.open_actions != null && <>Open actions: {s.open_actions}</>}
                  </span>
                </li>
              ))}
            </ul>
          </SectionCard>
        )}

        <SectionCard kicker="DRILL" title="Next steps">
          <ul className="text-sm space-y-2 text-muted-foreground">
            <li>
              <Link
                className="text-primary hover:underline"
                to={hrefWithMasterParams(d?.drill_paths?.close || "/app/finance-operations/month-end-close")}
              >
                Month-end close
              </Link>
            </li>
            <li>
              <Link
                className="text-primary hover:underline"
                to={hrefWithMasterParams(d?.drill_paths?.cases || "/app/cases?status=open")}
              >
                Open cases
              </Link>
            </li>
            <li>
              <Link
                className="text-primary hover:underline"
                to={hrefWithMasterParams(d?.drill_paths?.exceptions || "/app/audit")}
              >
                Controls &amp; exceptions
              </Link>
            </li>
          </ul>
        </SectionCard>
      </div>
    </PageShell>
  );
}
