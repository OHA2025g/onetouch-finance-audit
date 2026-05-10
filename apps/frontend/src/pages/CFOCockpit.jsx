import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { http } from "../lib/api";
import { StatCard } from "../components/StatCard";
import { SeverityBadge } from "../components/Badges";
import { fmtUSD, fmtPct, fmtDate } from "../lib/format";
import { LineChart, Line, ResponsiveContainer, XAxis, YAxis, CartesianGrid, Tooltip, AreaChart, Area } from "recharts";
import { ArrowRight, Download, ArrowsClockwise, Sparkle, FunnelSimple, X } from "@phosphor-icons/react";
import { toast } from "sonner";
import clsx from "clsx";
import InsightPanel from "../components/InsightPanel";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { RC_STROKE, RC_TICK, rcTooltipStyle } from "../lib/rechartsTheme";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import ReadinessHeatmap from "../components/ReadinessHeatmap";

/** Label fallback when a CFO hero row lacks a stable KPI id */
const CFO_HERO_LABEL_TO_KPI_ID = {
  "Audit readiness": "audit_readiness_pct",
  "Unresolved exposure": "unresolved_high_risk_exposure",
  "High/critical cases": "high_critical_open_cases",
  "Repeat findings": "repeat_finding_rate_pct",
  "Evidence completeness": "evidence_completeness_pct",
  "Remediation SLA": "remediation_sla_pct",
};

function resolveCfoHeroKpiId(row) {
  const raw = row?.id ?? row?.kpi_id;
  if (typeof raw === "string" && raw.trim()) return raw.trim();
  if (typeof raw === "number" && Number.isFinite(raw)) return String(raw);
  return (row?.label && CFO_HERO_LABEL_TO_KPI_ID[row.label]) || "";
}

