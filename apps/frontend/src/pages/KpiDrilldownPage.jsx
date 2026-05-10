import React, { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { http } from "../lib/api";
import { ArrowLeft } from "@phosphor-icons/react";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { pathForRelatedType } from "../lib/drillPaths";

export default function KpiDrilldownPage() {
  const { kpiId } = useParams();
  const { entityCode, hrefWithMasterParams } = useMastersFilters();
  const [defRow, setDefRow] = useState(null);
  const [trend, setTrend] = useState(null);
  const [drilldown, setDrilldown] = useState(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  const dashboardParams = useDashboardFilterParams();
  const load = useCallback(async () => {
    if (!kpiId) return;
    setLoading(true);
    setFailed(false);
    try {
      const [defsRes, trendRes, drillRes] = await Promise.all([
        http.get("/kpi/definitions"),
        http.get(`/kpi/trend/${encodeURIComponent(kpiId)}`, { params: dashboardParams }),
        http.get(`/kpi/drilldown/${encodeURIComponent(kpiId)}`, { params: dashboardParams }),
      ]);
      const items = defsRes.data?.items || [];
      setDefRow(items.find((x) => x.id === kpiId) || null);
      setTrend(trendRes.data);
      setDrilldown(drillRes.data);
    } catch (_e) {
      setFailed(true);
      toast.error("Failed to load KPI drill-down");
    } finally {
      setLoading(false);
    }
  }, [kpiId, dashboardParams]);

  useEffect(() => {
    load();
  }, [load]);

  const backCfo = hrefWithMasterParams("/app/cfo");
  const moduleHref = defRow?.drill_path ? hrefWithMasterParams(defRow.drill_path) : null;

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
    <PageShell maxWidth="max-w-[960px]" className="">
      <div data-testid="kpi-drill-page">
        <PageHeader
          kicker="CFO · KPI DRILL-DOWN"
          title={defRow?.label || kpiId.replaceAll("_", " ")}
          subtitle={
            <>
              Scoped to reporting context ({entityCode || "all entities"})
              {defRow?.description ? ` · ${defRow.description}` : null}
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

        <MastersFilterStrip className="mb-6" />

        {loading ? (
          <div className="crt-overline text-muted-foreground" data-testid="kpi-drill-loading">
            Loading KPI context…
          </div>
        ) : failed ? (
          <div className="rounded-sm border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive" data-testid="kpi-drill-error">
            Could not load this KPI. Check your session and try again.
            <button
              type="button"
              onClick={() => load()}
              className="crt-num ml-4 underline underline-offset-2"
            >
              Retry
            </button>
          </div>
        ) : (
          <>
            {moduleHref ? (
              <p className="crt-num mb-4 text-[11px] uppercase tracking-wider text-muted-foreground">
                <Link to={moduleHref} className="text-primary hover:underline" data-testid="kpi-module-link">
                  Open in module surface →
                </Link>
              </p>
            ) : null}

            <SectionCard
              kicker="TREND"
              title="Series"
              className="mb-6"
              bodyClassName="p-4 text-sm text-muted-foreground"
            >
              {trend?.note ? <p>{trend.note}</p> : null}
              {Array.isArray(trend?.series) && trend.series.length ? (
                <pre className="crt-num mt-2 max-h-48 overflow-auto rounded-sm bg-zinc-50 p-3 text-[11px] dark:bg-zinc-900">
                  {JSON.stringify(trend.series.slice(0, 8), null, 2)}
                  {trend.series.length > 8 ? "\n…" : ""}
                </pre>
              ) : trend?.note ? null : (
                <p data-testid="kpi-drill-empty-trend">No trend series for this KPI in the current slice.</p>
              )}
            </SectionCard>

            <SectionCard
              kicker="DRILL"
              title="Contributing refs"
              bodyClassName="p-4"
            >
              {!(drilldown?.refs?.length > 0) ? (
                <p className="text-sm text-muted-foreground" data-testid="kpi-drill-empty-refs">
                  No structured refs for this KPI yet — use the module link above or CFO cockpit exports.
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
