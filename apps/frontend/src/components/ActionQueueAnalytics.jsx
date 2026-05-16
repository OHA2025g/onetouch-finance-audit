import React, { useMemo } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  Legend,
  ScatterChart,
  Scatter,
  ZAxis,
} from "recharts";
import { SectionCard } from "./PageShell";
import { RC_STROKE, RC_TICK, rcTooltipStyle } from "../lib/rechartsTheme";
import { fmtUSD } from "../lib/format";

const PIE_COLORS = [
  "hsl(var(--chart-1))",
  "hsl(var(--chart-3))",
  "hsl(var(--chart-4))",
  "hsl(var(--chart-5))",
  "hsl(var(--muted-foreground))",
];

const TYPE_COLORS = [
  "hsl(var(--chart-1))",
  "hsl(var(--chart-2))",
  "hsl(var(--chart-3))",
  "hsl(var(--chart-4))",
  "hsl(var(--chart-5))",
];

export function ActionQueueOpsScorecard({ linkage }) {
  if (!linkage?.length) return null;
  return (
    <SectionCard kicker="OPS" title="Operations ↔ queue linkage" className="mb-6" bodyClassName="p-4">
      <div className="grid gap-2 sm:grid-cols-2" data-testid="aq-ops-scorecard">
        {linkage.map((row) => (
          <div
            key={row.id}
            className="flex items-center justify-between rounded-sm border border-zinc-200 px-3 py-2 dark:border-zinc-700"
          >
            <span className="text-xs text-foreground">{row.label}</span>
            <span className="crt-num text-[10px] uppercase text-muted-foreground">
              {row.value ?? "—"}
              {row.unit === "weeks" ? " wks" : ""}
              {(row.linked_queue_count ?? 0) > 0 ? (
                <span className="ml-2 font-semibold text-primary">{row.linked_queue_count} in queue</span>
              ) : null}
            </span>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

export function ActionQueueKpiStrip({ summary }) {
  if (!summary) return null;
  const byPri = summary.by_priority || {};
  const tiles = [
    { label: "Open", value: summary.open_total ?? 0 },
    { label: "P0", value: summary.p0_open ?? byPri.P0 ?? 0 },
    { label: "P1", value: summary.p1_open ?? byPri.P1 ?? 0 },
    { label: "P2", value: byPri.P2 ?? 0 },
    { label: "P3", value: byPri.P3 ?? 0 },
    { label: "Exposure", value: fmtUSD(summary.queue_exposure_usd ?? 0) },
    { label: "Mean age (d)", value: summary.mean_age_days ?? 0 },
    { label: "SLA %", value: `${summary.sla_compliance_pct ?? 0}%` },
    { label: "Stale", value: summary.stale_open_count ?? 0 },
    { label: "Decision 7d", value: `${summary.decision_rate_7d ?? 0}%` },
    { label: "Escalation", value: `${summary.escalation_rate_7d ?? 0}%` },
    { label: "TTF (h)", value: summary.median_time_to_first_action_hours ?? "—" },
    { label: "TTC (d)", value: summary.median_time_to_close_days ?? "—" },
    {
      label: "Note %",
      value:
        summary.audit_note_completeness_pct != null ? `${summary.audit_note_completeness_pct}%` : "—",
    },
  ];
  return (
    <div className="mb-6 grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-6 xl:grid-cols-7" data-testid="aq-kpi-strip">
      {tiles.map((t) => (
        <div
          key={t.label}
          className="rounded-sm border border-zinc-200 bg-white px-2 py-2 dark:border-zinc-700 dark:bg-zinc-900/40"
        >
          <p className="crt-num text-[9px] uppercase tracking-wider text-muted-foreground">{t.label}</p>
          <p className="font-display text-sm font-semibold tabular-nums text-foreground">{t.value}</p>
        </div>
      ))}
    </div>
  );
}

function EntityProcessHeatmap({ matrix }) {
  const { entities, processes, grid } = useMemo(() => {
    const rows = matrix || [];
    const entSet = [...new Set(rows.map((r) => r.entity || "unknown"))].slice(0, 8);
    const procSet = [...new Set(rows.map((r) => r.process || "Unassigned"))].slice(0, 8);
    const lookup = {};
    let max = 1;
    for (const r of rows) {
      const key = `${r.entity}|${r.process}`;
      lookup[key] = r.count;
      if (r.count > max) max = r.count;
    }
    return { entities: entSet, processes: procSet, grid: { lookup, max } };
  }, [matrix]);

  if (!entities.length) return <p className="text-sm text-muted-foreground">No open items in scope.</p>;

  return (
    <div className="overflow-x-auto" data-testid="aq-entity-process-heatmap">
      <table className="w-full min-w-[280px] border-collapse text-[10px]">
        <thead>
          <tr>
            <th className="p-1 text-left text-muted-foreground">Entity</th>
            {processes.map((p) => (
              <th key={p} className="crt-num max-w-[72px] truncate p-1 text-center text-muted-foreground" title={p}>
                {p.slice(0, 10)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {entities.map((ent) => (
            <tr key={ent}>
              <td className="crt-num truncate p-1 font-medium text-foreground" title={ent}>
                {ent}
              </td>
              {processes.map((proc) => {
                const c = grid.lookup[`${ent}|${proc}`] || 0;
                const alpha = c ? 0.15 + (c / grid.max) * 0.85 : 0.04;
                return (
                  <td
                    key={proc}
                    className="crt-num p-1 text-center tabular-nums"
                    style={{ backgroundColor: `hsl(var(--chart-1) / ${alpha})` }}
                    title={`${ent} · ${proc}: ${c}`}
                  >
                    {c || "·"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ActionQueueCharts({ dashboard }) {
  const summary = dashboard?.summary || {};
  const trends = dashboard?.trends?.series || [];
  const throughput = dashboard?.trends?.throughput || trends;
  const typeMixSeries = dashboard?.trends?.type_mix_series || [];
  const topExp = dashboard?.top_exposure || [];
  const burndownSeries = dashboard?.sla_burndown?.series || [];

  const agingData = [
    { bucket: "0–3d", count: summary.aging_buckets?.["0_3"] ?? 0 },
    { bucket: "4–7d", count: summary.aging_buckets?.["4_7"] ?? 0 },
    { bucket: "8–14d", count: summary.aging_buckets?.["8_14"] ?? 0 },
    { bucket: "14d+", count: summary.aging_buckets?.["14_plus"] ?? 0 },
  ];

  const statusData = Object.entries(summary.by_status || {}).map(([name, value]) => ({ name, value }));
  const priorityByType = dashboard?.priority_by_type || [];
  const exposureByProcess = summary.exposure_by_process || [];
  const readinessSeries = dashboard?.readiness_correlation?.series || [];
  const approverBottleneck = dashboard?.approver_bottleneck || [];

  const priorityTypeKeys = useMemo(() => {
    const keys = new Set();
    for (const row of priorityByType) {
      Object.keys(row).forEach((k) => {
        if (k !== "priority") keys.add(k);
      });
    }
    return [...keys].slice(0, 8);
  }, [priorityByType]);

  const typeKeys = useMemo(() => {
    const keys = new Set();
    for (const row of typeMixSeries) {
      Object.keys(row).forEach((k) => {
        if (k !== "week") keys.add(k);
      });
    }
    return [...keys].slice(0, 6);
  }, [typeMixSeries]);

  if (!dashboard) return null;

  return (
    <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
      <SectionCard kicker="AGING" title="Open items by age" bodyClassName="p-4">
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={agingData}>
            <CartesianGrid stroke={RC_STROKE} vertical={false} />
            <XAxis dataKey="bucket" stroke={RC_STROKE} tick={RC_TICK} />
            <YAxis stroke={RC_STROKE} tick={RC_TICK} allowDecimals={false} />
            <Tooltip contentStyle={rcTooltipStyle()} />
            <Bar dataKey="count" fill="hsl(var(--chart-1))" />
          </BarChart>
        </ResponsiveContainer>
      </SectionCard>

      <SectionCard kicker="TREND" title="8-week queue trend" bodyClassName="p-4">
        <ResponsiveContainer width="100%" height={160}>
          <LineChart data={trends}>
            <CartesianGrid stroke={RC_STROKE} vertical={false} />
            <XAxis dataKey="week" stroke={RC_STROKE} tick={RC_TICK} />
            <YAxis stroke={RC_STROKE} tick={RC_TICK} allowDecimals={false} />
            <Tooltip contentStyle={rcTooltipStyle()} />
            <Line type="monotone" dataKey="open_total" stroke="hsl(var(--chart-1))" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="p0_open" stroke="hsl(var(--chart-3))" strokeWidth={1.5} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </SectionCard>

      <SectionCard kicker="THROUGHPUT" title="Weekly decisions" bodyClassName="p-4">
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={throughput}>
            <CartesianGrid stroke={RC_STROKE} vertical={false} />
            <XAxis dataKey="week" stroke={RC_STROKE} tick={RC_TICK} />
            <YAxis stroke={RC_STROKE} tick={RC_TICK} allowDecimals={false} />
            <Tooltip contentStyle={rcTooltipStyle()} />
            <Legend wrapperStyle={{ fontSize: 10 }} />
            <Bar dataKey="approved" stackId="a" fill="hsl(var(--chart-4))" />
            <Bar dataKey="rejected" stackId="a" fill="hsl(var(--chart-3))" />
            <Bar dataKey="escalated" stackId="a" fill="hsl(var(--chart-5))" />
          </BarChart>
        </ResponsiveContainer>
      </SectionCard>

      <SectionCard kicker="P0 BURNDOWN" title="P0 open over time" bodyClassName="p-4">
        <ResponsiveContainer width="100%" height={160}>
          <LineChart data={burndownSeries}>
            <CartesianGrid stroke={RC_STROKE} vertical={false} />
            <XAxis dataKey="week" stroke={RC_STROKE} tick={RC_TICK} />
            <YAxis stroke={RC_STROKE} tick={RC_TICK} allowDecimals={false} />
            <Tooltip contentStyle={rcTooltipStyle()} />
            <Line type="monotone" dataKey="p0_open" stroke="hsl(var(--destructive))" strokeWidth={2} dot />
          </LineChart>
        </ResponsiveContainer>
        <p className="crt-num mt-2 text-[10px] text-muted-foreground">
          Target P0: {dashboard.sla_burndown?.target_p0 ?? 0} · Remaining: {dashboard.sla_burndown?.remaining ?? 0}
        </p>
      </SectionCard>

      <SectionCard kicker="TYPE MIX" title="Open items by type (weekly)" bodyClassName="p-4">
        {typeMixSeries.length && typeKeys.length ? (
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={typeMixSeries}>
              <CartesianGrid stroke={RC_STROKE} vertical={false} />
              <XAxis dataKey="week" stroke={RC_STROKE} tick={RC_TICK} />
              <YAxis stroke={RC_STROKE} tick={RC_TICK} allowDecimals={false} />
              <Tooltip contentStyle={rcTooltipStyle()} />
              <Legend wrapperStyle={{ fontSize: 9 }} />
              {typeKeys.map((k, i) => (
                <Bar key={k} dataKey={k} stackId="types" fill={TYPE_COLORS[i % TYPE_COLORS.length]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-sm text-muted-foreground">Snapshots will populate after refresh.</p>
        )}
      </SectionCard>

      <SectionCard kicker="HEATMAP" title="Entity × process" bodyClassName="p-4">
        <EntityProcessHeatmap matrix={dashboard.entity_process_matrix} />
      </SectionCard>

      <SectionCard kicker="EXPOSURE" title="Top exposure in queue" bodyClassName="p-4">
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={topExp} layout="vertical" margin={{ left: 8 }}>
            <CartesianGrid stroke={RC_STROKE} horizontal={false} />
            <XAxis type="number" stroke={RC_STROKE} tick={RC_TICK} />
            <YAxis type="category" dataKey="title" width={90} stroke={RC_STROKE} tick={{ ...RC_TICK, fontSize: 9 }} />
            <Tooltip contentStyle={rcTooltipStyle()} formatter={(v) => fmtUSD(v)} />
            <Bar dataKey="exposure" fill="hsl(var(--chart-4))" />
          </BarChart>
        </ResponsiveContainer>
      </SectionCard>

      <SectionCard kicker="STATUS" title="Status mix" bodyClassName="p-4">
        <ResponsiveContainer width="100%" height={160}>
          <PieChart>
            <Pie data={statusData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={55} label>
              {statusData.map((_, i) => (
                <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip contentStyle={rcTooltipStyle()} />
          </PieChart>
        </ResponsiveContainer>
      </SectionCard>

      <SectionCard kicker="BY PROCESS" title="Exposure by process" bodyClassName="p-4">
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={exposureByProcess}>
            <CartesianGrid stroke={RC_STROKE} vertical={false} />
            <XAxis dataKey="process" stroke={RC_STROKE} tick={{ ...RC_TICK, fontSize: 9 }} />
            <YAxis stroke={RC_STROKE} tick={RC_TICK} />
            <Tooltip contentStyle={rcTooltipStyle()} formatter={(v) => fmtUSD(v)} />
            <Bar dataKey="exposure" fill="hsl(var(--chart-2))" />
          </BarChart>
        </ResponsiveContainer>
      </SectionCard>

      <SectionCard kicker="PRIORITY" title="Open by priority (stacked type)" bodyClassName="p-4">
        {priorityByType.length && priorityTypeKeys.length ? (
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={priorityByType}>
              <CartesianGrid stroke={RC_STROKE} vertical={false} />
              <XAxis dataKey="priority" stroke={RC_STROKE} tick={RC_TICK} />
              <YAxis stroke={RC_STROKE} tick={RC_TICK} allowDecimals={false} />
              <Tooltip contentStyle={rcTooltipStyle()} />
              <Legend wrapperStyle={{ fontSize: 9 }} />
              {priorityTypeKeys.map((k, i) => (
                <Bar key={k} dataKey={k} stackId="pri" fill={TYPE_COLORS[i % TYPE_COLORS.length]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-sm text-muted-foreground">No open items in scope.</p>
        )}
      </SectionCard>

      {readinessSeries.length > 0 ? (
        <SectionCard kicker="ASSURANCE" title="Readiness vs queue depth" bodyClassName="p-4">
          <ResponsiveContainer width="100%" height={180}>
            <ScatterChart margin={{ left: 8, bottom: 8 }}>
              <CartesianGrid stroke={RC_STROKE} />
              <XAxis
                type="number"
                dataKey="open_total"
                name="Open items"
                stroke={RC_STROKE}
                tick={RC_TICK}
              />
              <YAxis
                type="number"
                dataKey="audit_readiness_pct"
                name="Readiness %"
                stroke={RC_STROKE}
                tick={RC_TICK}
                domain={[0, 100]}
              />
              <ZAxis type="category" dataKey="week" name="Week" />
              <Tooltip contentStyle={rcTooltipStyle()} cursor={{ strokeDasharray: "3 3" }} />
              <Scatter data={readinessSeries} fill="hsl(var(--chart-1))" />
            </ScatterChart>
          </ResponsiveContainer>
        </SectionCard>
      ) : null}

      {approverBottleneck.length > 0 ? (
        <SectionCard kicker="BOTTLENECK" title="Approver load (open)" bodyClassName="p-4">
          <ul className="space-y-1 text-xs" data-testid="aq-approver-bottleneck">
            {approverBottleneck.map((row) => (
              <li key={row.assignee} className="flex justify-between gap-2">
                <span className="truncate text-muted-foreground">{row.assignee}</span>
                <span className="crt-num font-semibold tabular-nums">{row.open_count}</span>
              </li>
            ))}
          </ul>
        </SectionCard>
      ) : null}
    </div>
  );
}