export default function CFOCockpit() {
  const [data, setData] = useState(null);
  const [kpiSummary, setKpiSummary] = useState(null);
  const [actionQueue, setActionQueue] = useState(null);
  const [loading, setLoading] = useState(true);
  const [bootError, setBootError] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [processFilter, setProcessFilter] = useState("all");
  const [heroReorderMode, setHeroReorderMode] = useState(false);
  const [heroOrder, setHeroOrder] = useState(null); // string[] of KPI ids
  const { entityCode, periodExplicit, departmentId, costCenterId, hrefWithMasterParams } = useMastersFilters();
  const nav = useNavigate();
  const firstLoadRef = useRef(true);

  const heroOrderStorageKey = useMemo(() => {
    try {
      const raw = localStorage.getItem("ota_user");
      const u = raw ? JSON.parse(raw) : null;
      const email = typeof u?.email === "string" ? u.email : "anon";
      return `ota_cfo_hero_order_v1::${email}`;
    } catch {
      return "ota_cfo_hero_order_v1::anon";
    }
  }, []);

  const dashboardParams = useDashboardFilterParams();

  const load = useCallback(async () => {
    if (firstLoadRef.current) setLoading(true);
    try {
      const [cfoRes, defsRes, kpiRes] = await Promise.all([
        http.get("/dashboard/cfo", { params: dashboardParams }),
        http.get("/kpi/definitions"),
        http.get("/kpi/cfo-summary", { params: dashboardParams }),
      ]);
      const d = cfoRes.data;
      setBootError(false);
      setData(d);
      // Keep definitions request for forward-compat (catalog/drill metadata), but this page renders from summary.
      void defsRes;
      setKpiSummary(kpiRes.data || null);
      // Slice 3 — Action queue: refresh materialized items, then render top few.
      http
        .get("/cfo/action-queue", { params: { ...dashboardParams, refresh: true, limit: 6 } })
        .then((r) => setActionQueue(r.data))
        .catch(() => {});
    } catch (_e) {
      setBootError(true);
      toast.error("Failed to load CFO data");
    } finally {
      if (firstLoadRef.current) {
        setLoading(false);
        firstLoadRef.current = false;
      }
    }
  }, [dashboardParams]);

  useEffect(() => {
    load();
  }, [load]);

  const runAll = async () => {
    setRefreshing(true);
    try {
      const { data: r } = await http.post("/controls/run-all");
      toast.success(`Re-ran ${r.runs.length} controls · ${r.total_exceptions} exceptions`);
      await load();
    } catch (_e) { toast.error("Run failed"); }
    setRefreshing(false);
  };

  const exportPack = useCallback(
    async (format) => {
      try {
        const resp = await http.get(`/reports/audit-committee-pack.${format}`, {
          params: dashboardParams,
          responseType: "blob",
        });
        const blob = new Blob([resp.data]);
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `audit-committee-pack.${format}`;
        a.click();
        URL.revokeObjectURL(url);
        const scoped =
          !!(dashboardParams.entity_code ||
          dashboardParams.period_ym ||
          dashboardParams.department_id ||
          dashboardParams.cost_center_id);
        toast.success(
          scoped ? `Downloaded scoped ${format.toUpperCase()} pack (Phase 13)` : `Downloaded ${format.toUpperCase()} pack`,
        );
      } catch {
        toast.error(`Export ${format} failed`);
      }
    },
    [dashboardParams],
  );

  const entityFilter = entityCode || "all";

  const processes = useMemo(() => {
    const hm = data?.heatmap;
    if (!hm?.length) return [];
    return [...new Set(hm.map((r) => r.process))].sort();
  }, [data]);

  const filteredHeatmap = useMemo(() => {
    const hm = data?.heatmap;
    if (!hm?.length) return [];
    return hm.filter((r) => processFilter === "all" || r.process === processFilter);
  }, [data, processFilter]);

  const filteredTopRisks = useMemo(() => {
    if (!data?.top_risks) return [];
    return data.top_risks.filter((r) => processFilter === "all" || r.process === processFilter).slice(0, 10);
  }, [data, processFilter]);

  const hero = useMemo(() => {
    const k = data?.kpis || {};
    if ((kpiSummary?.kpis || []).length) return kpiSummary.kpis;
    // Default hero tiles (stable IDs) when KPI summary is unavailable.
    return [
      {
        id: "audit_readiness_pct",
        label: "Audit readiness",
        unit: "pct",
        value: k.audit_readiness_pct,
        severity: k.audit_readiness_pct >= 80 ? "success" : k.audit_readiness_pct >= 60 ? "warning" : "critical",
        drill_path: "/app/readiness",
      },
      {
        id: "unresolved_high_risk_exposure",
        label: "Unresolved exposure",
        unit: "usd",
        value: k.unresolved_high_risk_exposure,
        severity: "critical",
        drill_path: "/app/cases?status=open",
      },
      {
        id: "high_critical_open_cases",
        label: "High/critical cases",
        unit: "count",
        value: k.high_critical_open_cases,
        severity: k.high_critical_open_cases > 5 ? "critical" : "warning",
        drill_path: "/app/cases?status=open&severity=critical",
      },
      {
        id: "repeat_finding_rate_pct",
        label: "Repeat findings",
        unit: "pct",
        value: k.repeat_finding_rate_pct,
        severity: k.repeat_finding_rate_pct > 30 ? "warning" : "success",
        drill_path: "/app/audit",
      },
      {
        id: "evidence_completeness_pct",
        label: "Evidence completeness",
        unit: "pct",
        value: k.evidence_completeness_pct,
        severity: null,
        drill_path: "/app/evidence",
      },
      {
        id: "remediation_sla_pct",
        label: "Remediation SLA",
        unit: "pct",
        value: k.remediation_sla_pct,
        severity: k.remediation_sla_pct >= 85 ? "success" : "warning",
        drill_path: "/app/cases",
      },
    ];
  }, [data, kpiSummary]);

  const heroById = useMemo(() => {
    const m = new Map();
    for (const row of hero) {
      const id = resolveCfoHeroKpiId(row) || row.id || row.label;
      if (id) m.set(String(id), row);
    }
    return m;
  }, [hero]);

  // Initialize order from localStorage once data is available.
  useEffect(() => {
    if (!heroById.size) return;
    if (heroOrder != null) return;
    try {
      const raw = localStorage.getItem(heroOrderStorageKey);
      const parsed = raw ? JSON.parse(raw) : null;
      const arr = Array.isArray(parsed) ? parsed.map(String) : [];
      const valid = arr.filter((id) => heroById.has(id));
      const missing = [...heroById.keys()].filter((id) => !valid.includes(id));
      setHeroOrder([...valid, ...missing]);
    } catch {
      setHeroOrder([...heroById.keys()]);
    }
  }, [heroById, heroOrder, heroOrderStorageKey]);

  const orderedHero = useMemo(() => {
    if (!heroById.size) return hero;
    const order = Array.isArray(heroOrder) && heroOrder.length ? heroOrder : [...heroById.keys()];
    const out = [];
    for (const id of order) {
      const row = heroById.get(id);
      if (row) out.push(row);
    }
    // Safety: preserve any unexpected extra rows
    if (out.length < hero.length) {
      const seen = new Set(out.map((r) => resolveCfoHeroKpiId(r) || r.id || r.label));
      for (const r of hero) {
        const id = resolveCfoHeroKpiId(r) || r.id || r.label;
        if (!seen.has(id)) out.push(r);
      }
    }
    return out;
  }, [hero, heroById, heroOrder]);

  const persistHeroOrder = useCallback((next) => {
    setHeroOrder(next);
    try {
      localStorage.setItem(heroOrderStorageKey, JSON.stringify(next));
    } catch {
      // ignore
    }
  }, [heroOrderStorageKey]);

  const moveHero = useCallback((id, dir) => {
    const order = Array.isArray(heroOrder) && heroOrder.length ? [...heroOrder] : [...heroById.keys()];
    const idx = order.indexOf(id);
    if (idx < 0) return;
    const nextIdx = dir === "up" ? idx - 1 : idx + 1;
    if (nextIdx < 0 || nextIdx >= order.length) return;
    const tmp = order[idx];
    order[idx] = order[nextIdx];
    order[nextIdx] = tmp;
    persistHeroOrder(order);
  }, [heroById, heroOrder, persistHeroOrder]);

  if (loading) {
    return (
      <div
        className="crt-overline p-8 text-muted-foreground"
        data-testid="cfo-loading"
      >
        Loading command center…
      </div>
    );
  }

  if (bootError || !data) {
    return (
      <PageShell maxWidth="max-w-[960px]" className="">
        <PageHeader kicker="CFO · COMMAND CENTER" title="Could not load cockpit" subtitle="Check connectivity and retry." />
        <div className="rounded-sm border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive" data-testid="cfo-error">
          Failed to load CFO dashboard data.
          <button
            type="button"
            onClick={() => {
              firstLoadRef.current = true;
              load();
            }}
            className="crt-num ml-4 underline underline-offset-2"
          >
            Retry
          </button>
        </div>
      </PageShell>
    );
  }

  const k = data.kpis || {};

  return (
    <PageShell maxWidth="max-w-[1600px]" className="" >
      <div data-testid="cfo-cockpit">
        <PageHeader
          kicker="CFO · COMMAND CENTER"
          title="Audit readiness"
          subtitle={
            <>
              Enterprise view · {fmtDate(new Date().toISOString())} ·{" "}
              {entityFilter === "all" ? "all entities" : entityFilter}
              {processFilter !== "all" ? ` · ${processFilter}` : ""}
            </>
          }
          right={
            <>
              <Link
                to={hrefWithMasterParams("/app/audit-committee")}
                className="hidden items-center gap-2 rounded-sm border border-zinc-300 bg-white px-3 py-2 text-xs font-medium uppercase tracking-wider text-zinc-600 shadow-none transition-colors hover:bg-zinc-50 sm:inline-flex dark:border-zinc-600 dark:bg-zinc-100 dark:text-zinc-700 dark:hover:bg-white"
                data-testid="cfo-audit-committee-link"
              >
                Audit committee
              </Link>
              <Link
                to={hrefWithMasterParams("/app/risk-intelligence")}
                className="hidden items-center gap-2 rounded-sm border border-zinc-300 bg-white px-3 py-2 text-xs font-medium uppercase tracking-wider text-zinc-600 shadow-none transition-colors hover:bg-zinc-50 sm:inline-flex dark:border-zinc-600 dark:bg-zinc-100 dark:text-zinc-700 dark:hover:bg-white"
                data-testid="cfo-risk-intelligence-link"
              >
                Risk intelligence
              </Link>
              <button
                type="button"
                onClick={() => setFiltersOpen(true)}
                className="flex items-center gap-2 rounded-sm border border-zinc-300 bg-white px-3 py-2 text-xs font-medium uppercase tracking-wider text-zinc-600 shadow-none transition-colors hover:bg-zinc-50 lg:hidden dark:border-zinc-600 dark:bg-zinc-100 dark:text-zinc-700 dark:hover:bg-white"
                data-testid="mobile-filters-btn"
              >
                <FunnelSimple size={12} /> Filters
              </button>
              <button
                data-testid="run-all-btn"
                onClick={runAll}
                disabled={refreshing}
                className="flex items-center gap-2 rounded-sm border border-zinc-300 bg-white px-3 py-2 text-xs font-medium uppercase tracking-wider text-zinc-600 shadow-none transition-colors hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-600 dark:bg-zinc-100 dark:text-zinc-700 dark:hover:bg-white"
              >
                <ArrowsClockwise size={12} className={clsx(refreshing && "animate-spin")} /> Run all controls
              </button>
              <button
                data-testid="export-xlsx-btn"
                onClick={() => exportPack("xlsx")}
                className="flex items-center gap-2 rounded-sm border border-primary bg-primary px-3 py-2 text-xs font-medium uppercase tracking-wider text-white shadow-none transition-opacity hover:opacity-90"
              >
                <Download size={12} /> XLSX
              </button>
              <button
                data-testid="export-pack-btn"
                onClick={() => exportPack("pdf")}
                className="flex items-center gap-2 rounded-sm border border-primary bg-primary px-4 py-2 text-xs font-medium uppercase tracking-wider text-white shadow-none transition-opacity hover:opacity-90"
              >
                <Download size={12} /> Export PDF
              </button>
            </>
          }
        />

        <MastersFilterStrip className="mb-4" />
        {(entityCode || periodExplicit || departmentId || costCenterId) && (
          <p className="crt-num mb-4 text-[10px] uppercase tracking-wider text-muted-foreground">
            KPIs and server lists below follow this reporting context (Phase 12).
          </p>
        )}

        {/* Process-only facet (heatmap / top risks are still multi-entity in payload; this narrows the view client-side). */}
        <div className="mb-6 hidden flex-wrap items-center gap-2 lg:flex">
          <span className="crt-overline inline-flex h-9 items-center rounded-sm border border-zinc-200 bg-white px-3 text-muted-foreground dark:border-zinc-700 dark:bg-zinc-900/60">
            Process view
          </span>
          <select
            value={processFilter}
            onChange={(e) => setProcessFilter(e.target.value)}
            className="crt-num h-9 rounded-sm border border-zinc-300 bg-white px-3 text-xs uppercase tracking-wider text-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100"
            data-testid="process-filter"
          >
          <option value="all">All processes</option>
          {processes.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
          {processFilter !== "all" && (
            <button
              type="button"
              onClick={() => setProcessFilter("all")}
              className="crt-num h-9 rounded-sm border border-zinc-300 bg-white px-4 text-xs uppercase tracking-wider text-muted-foreground transition-colors hover:bg-zinc-50 hover:text-foreground dark:border-zinc-600 dark:bg-zinc-900 dark:hover:bg-zinc-800"
            >
              Clear process
            </button>
          )}
        </div>

      {/* Mobile filter drawer */}
      {filtersOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-black/50" onClick={() => setFiltersOpen(false)} />
          <div className="absolute right-0 top-0 h-full w-[88%] max-w-sm border-l border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
            <div className="mb-4 flex items-center justify-between">
              <div className="crt-overline text-muted-foreground">Filters</div>
              <button type="button" onClick={() => setFiltersOpen(false)} className="text-muted-foreground transition-colors hover:text-foreground" aria-label="Close">
                <X size={18} />
              </button>
            </div>
            <div className="space-y-3">
              <p className="crt-num text-[10px] uppercase leading-relaxed text-muted-foreground">
                Entity, period, department, and cost center use the reporting strip on this page (scroll up).
              </p>
              <div>
                <div className="crt-overline mb-1 text-muted-foreground">Process</div>
                <select
                  value={processFilter}
                  onChange={(e) => setProcessFilter(e.target.value)}
                  className="crt-num w-full rounded-sm border border-zinc-300 bg-white px-2 py-2 text-xs uppercase tracking-wider text-foreground dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100"
                >
                  <option value="all">All processes</option>
                  {processes.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  className="crt-num flex-1 rounded-sm bg-primary py-2 text-xs uppercase tracking-wider text-white"
                  onClick={() => setFiltersOpen(false)}
                >
                  Apply
                </button>
                <button
                  type="button"
                  className="crt-num flex-1 rounded-sm border border-zinc-300 bg-white py-2 text-xs uppercase tracking-wider text-muted-foreground transition-colors hover:bg-zinc-50 hover:text-foreground dark:border-zinc-600 dark:bg-zinc-900 dark:hover:bg-zinc-800"
                  onClick={() => setProcessFilter("all")}
                >
                  Clear
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

        {/* KPI hero band (Phase 3 / Slice 2 — driven by /kpi endpoints) */}
        <div className="mb-2 flex items-center justify-between">
          <div className="crt-overline text-muted-foreground">KPI tiles</div>
          <div className="flex items-center gap-2">
            {heroReorderMode ? (
              <>
                <button
                  type="button"
                  className="crt-num rounded-sm bg-primary px-3 py-2 text-[10px] uppercase tracking-wider text-white"
                  onClick={() => setHeroReorderMode(false)}
                  data-testid="hero-reorder-done"
                >
                  Done
                </button>
                <button
                  type="button"
                  className="crt-num rounded-sm border border-zinc-300 bg-white px-3 py-2 text-[10px] uppercase tracking-wider text-muted-foreground hover:bg-zinc-50 hover:text-foreground dark:border-zinc-600 dark:bg-zinc-900 dark:hover:bg-zinc-800"
                  onClick={() => {
                    const fresh = [...heroById.keys()];
                    persistHeroOrder(fresh);
                  }}
                  data-testid="hero-reorder-reset"
                >
                  Reset order
                </button>
              </>
            ) : (
              <button
                type="button"
                className="crt-num rounded-sm border border-zinc-300 bg-white px-3 py-2 text-[10px] uppercase tracking-wider text-muted-foreground hover:bg-zinc-50 hover:text-foreground dark:border-zinc-600 dark:bg-zinc-900 dark:hover:bg-zinc-800"
                onClick={() => setHeroReorderMode(true)}
                data-testid="hero-reorder-open"
              >
                Reorder
              </button>
            )}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3 mb-8 md:grid-cols-3 lg:grid-cols-6">
          {orderedHero.map((row) => {
            const kpiSlug = resolveCfoHeroKpiId(row);
            const kpiHref = kpiSlug ? hrefWithMasterParams(`/app/kpi/${encodeURIComponent(kpiSlug)}`) : null;
            const fallbackHref = row.drill_path ? hrefWithMasterParams(row.drill_path) : null;
            const to = kpiHref || fallbackHref;
            const value =
              row.unit === "usd"
                ? fmtUSD(row.value)
                : row.unit === "pct"
                  ? fmtPct(row.value)
                  : typeof row.value === "number"
                    ? String(row.value)
                    : String(row.value ?? "—");
            const unit = row.unit === "pct" ? "" : row.unit === "count" ? "" : "";
            const card = (
              <StatCard label={row.label} value={value} unit={unit} severity={row.severity || undefined} />
            );
            const tileId = String(kpiSlug || row.id || row.label || "");
            const reorderControls = heroReorderMode ? (
              <div className="mt-2 flex gap-2">
                <button
                  type="button"
                  className="crt-num flex-1 rounded-sm border border-zinc-300 bg-white py-1.5 text-[10px] uppercase tracking-wider text-muted-foreground hover:bg-zinc-50 hover:text-foreground dark:border-zinc-600 dark:bg-zinc-900 dark:hover:bg-zinc-800"
                  onClick={(e) => { e.preventDefault(); e.stopPropagation(); moveHero(tileId, "up"); }}
                  data-testid={`hero-move-up-${tileId}`}
                >
                  Up
                </button>
                <button
                  type="button"
                  className="crt-num flex-1 rounded-sm border border-zinc-300 bg-white py-1.5 text-[10px] uppercase tracking-wider text-muted-foreground hover:bg-zinc-50 hover:text-foreground dark:border-zinc-600 dark:bg-zinc-900 dark:hover:bg-zinc-800"
                  onClick={(e) => { e.preventDefault(); e.stopPropagation(); moveHero(tileId, "down"); }}
                  data-testid={`hero-move-down-${tileId}`}
                >
                  Down
                </button>
              </div>
            ) : null;
            const linkCls = clsx(
              "block rounded-sm text-inherit no-underline outline-none ring-offset-background transition-colors",
              "focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2",
              to && "cursor-pointer",
            );
            const testSuffix = kpiSlug || row.id || row.label || "tile";
            const content = (
              <div className="rounded-sm">
                {card}
                {reorderControls}
              </div>
            );
            return to && !heroReorderMode ? (
              <Link key={kpiSlug || row.id || row.drill_path || row.label} to={to} data-testid={`kpi-${testSuffix}`} className={linkCls}>
                {content}
              </Link>
            ) : (
              <div key={kpiSlug || row.id || row.drill_path || row.label} className={heroReorderMode && to ? "cursor-move" : ""}>
                {content}
              </div>
            );
          })}
        </div>

        {/* Slice 3 — CFO action queue */}
        <SectionCard
          kicker="ACTIONS"
          title="CFO action queue"
          subtitle="Prioritized items across cases, exceptions, approvals, and integrations."
          className="mb-8"
          collapsible
          collapseTestId="cfo-cockpit-action-queue-collapse"
          right={
            <button
              type="button"
              onClick={async () => {
                try {
                  const r = await http.get("/cfo/action-queue", {
                    params: { ...dashboardParams, refresh: true, limit: 6 },
                  });
                  setActionQueue(r.data);
                  toast.success("Action queue refreshed");
                } catch {
                  toast.error("Refresh failed");
                }
              }}
              className="crt-num text-[10px] uppercase tracking-wider text-primary hover:underline"
              data-testid="cfo-cockpit-action-queue-refresh"
            >
              Refresh
            </button>
          }
          bodyClassName="p-0"
        >
          {!actionQueue?.items?.length ? (
            <div
              className="p-4 text-sm text-muted-foreground"
              data-testid="cfo-action-queue-empty"
            >
              No queued actions under the current reporting context.
            </div>
          ) : (
            <div className="divide-y divide-zinc-200 dark:divide-zinc-800">
              {actionQueue.items.map((it) => (
                <div
                  key={it.id}
                  className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
                  data-testid={`cfo-action-item-${it.id}`}
                >
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-foreground">{it.title}</div>
                    <div className="crt-num mt-0.5 text-[10px] uppercase tracking-wider text-muted-foreground">
                      {it.priority} · {it.type?.replaceAll("_", " ")}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {it.drill?.route ? (
                      <button
                        type="button"
                        onClick={() => nav(hrefWithMasterParams(it.drill.route))}
                        className="crt-num rounded-sm border border-zinc-300 bg-white px-2 py-1 text-[9px] uppercase tracking-wider text-muted-foreground hover:bg-zinc-50 hover:text-foreground dark:border-zinc-600 dark:bg-zinc-900 dark:hover:bg-zinc-800"
                      >
                        Open
                      </button>
                    ) : null}
                    <button
                      type="button"
                      onClick={async () => {
                        try {
                          await http.post(`/cfo/action/${it.id}/approve`, { note: "Approved from CFO cockpit" });
                          toast.success("Approved");
                          const r = await http.get("/cfo/action-queue", { params: { ...dashboardParams, refresh: true, limit: 6 } });
                          setActionQueue(r.data);
                        } catch (e) {
                          toast.error(e?.response?.data?.detail || "Approve failed");
                        }
                      }}
                      className="crt-num rounded-sm border border-primary bg-primary px-2 py-1 text-[9px] uppercase tracking-wider text-white hover:opacity-90"
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      onClick={async () => {
                        try {
                          await http.post(`/cfo/action/${it.id}/escalate`, { note: "Escalated from CFO cockpit" });
                          toast.success("Escalated");
                          const r = await http.get("/cfo/action-queue", { params: { ...dashboardParams, refresh: true, limit: 6 } });
                          setActionQueue(r.data);
                        } catch (e) {
                          toast.error(e?.response?.data?.detail || "Escalate failed");
                        }
                      }}
                      className="crt-num rounded-sm border border-zinc-300 bg-white px-2 py-1 text-[9px] uppercase tracking-wider text-muted-foreground hover:bg-zinc-50 hover:text-foreground dark:border-zinc-600 dark:bg-zinc-900 dark:hover:bg-zinc-800"
                    >
                      Escalate
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </SectionCard>

        <InsightPanel section="cfo" title="CFO AI Insights" />

        {/* Two-column: Heatmap + AI narrative */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-8">
          <SectionCard
            className="lg:col-span-2"
            kicker="READINESS"
            title="Process × entity heatmap"
            right={<span className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">lower = worse</span>}
          >
            <ReadinessHeatmap
              rows={filteredHeatmap.length ? filteredHeatmap : data.heatmap || []}
              buildDrillHref={(p, e) =>
                hrefWithMasterParams(
                  `/app/cases?process=${encodeURIComponent(p)}&entity=${encodeURIComponent(e)}`,
                )
              }
            />
          </SectionCard>

          <SectionCard className="beam-border" kicker="ASSURANCE AI" title="AI narrative">
          <div className="mb-4 flex items-center gap-2">
            <Sparkle size={14} weight="fill" className="text-[hsl(var(--chart-1))]" />
            <h3 className="font-display text-base font-semibold tracking-tight text-foreground">AI narrative</h3>
            <span className="crt-num ml-auto border border-[hsl(var(--chart-1)/0.35)] px-1.5 py-0.5 text-[9px] uppercase tracking-wider text-[hsl(var(--chart-1))]">
              gemini · flash
            </span>
          </div>
          <div className="space-y-3 text-sm leading-relaxed text-muted-foreground">
            <p>
              Overall readiness at{" "}
              <span className="crt-num tabular-nums font-medium text-foreground">
                {(typeof k.audit_readiness_pct === "number" ? k.audit_readiness_pct : 0).toFixed(1)}%
              </span>{" "}
              with{" "}
              <span className="crt-num font-medium text-[hsl(var(--destructive))]">{fmtUSD(k.unresolved_high_risk_exposure)}</span> in
              unresolved exposure across {k.high_critical_open_cases ?? "—"} high/critical open cases
              <span className="crt-num text-muted-foreground/90"> [#1]</span>.
            </p>
            <p>
              Top risk drivers: backdated journals in R2R, duplicate invoice detections across APAC entities, and two open SoD conflicts in
              finance roles<span className="crt-num text-muted-foreground/90"> [#2][#3]</span>.
            </p>
            <p>
              Remediation SLA is tracking at{" "}
              <span className="crt-num tabular-nums font-medium">{fmtPct(k.remediation_sla_pct ?? 0)}</span>.
              Recommend immediate CFO review of priority-1 cases before close cutoff.
              <span className="crt-num mt-2 block text-[10px] uppercase tracking-wider text-[hsl(var(--chart-3))]">
                ACTION_REVIEW: human approval required
              </span>
            </p>
          </div>
          <button
            data-testid="open-copilot-btn"
            onClick={() => nav(hrefWithMasterParams("/app/copilot"))}
            className="crt-num mt-5 flex items-center gap-1 text-[10px] uppercase tracking-[0.15em] text-[hsl(var(--chart-1))] transition-colors hover:text-foreground"
          >
            Ask copilot <ArrowRight size={12} />
          </button>
          </SectionCard>
        </div>

        {/* Trends + Top risks */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-8">
          <SectionCard kicker="8-WEEK TREND" title="Readiness" bodyClassName="p-5">
          <ResponsiveContainer width="100%" height={140}>
            <AreaChart data={data.trends || []}>
              <CartesianGrid stroke={RC_STROKE} vertical={false} />
              <XAxis dataKey="week" stroke={RC_STROKE} tick={RC_TICK} />
              <YAxis domain={[50, 100]} stroke={RC_STROKE} tick={RC_TICK} />
              <Tooltip contentStyle={rcTooltipStyle()} />
              <Area type="monotone" dataKey="readiness" stroke="hsl(var(--chart-4))" strokeWidth={1.5} fill="url(#greenArea)" />
              <defs>
                <linearGradient id="greenArea" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="hsl(var(--chart-4))" stopOpacity={0.25} />
                  <stop offset="100%" stopColor="hsl(var(--chart-4))" stopOpacity={0} />
                </linearGradient>
              </defs>
            </AreaChart>
          </ResponsiveContainer>
          </SectionCard>
          <SectionCard kicker="8-WEEK TREND" title="Control failures" bodyClassName="p-5">
          <ResponsiveContainer width="100%" height={140}>
            <LineChart data={data.trends || []}>
              <CartesianGrid stroke={RC_STROKE} vertical={false} />
              <XAxis dataKey="week" stroke={RC_STROKE} tick={RC_TICK} />
              <YAxis stroke={RC_STROKE} tick={RC_TICK} />
              <Tooltip contentStyle={rcTooltipStyle()} />
              <Line
                type="monotone"
                dataKey="control_fail_count"
                stroke="hsl(var(--chart-3))"
                strokeWidth={1.5}
                dot={{ fill: "hsl(var(--chart-3))", r: 2 }}
              />
            </LineChart>
          </ResponsiveContainer>
          </SectionCard>
          <SectionCard kicker="8-WEEK TREND" title="Financial exposure" bodyClassName="p-5">
          <ResponsiveContainer width="100%" height={140}>
            <LineChart data={data.trends || []}>
              <CartesianGrid stroke={RC_STROKE} vertical={false} />
              <XAxis dataKey="week" stroke={RC_STROKE} tick={RC_TICK} />
              <YAxis stroke={RC_STROKE} tick={RC_TICK} tickFormatter={(v) => `${(v / 1000000).toFixed(1)}M`} />
              <Tooltip contentStyle={rcTooltipStyle()} formatter={(v) => `$${(v / 1000000).toFixed(2)}M`} />
              <Line
                type="monotone"
                dataKey="exposure"
                stroke="hsl(var(--chart-2))"
                strokeWidth={1.5}
                dot={{ fill: "hsl(var(--chart-2))", r: 2 }}
              />
            </LineChart>
          </ResponsiveContainer>
          </SectionCard>
        </div>

        {/* Top risks + Top failing controls */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <SectionCard
            className="lg:col-span-2 overflow-hidden"
            title="Top unresolved risks"
            kicker="RISK"
            right={<span className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">by severity × exposure</span>}
          >
          {/* Desktop table */}
          <div className="hidden md:block">
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[60vh]" testId="cfo-top-risks-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>Issue</DataTableTh>
                  <DataTableTh className="w-28">Severity</DataTableTh>
                  <DataTableTh className="w-28">Entity</DataTableTh>
                  <DataTableTh align="right" className="w-32">Exposure</DataTableTh>
                  <DataTableTh className="w-12" />
                </tr>
              </DataTableHead>
              <DataTableBody>
                {filteredTopRisks.map((r) => (
                  <DataTableRow
                    key={r.id}
                    onClick={() => nav(hrefWithMasterParams(`/app/evidence/${r.id}`))}
                    testId={`top-risk-${r.control_code}`}
                  >
                    <DataTableTd className="text-foreground">
                      <div className="max-w-md truncate text-sm">{r.title}</div>
                      <div className="crt-num mt-0.5 text-[10px] text-muted-foreground">{r.control_code} · {r.process}</div>
                    </DataTableTd>
                    <DataTableTd><SeverityBadge severity={r.severity} /></DataTableTd>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{r.entity}</DataTableTd>
                    <DataTableTd align="right" className="crt-num tabular-nums text-foreground">{fmtUSD(r.financial_exposure)}</DataTableTd>
                    <DataTableTd className="text-muted-foreground"><ArrowRight size={14} /></DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          </div>

          {/* Mobile list */}
          <div className="divide-y divide-zinc-200 dark:divide-zinc-800 md:hidden">
            {filteredTopRisks.map((r) => (
              <button
                key={r.id}
                type="button"
                onClick={() => nav(hrefWithMasterParams(`/app/evidence/${r.id}`))}
                className="w-full p-4 text-left transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-900/60"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate text-sm text-foreground">{r.title}</div>
                    <div className="crt-num mt-1 text-[10px] text-muted-foreground">{r.control_code} · {r.process} · {r.entity}</div>
                  </div>
                  <SeverityBadge severity={r.severity} />
                </div>
                <div className="mt-2 flex items-center justify-between">
                  <div className="crt-num text-xs text-muted-foreground">Exposure</div>
                  <div className="crt-num tabular-nums text-foreground">{fmtUSD(r.financial_exposure)}</div>
                </div>
              </button>
            ))}
          </div>
          </SectionCard>

          <SectionCard kicker="CONTROLS" title="Top failing controls" data-testid="top-failing-controls">
            <div className="space-y-2">
              {(data.top_failing_controls || []).map((c) => (
                <button
                  type="button"
                  key={c.code}
                  onClick={() => nav(hrefWithMasterParams(`/app/drill/control/${encodeURIComponent(c.code)}`))}
                  className="flex w-full items-start justify-between gap-3 rounded-sm border border-zinc-200 bg-zinc-50/80 px-4 py-3 transition-colors hover:bg-zinc-100/90 dark:border-zinc-800 dark:bg-zinc-900/40 dark:hover:bg-zinc-900/70"
                  data-testid={`top-failing-${c.code}`}
                >
                  <div className="min-w-0 flex-1 text-left">
                    <div className="crt-num text-[10px] text-muted-foreground">{c.code}</div>
                    <div className="truncate text-sm text-foreground">{c.name}</div>
                    <div className="crt-num mt-0.5 text-[10px] text-muted-foreground">{c.process}</div>
                  </div>
                  <div className="text-right">
                    <div className="crt-num text-xl tabular-nums text-[hsl(var(--destructive))]">{c.exceptions}</div>
                    <div className="crt-num text-[9px] uppercase tracking-wider text-muted-foreground">exceptions</div>
                  </div>
                </button>
              ))}
            </div>
          </SectionCard>
        </div>
      </div>
    </PageShell>
  );
}
