import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ComposedChart,
  Area,
  Line,
} from "recharts";
import { toast } from "sonner";
import { http } from "../../lib/api";
import { fmtUSD, fmtPct } from "../../lib/format";
import { RC_STROKE, RC_TICK, rcTooltipStyle } from "../../lib/rechartsTheme";
import { StatCard } from "../StatCard";
import { SectionCard } from "../PageShell";
import {
  DataTable,
  DataTableBody,
  DataTableHead,
  DataTableRow,
  DataTableTd,
  DataTableTh,
} from "../DataTable";
import { pathForRelatedType } from "../../lib/drillPaths";
import clsx from "clsx";

const KPI_LABELS = {
  repeat_finding_rate_pct: "Repeat findings",
  evidence_completeness_pct: "Evidence completeness",
  remediation_sla_pct: "Remediation SLA",
  high_critical_open_cases: "High/critical cases",
  unresolved_high_risk_exposure: "Unresolved exposure",
};

function cellTone(r) {
  if (r.readiness >= 80) return "text-[hsl(var(--chart-4))]";
  if (r.readiness >= 60) return "text-[hsl(var(--chart-3))]";
  return "text-[hsl(var(--destructive))]";
}

const RISK_BAND_LABELS = {
  critical: "Critical",
  elevated: "Elevated",
  moderate: "Moderate",
  stable: "Stable",
};

