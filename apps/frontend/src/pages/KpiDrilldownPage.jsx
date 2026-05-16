import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { LineChart, Line, ResponsiveContainer, XAxis, YAxis, CartesianGrid, Tooltip } from "recharts";
import { http } from "../lib/api";
import { ArrowLeft } from "@phosphor-icons/react";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import AuditReadinessDrillDetail from "../components/kpi/AuditReadinessDrillDetail";
import { pathForRelatedType } from "../lib/drillPaths";
import { fmtUSD, fmtPct } from "../lib/format";
import { RC_STROKE, RC_TICK, rcTooltipStyle } from "../lib/rechartsTheme";

const AUDIT_READINESS_ID = "audit_readiness_pct";

function normalizeTrendPoints(raw) {
  if (!Array.isArray(raw)) return [];
  return raw
    .map((pt) => {
      const period = pt.period || pt.week || "";
      const value =
        typeof pt.value === "number"
          ? pt.value
          : typeof pt.readiness === "number"
            ? pt.readiness
            : parseFloat(pt.value ?? pt.readiness ?? "NaN");
      return { period: String(period), value: Number.isFinite(value) ? value : 0 };
    })
    .filter((r) => r.period);
}

export default function KpiDrilldownPage() {
  const { kpiId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const { entityCode, hrefWithMasterParams } = useMastersFilters();
  const [defRow, setDefRow] = useState(null);
  const [trend, setTrend] = useState(null);
  const [drilldown, setDrilldown] = useState(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  const processFilter = searchParams.get("process") || "all";
  const isAuditReadiness = kpiId === AUDIT_READINESS_ID || kpiId === "readiness";

  const dashboardParams = useDashboardFilterParams();
  const apiParams = useMemo(
    () => ({
      ...dashboardParams,
      ...(processFilter !== "all" ? { process: processFilter } : {}),
    }),
    [dashboardParams, processFilter],
  );

  const load = useCallback(async () => {
    if (!kpiId) return;
    setLoading(true);
    setFailed(false);
    try {
      const kid = kpiId === "readiness" ? AUDIT_READINESS_ID : kpiId;
      const [defsRes, trendRes, drillRes] = await Promise.all([
        http.get("/kpi/definitions"),
        http.get(`/kpi/trend/${encodeURIComponent(kid)}`, { params: apiParams }),
        http.get(`/kpi/drilldown/${encodeURIComponent(kid)}`, { params: apiParams }),
      ]);
      const items = defsRes.data?.items || [];
      setDefRow(items.find((x) => x.id === kid || x.id === kpiId) || null);
      setTrend(trendRes.data);
      setDrilldown(drillRes.data);
    } catch (_e) {
      setFailed(true);
      toast.error("Failed to load KPI drill-down");
    } finally {
      setLoading(false);
    }
  }, [kpiId, apiParams]);

  useEffect(() => {
    load();
  }, [load]);

  const processes = useMemo(() => {
    const hm = drilldown?.detail?.heatmap;
    if (!hm?.length) return [];
    return [...new Set(hm.map((r) => r.process))].sort();
  }, [drilldown]);

  const backCfo = hrefWithMasterParams("/app/cfo");
  const moduleHref = defRow?.drill_path ? hrefWithMasterParams(defRow.drill_path) : null;

  const chartData = useMemo(() => normalizeTrendPoints(trend?.series), [trend]);

  const valueKind = trend?.value_kind || (defRow?.unit === "usd" ? "usd" : defRow?.unit === "count" ? "count" : "pct");

  const formatValue = useCallback(
    (v) => {
      const n = typeof v === "number" ? v : parseFloat(v);
      if (!Number.isFinite(n)) return "—";
      if (valueKind === "usd" || defRow?.unit === "usd") return fmtUSD(n);
      if (valueKind === "pct" || defRow?.unit === "pct") return fmtPct(n);
      return String(Math.round(n));
    },
    [defRow?.unit, valueKind],
  );

  const latestValue = isAuditReadiness
    ? drilldown?.detail?.summary?.current ?? (chartData.length ? chartData[chartData.length - 1].value : null)
    : chartData.length
      ? chartData[chartData.length - 1].value
      : null;

  const refRowHref = (r) => {
    if (!r) return null;
    if (r.type === "close_task" && r.cycle_id) {
      return hrefWithMasterParams(`/app/finance-operations/month-end-close/${encodeURIComponent(r.cycle_id)}`);
    }
    const p = pathForRelatedType(r.type, r.id);
    return p ? hrefWithMasterParams(p) : null;
  };

  if (!kpiId) {
    return (
      <PageShell>
        <PageHeader kicker="KPI" title="Missing KPI id" subtitle="Navigate from the CFO cockpit hero band." />
      </PageShell>
    );
  }

  return (
    <PageShell maxWidth={isAuditReadiness ? "max-w-[1600px]" : "max-w-[960px]"} className="">
      <div data-testid="kpi-drill-page">
        <PageHeader
          kicker="CFO · KPI DRILL-DOWN"
          title={defRow?.label || kpiId.replaceAll("_", " ")}
          subtitle={
            <>
              Scoped to reporting context ({entityCode || "all entities"})
              {processFilter !== "all" ? ` · ${processFilter}` : null}
              {defRow?.description ? ` · ${defRow.description}` : null}
              {latestValue != null && Number.isFinite(latestValue) ? (
                <span className="block mt-1 font-mono text-sm text-foreground">
                  {isAuditReadiness ? "Current readiness" : "Latest (series end)"}: {formatValue(latestValue)}
                </span>
              ) : null}
            </>
          }
          right={
            <Link
              to={backCfo}
              className="inline-flex items-center gap-2 rounded-sm border border-zinc-300 bg-white px-3 py-2 text-xs font-medium uppercase tracking-wider text-zinc-600 shadow-none hover:bg-zinc-50 dark:border-zinc-600 dark:bg-zinc-900 dark:hover:bg-zinc-800"
              data-testid="kpi-back-cfo"
            >
              <ArrowLeft size={14} /> CFO cockpit
            </Link>
          }
        />

        <MastersFilterStrip className="mb-4" />

        {isAuditReadiness && processes.length > 0 ? (
          <div className="mb-6 flex flex-wrap items-center gap-2">
            <span className="crt-overline text-muted-foreground">Process</span>
            <select
              value={processFilter}
              onChange={(e) => {
                const v = e.target.value;
                const next = new URLSearchParams(searchParams);
                if (v === "all") next.delete("process");
                else next.set("process", v);
                setSearchParams(next, { replace: true });
              }}
              className="crt-num rounded-sm border border-zinc-300 bg-white px-2 py-2 text-xs uppercase tracking-wider dark:border-zinc-600 dark:bg-zinc-900"
              data-testid="readiness-process-filter"
            >
              <option value="all">All processes</option>
              {processes.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </div>
        ) : null}

        {loading ? (
          <div className="crt-overline text-muted-foreground" data-testid="kpi-drill-loading">
            Loading KPI context…
          </div>
        ) : failed ? (
          <div className="rounded-sm border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive" data-testid="kpi-drill-error">
            Could not load this KPI. Check your session and try again.
            <button type="button" onClick={() => load()} className="crt-num ml-4 underline underline-offset-2">
              Retry
            </button>
          </div>
        ) : isAuditReadiness && drilldown?.detail ? (
          <AuditReadinessDrillDetail
            detail={drilldown.detail}
            trend={trend}
            drilldown={drilldown}
            dashboardParams={apiParams}
            hrefWithMasterParams={hrefWithMasterParams}
            onReload={load}
            moduleHref={moduleHref}
            onProcessSelect={(processName) => {
              const next = new URLSearchParams(searchParams);
              if (processName) next.set("process", processName);
              else next.delete("process");
              setSearchParams(next, { replace: true });
            }}
          />
        ) : (
          <>
            {moduleHref ? (
              <p className="crt-num mb-4 text-[11px] uppercase tracking-wider text-muted-foreground">
                <Link to={moduleHref} className="text-primary hover:underline" data-testid="kpi-module-link">
                  Open in module surface →
                </Link>
              </p>
            ) : null}

            <SectionCard kicker="TREND" title="Series (scoped)" className="mb-6" bodyClassName="p-4">
              {trend?.note ? <p className="mb-2 text-sm text-muted-foreground">{trend.note}</p> : null}
              {chartData.length ? (
                <div className="h-64 w-full" data-testid="kpi-trend-chart">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
                      <CartesianGrid stroke={RC_STROKE} strokeDasharray="3 3" />
                      <XAxis dataKey="period" tick={RC_TICK} tickLine={false} interval={0} angle={-25} textAnchor="end" height={56} />
                      <YAxis
                        dataKey="value"
                        tick={RC_TICK}
                        tickLine={false}
                        tickFormatter={(v) => {
                          if (valueKind === "usd") return v >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : `${(v / 1000).toFixed(0)}k`;
                          if (valueKind === "pct") return `${v}%`;
                          return String(Math.round(v));
                        }}
                        width={44}
                      />
                      <Tooltip
                        contentStyle={rcTooltipStyle()}
                        formatter={(v) => [formatValue(v), "Value"]}
                        labelFormatter={(l) => String(l)}
                      />
                      <Line type="monotone" dataKey="value" stroke="hsl(var(--primary))" strokeWidth={2} dot={{ r: 3 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ) : trend?.note ? null : (
                <p className="text-sm text-muted-foreground" data-testid="kpi-drill-empty-trend">
                  No trend series for this KPI in the current slice.
                </p>
              )}
            </SectionCard>

            <SectionCard kicker="DRILL" title="Contributing records" bodyClassName="p-4">
              {!(drilldown?.refs?.length > 0) ? (
                <p className="text-sm text-muted-foreground" data-testid="kpi-drill-empty-refs">
                  No structured refs for this KPI in the current reporting context. Try broadening entity/period filters or
                  use the module link above.
                </p>
              ) : (
                <ul className="space-y-2 text-sm">
                  {drilldown.refs.map((r, idx) => {
                    const rowHref = refRowHref(r);
                    const key = `${r.type}-${r.id ?? idx}`;
                    return (
                      <li
                        key={key}
                        className="flex flex-wrap items-baseline gap-2 border-b border-zinc-100 pb-2 dark:border-zinc-800"
                        data-testid={`kpi-drill-ref-${idx}`}
                      >
                        <span className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">{r.type}</span>
                        {rowHref ? (
                          <Link to={rowHref} className="text-primary hover:underline" data-testid={`kpi-drill-ref-link-${idx}`}>
                            {r.label || r.id}
                          </Link>
                        ) : (
                          <span className="text-foreground">{r.label || r.id}</span>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </SectionCard>
          </>
        )}
      </div>
    </PageShell>
  );
}
