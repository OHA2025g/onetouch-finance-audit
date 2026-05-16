import React, { useMemo } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { RC_STROKE, RC_TICK, rcTooltipStyle } from "../../lib/rechartsTheme";
import { fmtUSD } from "../../lib/format";
import { healthDonutData } from "../../lib/auditWorkspaceSummary";
import { SectionCard } from "../PageShell";

const SEV_COLORS = {
  critical: "hsl(var(--destructive))",
  high: "hsl(var(--chart-3))",
  medium: "hsl(var(--chart-2))",
  low: "hsl(var(--chart-4))",
};

function ChartSrTable({ caption, headers, rows, testId }) {
  if (!rows.length) return null;
  return (
    <table className="sr-only" data-testid={testId}>
      <caption>{caption}</caption>
      <thead>
        <tr>
          {headers.map((h) => (
            <th key={h} scope="col">
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.key}>
            {row.cells.map((cell, i) => (
              <td key={i}>{cell}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function HeatmapGrid({ heatmap = [] }) {
  const { processes, severities, grid, failGrid } = useMemo(() => {
    const procs = [...new Set(heatmap.map((h) => h.process))].sort();
    const sevs = [...new Set(heatmap.map((h) => h.criticality))].sort((a, b) => {
      const rank = { critical: 4, high: 3, medium: 2, low: 1 };
      return (rank[b] || 0) - (rank[a] || 0);
    });
    const map = {};
    const failMap = {};
    for (const h of heatmap) {
      map[`${h.process}|${h.criticality}`] = h.open_count;
      failMap[`${h.process}|${h.criticality}`] = h.fail_count ?? 0;
    }
    return { processes: procs, severities: sevs, grid: map, failGrid: failMap };
  }, [heatmap]);

  if (!processes.length) {
    return <p className="crt-num text-xs text-muted-foreground">No open exceptions in scope.</p>;
  }

  return (
    <div className="w-full overflow-x-auto">
      <table className="w-full min-w-[280px] border-collapse text-xs" data-testid="audit-exception-heatmap">
        <thead>
          <tr>
            <th className="crt-num p-2 text-left text-[10px] uppercase tracking-wider text-muted-foreground">Process</th>
            {severities.map((s) => (
              <th key={s} className="crt-num p-2 text-center text-[10px] uppercase tracking-wider text-muted-foreground">
                {s}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {processes.map((proc) => (
            <tr key={proc} className="border-t border-zinc-200 dark:border-zinc-800">
              <td className="crt-num p-2 font-medium text-foreground">{proc}</td>
              {severities.map((sev) => {
                const n = grid[`${proc}|${sev}`] || 0;
                const fail = failGrid[`${proc}|${sev}`] || 0;
                const intensity = n === 0 ? 0 : Math.min(1, 0.25 + n * 0.15);
                return (
                  <td key={sev} className="p-1 text-center">
                    <span
                      className="crt-num inline-flex h-8 min-w-[2rem] flex-col items-center justify-center rounded-sm text-[10px] tabular-nums leading-tight"
                      style={{
                        background: n
                          ? `color-mix(in srgb, ${SEV_COLORS[sev] || "hsl(var(--chart-2))"} ${Math.round(intensity * 100)}%, transparent)`
                          : "transparent",
                        color: n || fail ? "hsl(var(--foreground))" : "hsl(var(--muted-foreground))",
                      }}
                      title={fail ? `${n} open · ${fail} failing controls` : undefined}
                    >
                      {n ? n : "—"}
                      {fail > 0 ? <span className="text-[8px] text-muted-foreground">{fail} fail</span> : null}
                    </span>
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

export function AuditHealthDonut({ passFailNotRun }) {
  const donut = healthDonutData(passFailNotRun);
  if (!donut.length) {
    return <p className="crt-num text-xs text-muted-foreground">No control runs yet.</p>;
  }
  const tableRows = donut.map((d) => ({ key: d.name, cells: [d.name, d.value] }));
  return (
    <>
    <ResponsiveContainer width="100%" height={180} data-testid="audit-health-donut">
      <PieChart>
        <Pie data={donut} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={42} outerRadius={68} paddingAngle={2}>
          {donut.map((d) => (
            <Cell key={d.name} fill={d.fill} />
          ))}
        </Pie>
        <Tooltip contentStyle={rcTooltipStyle()} />
      </PieChart>
    </ResponsiveContainer>
    <ChartSrTable
      caption="Control run health"
      headers={["Status", "Count"]}
      rows={tableRows}
      testId="audit-health-donut-table"
    />
    </>
  );
}

export function AuditByProcessChart({ byProcess = [], onSelectProcess }) {
  const data = byProcess.slice(0, 8);
  if (!data.length) {
    return <p className="crt-num text-xs text-muted-foreground">No open exceptions by process.</p>;
  }
  const tableRows = data.map((row) => ({
    key: row.process,
    cells: [row.process, row.open_count ?? 0, row.control_count ?? "—", fmtUSD(row.open_exposure_usd ?? 0)],
  }));
  return (
    <>
      <ResponsiveContainer width="100%" height={200} data-testid="audit-by-process-chart">
        <BarChart data={data} margin={{ left: 4, right: 8 }}>
          <CartesianGrid stroke={RC_STROKE} vertical={false} />
          <XAxis dataKey="process" stroke={RC_STROKE} tick={{ ...RC_TICK, fontSize: 9 }} interval={0} angle={-18} textAnchor="end" height={52} />
          <YAxis stroke={RC_STROKE} tick={RC_TICK} allowDecimals={false} />
          <Tooltip
            contentStyle={rcTooltipStyle()}
            formatter={(value, name) => value}
            labelFormatter={(label) => label}
            content={({ active, payload }) => {
              if (!active || !payload?.[0]) return null;
              const row = payload[0].payload;
              return (
                <div className="rounded-sm border border-zinc-200 bg-white px-2 py-1 text-xs shadow dark:border-zinc-700 dark:bg-zinc-900">
                  <div className="font-medium">{row.process}</div>
                  <div className="crt-num text-muted-foreground">
                    {row.open_count} open · {row.control_count ?? "—"} controls
                  </div>
                </div>
              );
            }}
          />
          <Bar
            dataKey="open_count"
            name="Open exceptions"
            fill="hsl(var(--chart-2))"
            radius={[2, 2, 0, 0]}
            cursor={onSelectProcess ? "pointer" : "default"}
            onClick={(bar) => {
              const proc = bar?.payload?.process;
              if (proc && onSelectProcess) onSelectProcess(proc);
            }}
          />
        </BarChart>
      </ResponsiveContainer>
      <ChartSrTable
        caption="Open exceptions by process"
        headers={["Process", "Open exceptions", "Controls", "Exposure"]}
        rows={tableRows}
        testId="audit-by-process-chart-table"
      />
    </>
  );
}

export function AuditBySeverityChart({ bySeverity = [] }) {
  const data = bySeverity.slice(0, 6);
  if (!data.length) {
    return <p className="crt-num text-xs text-muted-foreground">No open exceptions by severity.</p>;
  }
  return (
    <ResponsiveContainer width="100%" height={200} data-testid="audit-by-severity-chart">
      <BarChart data={data} margin={{ left: 4, right: 8 }}>
        <CartesianGrid stroke={RC_STROKE} vertical={false} />
        <XAxis dataKey="severity" stroke={RC_STROKE} tick={{ ...RC_TICK, fontSize: 9 }} />
        <YAxis stroke={RC_STROKE} tick={RC_TICK} allowDecimals={false} />
        <Tooltip contentStyle={rcTooltipStyle()} />
        <Bar dataKey="open_count" name="Open exceptions" fill="hsl(var(--chart-3))" radius={[2, 2, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function AuditTopFailingChart({ topFailing = [], onSelectControl }) {
  const data = topFailing.map((t) => ({
    label: t.code,
    controlId: t.id,
    exceptions: t.exceptions,
    exposure: t.open_exposure_usd,
  }));
  if (!data.length) {
    return <p className="crt-num text-xs text-muted-foreground">No failing controls in scope.</p>;
  }
  return (
    <ResponsiveContainer width="100%" height={200} data-testid="audit-top-failing-chart">
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 12 }}>
        <CartesianGrid stroke={RC_STROKE} horizontal={false} />
        <XAxis type="number" stroke={RC_STROKE} tick={RC_TICK} allowDecimals={false} />
        <YAxis type="category" dataKey="label" width={72} stroke={RC_STROKE} tick={{ ...RC_TICK, fontSize: 9 }} />
        <Tooltip contentStyle={rcTooltipStyle()} formatter={(v, name) => (name === "exposure" ? fmtUSD(v) : v)} />
        <Bar
          dataKey="exceptions"
          name="Exceptions"
          fill="hsl(var(--chart-3))"
          radius={[0, 2, 2, 0]}
          cursor={onSelectControl ? "pointer" : "default"}
          onClick={(bar) => {
            const id = bar?.payload?.controlId;
            if (id && onSelectControl) onSelectControl(id);
          }}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function AuditTrendsArea({ series = [] }) {
  if (!series.length) {
    return <p className="crt-num text-xs text-muted-foreground">Trend data unavailable.</p>;
  }
  return (
    <ResponsiveContainer width="100%" height={200} data-testid="audit-trends-chart">
      <AreaChart data={series} margin={{ left: 0, right: 8 }}>
        <CartesianGrid stroke={RC_STROKE} vertical={false} />
        <XAxis dataKey="date" stroke={RC_STROKE} tick={{ ...RC_TICK, fontSize: 8 }} interval="preserveStartEnd" />
        <YAxis stroke={RC_STROKE} tick={RC_TICK} allowDecimals={false} />
        <Tooltip contentStyle={rcTooltipStyle()} />
        <Area
          type="monotone"
          dataKey="new_exceptions"
          name="New exceptions"
          stroke="hsl(var(--chart-3))"
          fill="hsl(var(--chart-3))"
          fillOpacity={0.2}
        />
        <Area
          type="monotone"
          dataKey="failed_runs"
          name="Failed runs"
          stroke="hsl(var(--destructive))"
          fill="hsl(var(--destructive))"
          fillOpacity={0.15}
        />
        <Area
          type="monotone"
          dataKey="exceptions_closed"
          name="Closed"
          stroke="hsl(var(--chart-4))"
          fill="hsl(var(--chart-4))"
          fillOpacity={0.12}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function AuditChartsRow({ summary, trends, trendDays, onTrendDaysChange, onSelectControl, onSelectProcess }) {
  return (
    <div className="mb-4 grid grid-cols-1 gap-4 xl:grid-cols-12">
      <SectionCard className="xl:col-span-3" kicker="HEALTH" title="Control run health" bodyClassName="p-4">
        <AuditHealthDonut passFailNotRun={summary?.pass_fail_not_run} />
      </SectionCard>
      <SectionCard className="xl:col-span-3" kicker="PROCESS" title="Open exceptions by process" bodyClassName="p-4">
        <AuditByProcessChart byProcess={summary?.by_process} onSelectProcess={onSelectProcess} />
        {onSelectProcess ? (
          <p className="crt-num mt-2 text-[10px] text-muted-foreground">Click a process bar to open a control in that process.</p>
        ) : null}
      </SectionCard>
      <SectionCard className="xl:col-span-3" kicker="SEVERITY" title="Open exceptions by severity" bodyClassName="p-4">
        <AuditBySeverityChart bySeverity={summary?.by_severity} />
      </SectionCard>
      <SectionCard className="xl:col-span-3" kicker="TOP FAILING" title="Controls with most exceptions" bodyClassName="p-4">
        <AuditTopFailingChart topFailing={summary?.top_failing_controls} onSelectControl={onSelectControl} />
        {onSelectControl ? (
          <p className="crt-num mt-2 text-[10px] text-muted-foreground">Click a bar to open control detail.</p>
        ) : null}
      </SectionCard>
      <SectionCard
        className="xl:col-span-7"
        kicker="TREND"
        title={`${trendDays}-day exception & run activity`}
        bodyClassName="p-4"
        right={
          onTrendDaysChange ? (
            <div className="flex gap-1" data-testid="audit-trend-days-toggle">
              {[30, 90].map((d) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => onTrendDaysChange(d)}
                  className={
                    trendDays === d
                      ? "crt-num rounded-sm border border-primary bg-primary/10 px-2 py-1 text-[10px] uppercase tracking-wider text-primary"
                      : "crt-num rounded-sm border border-zinc-300 px-2 py-1 text-[10px] uppercase tracking-wider text-muted-foreground dark:border-zinc-600"
                  }
                >
                  {d}d
                </button>
              ))}
            </div>
          ) : null
        }
      >
        <AuditTrendsArea series={trends?.series} />
      </SectionCard>
      <SectionCard className="xl:col-span-5" kicker="HEATMAP" title="Process × severity" bodyClassName="p-4">
        <HeatmapGrid heatmap={summary?.heatmap} />
      </SectionCard>
    </div>
  );
}