export default function AuditReadinessDrillDetail({
  detail,
  trend,
  drilldown,
  dashboardParams,
  hrefWithMasterParams,
  onReload,
  moduleHref,
  onProcessSelect,
}) {
  const [weakOnly, setWeakOnly] = useState(false);
  const [matrixSort, setMatrixSort] = useState("readiness_asc");
  const [refreshing, setRefreshing] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportingXlsx, setExportingXlsx] = useState(false);
  const [exportingCommittee, setExportingCommittee] = useState(false);
  const [runningControls, setRunningControls] = useState(false);
  const v2Enabled = detail?.feature_flags?.readiness_drill_v2 !== false;

  const summary = detail?.summary || {};
  const heatmap = detail?.heatmap || [];
  const processes = useMemo(
    () => [...new Set(heatmap.map((r) => r.process))].sort(),
    [heatmap],
  );

  const filteredHeatmap = useMemo(() => {
    let rows = [...heatmap];
    if (weakOnly) rows = rows.filter((r) => (r.readiness ?? 100) < 60);
    if (matrixSort === "readiness_asc") rows.sort((a, b) => (a.readiness ?? 0) - (b.readiness ?? 0));
    else if (matrixSort === "readiness_desc") rows.sort((a, b) => (b.readiness ?? 0) - (a.readiness ?? 0));
    else if (matrixSort === "exposure_desc") rows.sort((a, b) => (b.exposure ?? 0) - (a.exposure ?? 0));
    return rows;
  }, [heatmap, weakOnly, matrixSort]);

  const chartData = useMemo(() => {
    const multi = trend?.multi_series;
    if (Array.isArray(multi) && multi.length) return multi;
    return (trend?.series || []).map((pt) => ({
      period: pt.period,
      readiness: pt.value,
      exposure: 0,
      control_fail_count: 0,
    }));
  }, [trend]);

  const componentBars = useMemo(() => {
    const c = detail?.portfolio_components || {};
    return [
      { name: "Controls (40%)", value: c.control_pct ?? 0 },
      { name: "Recon (25%)", value: c.recon_pct ?? 0 },
      { name: "Evidence (20%)", value: c.evidence_pct ?? 0 },
      { name: "Issues (15%)", value: c.issue_pct ?? 0 },
    ];
  }, [detail]);

  const componentTrendData = useMemo(() => trend?.component_series || [], [trend]);

  const waterfallData = useMemo(() => {
    const steps = detail?.waterfall || [];
    return steps.map((s) => ({
      label: s.label,
      value: typeof s.value === "number" ? s.value : 0,
      kind: s.kind,
    }));
  }, [detail]);

  const extra = detail?.extra_metrics || {};
  const narrative = detail?.narrative_slice;
  const paginatedWeak = detail?.lists?.weak_cells;

  const deltaLabel =
    summary.delta_pct != null
      ? `${summary.delta_direction === "down" ? "▼" : summary.delta_direction === "up" ? "▲" : ""} ${Math.abs(summary.delta_pct).toFixed(1)} pts vs prior`
      : null;

  const priorAnchorValue = useMemo(() => {
    const anchor = trend?.prior_anchor;
    if (!Array.isArray(anchor) || !anchor.length) return null;
    const v = anchor[0]?.value;
    return typeof v === "number" ? v : null;
  }, [trend]);

  const moversMode = detail?.movers?.mode;
  const deterioratorTitle =
    moversMode === "wow" ? "Biggest week-over-week drops" : "Lowest readiness cells";
  const improverTitle =
    moversMode === "wow" ? "Biggest week-over-week gains" : "Highest readiness cells";

  const scopeChips = useMemo(() => {
    const f = detail?.filters_applied || {};
    return Object.entries(f).filter(([, v]) => v != null && v !== "");
  }, [detail]);

  const trendSourceLabel =
    trend?.trend_source === "snapshots"
      ? "Historical snapshots"
      : trend?.trend_source === "cockpit"
        ? "Cockpit trend series"
        : trend?.trend_source === "synthetic"
          ? "Estimated series"
          : null;

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await http.post("/kpi/refresh", null, { params: dashboardParams });
      toast.success("KPIs refreshed");
      await onReload?.();
    } catch {
      toast.error("Refresh failed");
    } finally {
      setRefreshing(false);
    }
  };

  const handleRunAllControls = async () => {
    setRunningControls(true);
    try {
      const { data: r } = await http.post("/controls/run-all");
      toast.success(`Re-ran ${r.runs?.length ?? 0} controls · ${r.total_exceptions ?? 0} exceptions`);
      await onReload?.();
    } catch {
      toast.error("Run all controls failed");
    } finally {
      setRunningControls(false);
    }
  };

  const downloadBlob = (data, mime, filename) => {
    const url = URL.createObjectURL(new Blob([data], { type: mime }));
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleExport = async (format = "csv") => {
    const isXlsx = format === "xlsx";
    if (isXlsx) setExportingXlsx(true);
    else setExporting(true);
    try {
      const res = await http.get("/kpi/drilldown/audit_readiness_pct/export", {
        params: { ...dashboardParams, format },
        responseType: "blob",
      });
      const mime = isXlsx
        ? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        : "text/csv";
      downloadBlob(res.data, mime, isXlsx ? "audit_readiness_drill.xlsx" : "audit_readiness_drill.csv");
      toast.success("Export downloaded");
    } catch {
      toast.error("Export failed");
    } finally {
      if (isXlsx) setExportingXlsx(false);
      else setExporting(false);
    }
  };

  const handleCommitteeExport = async () => {
    setExportingCommittee(true);
    try {
      const res = await http.get("/reports/audit-committee-pack.xlsx", {
        params: dashboardParams,
        responseType: "blob",
      });
      downloadBlob(
        res.data,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "audit-committee-pack.xlsx",
      );
      toast.success("Committee pack downloaded");
    } catch {
      toast.error("Committee pack export failed");
    } finally {
      setExportingCommittee(false);
    }
  };

  const refRowHref = (r) => {
    if (!r) return null;
    const p = pathForRelatedType(r.type, r.id);
    return p ? hrefWithMasterParams(p) : null;
  };

  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-2" data-testid="readiness-drill-toolbar">
        <button
          type="button"
          onClick={handleRefresh}
          disabled={refreshing}
          className="crt-num rounded-sm border border-zinc-300 bg-white px-3 py-2 text-[10px] uppercase tracking-wider text-muted-foreground hover:bg-zinc-50 dark:border-zinc-600 dark:bg-zinc-900"
          data-testid="readiness-refresh-kpis"
        >
          {refreshing ? "Refreshing…" : "Refresh KPIs"}
        </button>
        <button
          type="button"
          onClick={handleRunAllControls}
          disabled={runningControls}
          className="crt-num rounded-sm border border-zinc-300 bg-white px-3 py-2 text-[10px] uppercase tracking-wider text-muted-foreground hover:bg-zinc-50 dark:border-zinc-600 dark:bg-zinc-900"
          data-testid="readiness-run-all-controls"
        >
          {runningControls ? "Running…" : "Run all controls"}
        </button>
        <button
          type="button"
          onClick={() => handleExport("csv")}
          disabled={exporting}
          className="crt-num rounded-sm border border-zinc-300 bg-white px-3 py-2 text-[10px] uppercase tracking-wider text-muted-foreground hover:bg-zinc-50 dark:border-zinc-600 dark:bg-zinc-900"
          data-testid="readiness-export-csv"
        >
          {exporting ? "Exporting…" : "Export CSV"}
        </button>
        {v2Enabled ? (
          <>
            <button
              type="button"
              onClick={() => handleExport("xlsx")}
              disabled={exportingXlsx}
              className="crt-num rounded-sm border border-zinc-300 bg-white px-3 py-2 text-[10px] uppercase tracking-wider text-muted-foreground hover:bg-zinc-50 dark:border-zinc-600 dark:bg-zinc-900"
              data-testid="readiness-export-xlsx"
            >
              {exportingXlsx ? "Exporting…" : "Export XLSX"}
            </button>
            <button
              type="button"
              onClick={handleCommitteeExport}
              disabled={exportingCommittee}
              className="crt-num rounded-sm border border-zinc-300 bg-white px-3 py-2 text-[10px] uppercase tracking-wider text-muted-foreground hover:bg-zinc-50 dark:border-zinc-600 dark:bg-zinc-900"
              data-testid="readiness-export-committee"
            >
              {exportingCommittee ? "Exporting…" : "Committee pack"}
            </button>
          </>
        ) : null}
        {moduleHref ? (
          <Link
            to={moduleHref}
            className="crt-num inline-flex items-center rounded-sm border border-zinc-300 bg-white px-3 py-2 text-[10px] uppercase tracking-wider text-primary hover:bg-zinc-50 dark:border-zinc-600 dark:bg-zinc-900"
            data-testid="kpi-module-link"
          >
            Full readiness module →
          </Link>
        ) : null}
        {summary.p0_open > 0 ? (
          <Link
            to={hrefWithMasterParams("/app/cfo-action-queue?priority=P0")}
            className="crt-num inline-flex items-center rounded-sm border border-destructive/40 bg-destructive/5 px-3 py-2 text-[10px] uppercase tracking-wider text-destructive"
            data-testid="readiness-p0-banner"
          >
            {summary.p0_open} P0 queue items · Review
          </Link>
        ) : null}
      </div>

      {(detail?.as_of || scopeChips.length > 0) ? (
        <div
          className="mb-4 flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-wider text-muted-foreground"
          data-testid="readiness-scope-meta"
        >
          {detail?.as_of ? <span data-testid="readiness-as-of">As of {new Date(detail.as_of).toLocaleString()}</span> : null}
          {scopeChips.map(([k, v]) => (
            <span key={k} className="crt-num rounded-sm border border-zinc-200 px-2 py-0.5 dark:border-zinc-700">
              {k}: {String(v)}
            </span>
          ))}
        </div>
      ) : null}

      <div className="grid grid-cols-2 gap-4 mb-6 md:grid-cols-3 xl:grid-cols-5" data-testid="readiness-summary-strip">
        <StatCard
          compact
          label="Audit readiness"
          value={fmtPct(summary.current)}
          unit=""
          severity={summary.severity}
          trend={summary.delta_pct ?? undefined}
          subtle={deltaLabel}
          testId="readiness-kpi-current"
        />
        <StatCard
          compact
          label="Prior period"
          value={summary.prior_value != null ? fmtPct(summary.prior_value) : "—"}
          unit=""
          severity="default"
          testId="readiness-kpi-prior"
        />
        <StatCard
          compact
          label="Gap to target"
          value={summary.gap_to_target != null ? fmtPct(Math.max(0, summary.gap_to_target)) : "—"}
          unit=""
          severity={summary.gap_to_target > 0 ? "warning" : "success"}
          testId="readiness-kpi-gap"
        />
        <StatCard
          compact
          label="Cells below 60%"
          value={String(summary.cells_below_60 ?? 0)}
          unit=""
          severity={(summary.cells_below_60 ?? 0) > 0 ? "critical" : "success"}
          subtle={`of ${summary.cell_count ?? 0} cells`}
          testId="readiness-kpi-weak-cells"
        />
        <StatCard
          compact
          label="Open high/critical"
          value={String(summary.open_high_total ?? 0)}
          unit=""
          severity={(summary.open_high_total ?? 0) > 5 ? "critical" : "warning"}
          testId="readiness-kpi-open-high"
        />
        <StatCard
          compact
          label="Exposure in scope"
          value={fmtUSD(summary.total_exposure_usd)}
          unit=""
          severity="warning"
          testId="readiness-kpi-exposure"
        />
        <StatCard
          compact
          label="P0 queue"
          value={String(summary.p0_open ?? 0)}
          unit=""
          severity={(summary.p0_open ?? 0) > 0 ? "critical" : "success"}
          testId="readiness-kpi-p0"
        />
        {v2Enabled ? (
          <>
            <StatCard
              compact
              label="P1 queue"
              value={String(summary.p1_open ?? 0)}
              unit=""
              severity={(summary.p1_open ?? 0) > 0 ? "warning" : "success"}
              testId="readiness-kpi-p1"
            />
            <StatCard
              compact
              label="Cells ≥ 80%"
              value={String(summary.cells_above_80 ?? 0)}
              unit=""
              severity={(summary.cells_above_80 ?? 0) >= (summary.cell_count ?? 1) / 2 ? "success" : "warning"}
              subtle={`of ${summary.cell_count ?? 0} cells`}
              testId="readiness-kpi-strong-cells"
            />
            <StatCard
              compact
              label="Risk band"
              value={RISK_BAND_LABELS[summary.risk_band] || summary.risk_band || "—"}
              unit=""
              severity={
                summary.risk_band === "critical"
                  ? "critical"
                  : summary.risk_band === "elevated"
                    ? "warning"
                    : "default"
              }
              testId="readiness-kpi-risk-band"
            />
          </>
        ) : null}
      </div>

      {(detail?.correlated_kpis || []).length > 0 ? (
        <div className="grid grid-cols-2 gap-2 mb-6 md:grid-cols-5" data-testid="readiness-correlated-kpis">
          {detail.correlated_kpis.map((k) => (
            <Link
              key={k.id}
              to={hrefWithMasterParams(`/app/kpi/${encodeURIComponent(k.id)}`)}
              className="crt-card block rounded-sm border border-zinc-200 p-3 transition-colors hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
            >
              <div className="crt-overline text-muted-foreground">{KPI_LABELS[k.id] || k.id}</div>
              <div className="crt-num mt-1 text-lg font-semibold tabular-nums">
                {k.unit === "usd" ? fmtUSD(k.value) : k.unit === "pct" ? fmtPct(k.value) : String(k.value ?? "—")}
              </div>
            </Link>
          ))}
        </div>
      ) : null}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-6">
      {detail?.weakest_cell ? (
        <div className="rounded-sm border border-zinc-200 bg-zinc-50/80 p-4 dark:border-zinc-700 dark:bg-zinc-900/40" data-testid="readiness-weakest-cell">
          <div className="crt-overline text-muted-foreground">Weakest cell</div>
          <div className="mt-1 text-sm">
            <Link
              to={hrefWithMasterParams(
                `/app/cases?process=${encodeURIComponent(detail.weakest_cell.process)}&entity=${encodeURIComponent(detail.weakest_cell.entity)}`,
              )}
              className="font-medium text-primary hover:underline"
            >
              {detail.weakest_cell.process} · {detail.weakest_cell.entity}
            </Link>
            {" · "}
            <span className={cellTone(detail.weakest_cell)}>{fmtPct(detail.weakest_cell.readiness)}</span>
            {" · "}
            {detail.weakest_cell.open_high ?? 0} open high · {fmtUSD(detail.weakest_cell.exposure)}
          </div>
        </div>
      ) : null}
        {detail?.weakest_entity ? (
          <div className="rounded-sm border border-zinc-200 bg-zinc-50/80 p-4 dark:border-zinc-700 dark:bg-zinc-900/40" data-testid="readiness-weakest-entity">
            <div className="crt-overline text-muted-foreground">Weakest entity</div>
            <div className="mt-1 text-sm">
              <span className="font-medium">{detail.weakest_entity.entity}</span>
              {" · "}
              <span className={cellTone({ readiness: detail.weakest_entity.readiness })}>
                {fmtPct(detail.weakest_entity.readiness)}
              </span>
              <span className="text-muted-foreground"> · {detail.weakest_entity.cell_count} cells</span>
            </div>
          </div>
        ) : null}
        {detail?.weakest_process ? (
          <div className="rounded-sm border border-zinc-200 bg-zinc-50/80 p-4 dark:border-zinc-700 dark:bg-zinc-900/40" data-testid="readiness-weakest-process">
            <div className="crt-overline text-muted-foreground">Weakest process</div>
            <div className="mt-1 text-sm">
              <span className="font-medium">{detail.weakest_process.process}</span>
              {" · "}
              <span className={cellTone({ readiness: detail.weakest_process.readiness })}>
                {fmtPct(detail.weakest_process.readiness)}
              </span>
              <span className="text-muted-foreground"> · {detail.weakest_process.cell_count} cells</span>
            </div>
          </div>
        ) : null}
      </div>

      {v2Enabled && narrative ? (
        <SectionCard kicker="NARRATIVE" title="Executive insight" className="mb-6" bodyClassName="p-4" data-testid="readiness-narrative">
          {narrative.executive_snapshot ? (
            <p className="mb-3 text-sm text-foreground">{narrative.executive_snapshot}</p>
          ) : null}
          {(narrative.drivers || []).length > 0 ? (
            <ul className="mb-3 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
              {narrative.drivers.slice(0, 4).map((d, i) => (
                <li key={i}>{d}</li>
              ))}
            </ul>
          ) : null}
          {narrative.risk_band ? (
            <p className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">
              ML risk band: {RISK_BAND_LABELS[narrative.risk_band] || narrative.risk_band}
            </p>
          ) : null}
        </SectionCard>
      ) : null}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <SectionCard kicker="COMPONENTS" title="Portfolio drivers (avg %)" bodyClassName="p-4">
          <div className="h-48" data-testid="readiness-component-chart">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={componentBars} layout="vertical" margin={{ left: 8, right: 8 }}>
                <CartesianGrid stroke={RC_STROKE} strokeDasharray="3 3" />
                <XAxis type="number" domain={[0, 100]} tick={RC_TICK} />
                <YAxis type="category" dataKey="name" width={100} tick={RC_TICK} />
                <Tooltip contentStyle={rcTooltipStyle()} formatter={(v) => [`${v}%`, "Score"]} />
                <Bar dataKey="value" fill="hsl(var(--primary))" radius={[0, 2, 2, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>
        <SectionCard kicker="DISTRIBUTION" title="Readiness bands" bodyClassName="p-4">
          <div className="h-48" data-testid="readiness-distribution-chart">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={detail?.distribution || []}>
                <CartesianGrid stroke={RC_STROKE} strokeDasharray="3 3" />
                <XAxis dataKey="bucket" tick={RC_TICK} />
                <YAxis tick={RC_TICK} />
                <Tooltip contentStyle={rcTooltipStyle()} />
                <Bar dataKey="count" fill="hsl(var(--chart-3))" name="Cells" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </SectionCard>
        {v2Enabled && waterfallData.length > 1 ? (
          <SectionCard kicker="WATERFALL" title="Score bridge (component gaps)" bodyClassName="p-4">
            <div className="h-48" data-testid="readiness-waterfall-chart">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={waterfallData} margin={{ left: 8, right: 8, bottom: 48 }}>
                  <CartesianGrid stroke={RC_STROKE} strokeDasharray="3 3" />
                  <XAxis dataKey="label" tick={RC_TICK} interval={0} angle={-30} textAnchor="end" height={72} />
                  <YAxis domain={[0, 100]} tick={RC_TICK} tickFormatter={(v) => `${v}%`} />
                  <Tooltip contentStyle={rcTooltipStyle()} formatter={(v) => [`${v}%`, "Score"]} />
                  <Bar dataKey="value" fill="hsl(var(--chart-2))" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </SectionCard>
        ) : null}
      </div>

      {v2Enabled && extra && Object.keys(extra).length > 0 ? (
        <SectionCard kicker="DRIVERS" title="Portfolio driver metrics" className="mb-6" bodyClassName="p-4" data-testid="readiness-extra-metrics">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 mb-4">
            <StatCard label="Control pass %" value={fmtPct(extra.global_control_pass_pct)} unit="" severity="default" />
            <StatCard
              label="Overdue recons"
              value={String(extra.overdue_reconciliations_count ?? 0)}
              unit=""
              severity={(extra.overdue_reconciliations_count ?? 0) > 0 ? "warning" : "success"}
            />
            <StatCard
              label="Cases w/o evidence"
              value={String(extra.cases_without_evidence_count ?? 0)}
              unit=""
              severity={(extra.cases_without_evidence_count ?? 0) > 0 ? "warning" : "success"}
            />
            <StatCard
              label="Controls never run"
              value={String(extra.controls_never_run_count ?? 0)}
              unit=""
              severity={(extra.controls_never_run_count ?? 0) > 0 ? "critical" : "success"}
            />
          </div>
          {(extra.repeat_offenders || []).length > 0 ? (
            <DataTable testId="readiness-repeat-offenders" maxHeightClassName="max-h-40">
              <DataTableHead>
                <tr>
                  <DataTableTh>Control</DataTableTh>
                  <DataTableTh align="right">Exceptions</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {extra.repeat_offenders.map((r) => (
                  <DataTableRow key={r.code}>
                    <DataTableTd>
                      <Link
                        to={hrefWithMasterParams(`/app/drill/control/${encodeURIComponent(r.code)}`)}
                        className="text-primary hover:underline"
                      >
                        {r.code}
                      </Link>
                    </DataTableTd>
                    <DataTableTd align="right" className="tabular-nums">
                      {r.exceptions}
                    </DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          ) : null}
        </SectionCard>
      ) : null}

      <SectionCard
        kicker="TREND"
        title="8-week readiness & exposure"
        className="mb-6"
        bodyClassName="p-4"
        right={
          trendSourceLabel ? (
            <span className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground" data-testid="readiness-trend-source">
              {trendSourceLabel}
            </span>
          ) : null
        }
      >
        {trend?.note ? <p className="mb-2 text-sm text-muted-foreground">{trend.note}</p> : null}
        {chartData.length ? (
          <div className="h-64" data-testid="readiness-multi-trend-chart">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
                <CartesianGrid stroke={RC_STROKE} strokeDasharray="3 3" />
                <XAxis dataKey="period" tick={RC_TICK} tickLine={false} angle={-25} textAnchor="end" height={56} />
                <YAxis yAxisId="left" domain={[0, 100]} tick={RC_TICK} tickFormatter={(v) => `${v}%`} width={44} />
                <YAxis yAxisId="right" orientation="right" tick={RC_TICK} tickFormatter={(v) => (v >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : `${(v / 1000).toFixed(0)}k`)} width={48} />
                <Tooltip contentStyle={rcTooltipStyle()} />
                <ReferenceLine yAxisId="left" y={trend?.target_pct ?? 80} stroke="hsl(var(--chart-4))" strokeDasharray="4 4" label="Target" />
                {priorAnchorValue != null ? (
                  <ReferenceLine
                    yAxisId="left"
                    y={priorAnchorValue}
                    stroke="hsl(var(--muted-foreground))"
                    strokeDasharray="2 6"
                    label={{ value: `Prior ${priorAnchorValue}%`, position: "insideTopRight" }}
                  />
                ) : null}
                <Area yAxisId="left" type="monotone" dataKey="readiness" stroke="hsl(var(--primary))" fill="hsl(var(--primary)/0.12)" name="Readiness %" />
                <Line yAxisId="right" type="monotone" dataKey="exposure" stroke="hsl(var(--chart-3))" strokeWidth={1.5} dot={false} name="Exposure" />
                <Line yAxisId="left" type="monotone" dataKey="control_fail_count" stroke="hsl(var(--destructive))" strokeWidth={1} dot={false} name="Control fails" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No trend series for this scope.</p>
        )}
        {v2Enabled && componentTrendData.length > 0 ? (
          <div className="mt-6 border-t border-zinc-200 pt-4 dark:border-zinc-700">
            <div className="crt-overline mb-2 text-muted-foreground">Component trends (8-week)</div>
            <div className="h-52" data-testid="readiness-component-trend-chart">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={componentTrendData} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
                  <CartesianGrid stroke={RC_STROKE} strokeDasharray="3 3" />
                  <XAxis dataKey="period" tick={RC_TICK} tickLine={false} angle={-25} textAnchor="end" height={56} />
                  <YAxis domain={[0, 100]} tick={RC_TICK} tickFormatter={(v) => `${v}%`} width={44} />
                  <Tooltip contentStyle={rcTooltipStyle()} />
                  <Line type="monotone" dataKey="control_pct" stroke="hsl(var(--primary))" dot={false} name="Controls" />
                  <Line type="monotone" dataKey="recon_pct" stroke="hsl(var(--chart-3))" dot={false} name="Recon" />
                  <Line type="monotone" dataKey="evidence_pct" stroke="hsl(var(--chart-4))" dot={false} name="Evidence" />
                  <Line type="monotone" dataKey="issue_pct" stroke="hsl(var(--destructive))" dot={false} name="Issues" />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>
        ) : null}
      </SectionCard>

      {(detail?.movers?.top_deteriorators?.length > 0 || detail?.movers?.top_improvers?.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <SectionCard kicker="MOVERS" title={deterioratorTitle} bodyClassName="p-4">
            <ul className="space-y-2 text-sm" data-testid="readiness-deteriorators">
              {(detail.movers.top_deteriorators || []).map((r, i) => (
                <li key={`${r.entity}-${r.process}-${i}`}>
                  {r.process} · {r.entity} — <span className={cellTone(r)}>{fmtPct(r.readiness)}</span>
                  {r.delta_pts != null ? (
                    <span className="text-destructive"> ({r.delta_pts > 0 ? "+" : ""}{r.delta_pts} pts WoW)</span>
                  ) : null}
                </li>
              ))}
            </ul>
          </SectionCard>
          <SectionCard kicker="MOVERS" title={improverTitle} bodyClassName="p-4">
            <ul className="space-y-2 text-sm" data-testid="readiness-improvers">
              {(detail.movers.top_improvers || []).map((r, i) => (
                <li key={`${r.entity}-${r.process}-${i}`}>
                  {r.process} · {r.entity} — <span className={cellTone(r)}>{fmtPct(r.readiness)}</span>
                  {r.delta_pts != null ? (
                    <span className="text-[hsl(var(--chart-4))]"> ({r.delta_pts > 0 ? "+" : ""}{r.delta_pts} pts WoW)</span>
                  ) : null}
                </li>
              ))}
            </ul>
          </SectionCard>
        </div>
      )}

      {(detail?.alerts || []).length > 0 ? (
        <div className="mb-6 rounded-sm border border-amber-500/40 bg-amber-500/5 p-4" data-testid="readiness-alerts">
          <div className="crt-overline mb-2 text-amber-700 dark:text-amber-400">Threshold alerts</div>
          <ul className="space-y-1 text-sm">
            {detail.alerts.map((a) => (
              <li key={a.id}>
                {a.href ? (
                  <Link to={hrefWithMasterParams(a.href)} className="text-primary hover:underline">
                    {a.message}
                  </Link>
                ) : (
                  a.message
                )}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {v2Enabled && paginatedWeak?.items?.length > 0 ? (
        <SectionCard
          kicker="WEAK CELLS"
          title={`Cells below 60% (${paginatedWeak.total})`}
          className="mb-6"
          bodyClassName="p-4"
          data-testid="readiness-weak-cells-list"
        >
          <ul className="space-y-2 text-sm">
            {paginatedWeak.items.map((r, i) => (
              <li key={`${r.entity}-${r.process}-${i}`}>
                <button
                  type="button"
                  className="text-primary hover:underline"
                  onClick={() => onProcessSelect?.(r.process)}
                >
                  {r.process} · {r.entity}
                </button>
                {" — "}
                <span className={cellTone(r)}>{fmtPct(r.readiness)}</span>
              </li>
            ))}
          </ul>
          {paginatedWeak.has_more ? (
            <p className="mt-2 text-xs text-muted-foreground">
              Showing {paginatedWeak.offset + 1}–{paginatedWeak.offset + paginatedWeak.items.length} of{" "}
              {paginatedWeak.total}
            </p>
          ) : null}
        </SectionCard>
      ) : null}

      <SectionCard
        kicker="MATRIX"
        title="Cell detail"
        className="mb-6"
        right={
          <div className="flex flex-wrap items-center gap-2">
            <label className="crt-num flex items-center gap-2 text-[10px] uppercase tracking-wider text-muted-foreground">
              <input type="checkbox" checked={weakOnly} onChange={(e) => setWeakOnly(e.target.checked)} data-testid="readiness-weak-only" />
              Weak only (&lt;60%)
            </label>
            <select
              value={matrixSort}
              onChange={(e) => setMatrixSort(e.target.value)}
              className="crt-num rounded-sm border border-zinc-300 bg-white px-2 py-1 text-[10px] uppercase dark:border-zinc-600 dark:bg-zinc-900"
              data-testid="readiness-matrix-sort"
            >
              <option value="readiness_asc">Readiness ↑</option>
              <option value="readiness_desc">Readiness ↓</option>
              <option value="exposure_desc">Exposure ↓</option>
            </select>
          </div>
        }
      >
        <DataTable testId="readiness-matrix-table" maxHeightClassName="max-h-80">
          <DataTableHead>
            <tr>
              <DataTableTh>Entity</DataTableTh>
              <DataTableTh>Process</DataTableTh>
              <DataTableTh align="right">Readiness</DataTableTh>
              <DataTableTh align="right">Control</DataTableTh>
              <DataTableTh align="right">Recon</DataTableTh>
              <DataTableTh align="right">Evidence</DataTableTh>
              <DataTableTh align="right">Issues</DataTableTh>
              <DataTableTh align="right">Open high</DataTableTh>
              <DataTableTh align="right">Exposure</DataTableTh>
            </tr>
          </DataTableHead>
          <DataTableBody>
            {filteredHeatmap.map((r) => (
              <DataTableRow key={`${r.entity}-${r.process}`}>
                <DataTableTd>{r.entity}</DataTableTd>
                <DataTableTd>{r.process}</DataTableTd>
                <DataTableTd align="right" className={clsx("tabular-nums", cellTone(r))}>
                  {fmtPct(r.readiness)}
                </DataTableTd>
                <DataTableTd align="right" className="tabular-nums text-muted-foreground">
                  {fmtPct((r.control_component ?? 0) * 100)}
                </DataTableTd>
                <DataTableTd align="right" className="tabular-nums text-muted-foreground">
                  {fmtPct((r.recon_component ?? 0) * 100)}
                </DataTableTd>
                <DataTableTd align="right" className="tabular-nums text-muted-foreground">
                  {fmtPct((r.evidence_component ?? 0) * 100)}
                </DataTableTd>
                <DataTableTd align="right" className="tabular-nums text-muted-foreground">
                  {fmtPct((r.issue_component ?? 0) * 100)}
                </DataTableTd>
                <DataTableTd align="right" className="tabular-nums">
                  {r.open_high ?? 0}
                </DataTableTd>
                <DataTableTd align="right" className="tabular-nums">
                  {fmtUSD(r.exposure)}
                </DataTableTd>
              </DataTableRow>
            ))}
          </DataTableBody>
        </DataTable>
      </SectionCard>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <SectionCard kicker="CONTROLS" title="Top failing controls" bodyClassName="p-4">
          <DataTable testId="readiness-failing-controls">
            <DataTableHead>
              <tr>
                <DataTableTh>Code</DataTableTh>
                <DataTableTh>Process</DataTableTh>
                <DataTableTh align="right">Exceptions</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {(detail?.top_failing_controls || []).map((c) => (
                <DataTableRow key={c.code}>
                  <DataTableTd>
                    <Link to={hrefWithMasterParams(`/app/drill/control/${encodeURIComponent(c.code)}`)} className="text-primary hover:underline">
                      {c.code}
                    </Link>
                  </DataTableTd>
                  <DataTableTd>{c.process}</DataTableTd>
                  <DataTableTd align="right" className="tabular-nums">
                    {c.exceptions}
                  </DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>
        <SectionCard kicker="RISKS" title="Top open risks" bodyClassName="p-4">
          <DataTable testId="readiness-top-risks">
            <DataTableHead>
              <tr>
                <DataTableTh>Title</DataTableTh>
                <DataTableTh>Severity</DataTableTh>
                <DataTableTh align="right">Exposure</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {(detail?.top_risks || []).slice(0, 10).map((r) => (
                <DataTableRow key={r.id}>
                  <DataTableTd>
                    <Link to={hrefWithMasterParams(`/app/evidence/${encodeURIComponent(r.id)}`)} className="text-primary hover:underline line-clamp-1">
                      {r.title || r.id}
                    </Link>
                  </DataTableTd>
                  <DataTableTd>{r.severity}</DataTableTd>
                  <DataTableTd align="right" className="tabular-nums">
                    {fmtUSD(r.financial_exposure)}
                  </DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>
      </div>

      {(detail?.recommended_actions || []).length > 0 ? (
        <SectionCard kicker="ACTIONS" title="Recommended next steps" className="mb-6" bodyClassName="p-4">
          <ul className="list-disc space-y-2 pl-5 text-sm text-muted-foreground" data-testid="readiness-recommended-actions">
            {detail.recommended_actions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </SectionCard>
      ) : null}

      <SectionCard kicker="DRILL" title="Contributing records" bodyClassName="p-4">
        {!(drilldown?.refs?.length > 0) ? (
          <p className="text-sm text-muted-foreground">No structured refs in this scope.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {drilldown.refs.map((r, idx) => {
              const rowHref = refRowHref(r);
              return (
                <li key={`${r.type}-${r.id ?? idx}`} className="flex flex-wrap gap-2 border-b border-zinc-100 pb-2 dark:border-zinc-800">
                  <span className="crt-num text-[10px] uppercase text-muted-foreground">{r.type}</span>
                  {rowHref ? (
                    <Link to={rowHref} className="text-primary hover:underline">
                      {r.label || r.id}
                    </Link>
                  ) : (
                    <span>{r.label || r.id}</span>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </SectionCard>
    </div>
  );
}
