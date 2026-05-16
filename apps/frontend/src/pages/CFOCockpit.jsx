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

const RISK_BAND_STYLES = {
  critical: "border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-300",
  elevated: "border-amber-500/40 bg-amber-500/10 text-amber-800 dark:text-amber-200",
  moderate: "border-yellow-500/35 bg-yellow-500/10 text-yellow-800 dark:text-yellow-200",
  stable: "border-emerald-500/35 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200",
};

function renderDriverLine(line, citations, hrefWithMasterParams) {
  const m = line.match(/^\[#(\d+)\]\s*(.*)$/s);
  if (!m) return line;
  const idx = parseInt(m[1], 10) - 1;
  const cite = citations?.[idx];
  const rest = m[2] || "";
  if (!cite?.app_path) {
    return (
      <>
        <span className="font-medium text-[hsl(var(--chart-1))]">[#{m[1]}]</span> {rest}
      </>
    );
  }
  return (
    <>
      <Link
        to={hrefWithMasterParams(cite.app_path)}
        className="font-medium text-primary hover:underline"
      >
        [#{m[1]}]
      </Link>{" "}
      {rest}
    </>
  );
}

function ExecutiveNarrativeBody({ narrative, hrefWithMasterParams }) {
  const sections = narrative?.sections;
  if (!sections) return null;
  const citations = narrative?.citations || [];

  const band = (sections.risk_band || "moderate").toLowerCase();
  const bandClass = RISK_BAND_STYLES[band] || RISK_BAND_STYLES.moderate;
  const hrefFn = hrefWithMasterParams || ((p) => p);

  return (
    <div className="space-y-4" data-testid="cfo-narrative-text">
      <p className="text-sm font-medium leading-snug text-foreground">{sections.scope_title}</p>

      <div className={clsx("rounded-sm border px-3 py-2", bandClass)}>
        <p className="crt-num text-[10px] uppercase tracking-wider opacity-80">Composite assurance risk</p>
        <p className="mt-0.5 font-display text-lg font-semibold tabular-nums tracking-tight">
          {sections.risk_score_pct}%
          <span className="ml-2 text-sm font-normal uppercase tracking-wide opacity-90">({band} band)</span>
        </p>
      </div>

      <p className="text-sm leading-relaxed text-muted-foreground">{sections.summary}</p>

      {sections.drivers?.length > 0 ? (
        <div>
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-foreground">
            Primary drivers ranked by model impact
          </p>
          <ul className="space-y-1.5 border-l-2 border-[hsl(var(--chart-1)/0.35)] pl-3">
            {sections.drivers.map((line, idx) => (
              <li key={idx} className="text-sm leading-snug text-muted-foreground">
                {line.startsWith("[#") ? renderDriverLine(line, citations, hrefFn) : <>• {line}</>}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {sections.actions?.length > 0 ? (
        <div>
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-foreground">Recommended actions</p>
          <ul className="list-disc space-y-1 pl-4 text-sm leading-relaxed text-muted-foreground">
            {sections.actions.map((action, idx) => (
              <li key={idx}>{action}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {sections.action_review ? (
        <p
          className="rounded-sm border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs font-medium leading-relaxed text-amber-900 dark:text-amber-100"
          data-testid="cfo-narrative-action-review"
        >
          <span className="crt-num text-[10px] uppercase tracking-wider">Action review</span>
          <span className="mt-1 block">{sections.action_review}</span>
        </p>
      ) : null}

      {sections.queue_summary?.open_total != null ? (
        <div
          className="rounded-sm border border-zinc-200 bg-zinc-50/80 px-3 py-3 dark:border-zinc-700 dark:bg-zinc-900/50"
          data-testid="cfo-narrative-queue-summary"
        >
          <p className="crt-num text-[10px] font-semibold uppercase tracking-wider text-foreground">Action queue</p>
          <div className="mt-2 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
            {[
              { l: "Open", v: sections.queue_summary.open_total },
              { l: "P0", v: sections.queue_summary.p0_open },
              { l: "Exposure", v: fmtUSD(sections.queue_summary.queue_exposure_usd ?? 0) },
              { l: "SLA %", v: `${sections.queue_summary.sla_compliance_pct ?? 0}%` },
            ].map((t) => (
              <div key={t.l}>
                <p className="crt-num text-[9px] uppercase text-muted-foreground">{t.l}</p>
                <p className="font-semibold tabular-nums">{t.v}</p>
              </div>
            ))}
          </div>
          <Link
            to={hrefFn("/app/cfo-action-queue")}
            className="crt-num mt-2 inline-block text-[10px] uppercase tracking-wider text-primary hover:underline"
          >
            Open action queue →
          </Link>
        </div>
      ) : null}
    </div>
  );
}

export default function CFOCockpit() {
  const [cc, setCc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [bootError, setBootError] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [processFilter, setProcessFilter] = useState("all");
  const [heroReorderMode, setHeroReorderMode] = useState(false);
  const [heroOrder, setHeroOrder] = useState(null);
  const [narrative, setNarrative] = useState(null);
  const [narrativeLoading, setNarrativeLoading] = useState(false);
  const [auditPortfolio, setAuditPortfolio] = useState([]);
  const [auditPortfolioLoading, setAuditPortfolioLoading] = useState(false);
  const [commentDraft, setCommentDraft] = useState({});
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

  const commandCenterParams = useMemo(
    () => ({
      ...dashboardParams,
      refresh: true,
      queue_limit: 6,
      include_narrative: true,
      ...(processFilter !== "all" ? { process: processFilter } : {}),
    }),
    [dashboardParams, processFilter],
  );

  const data = cc?.cockpit || null;
  const actionQueue = cc?.action_queue || null;
  const actionQueueSummary = cc?.action_queue_summary || null;
  const alerts = cc?.alerts || [];
  const whatChanged = cc?.what_changed || null;
  const opsKpis = cc?.ops_kpis || [];

  const load = useCallback(
    async (opts = {}) => {
      const { noCache = false } = opts;
      if (firstLoadRef.current) setLoading(true);
      try {
        const { data: payload } = await http.get("/cfo/command-center", {
          params: { ...commandCenterParams, no_cache: noCache },
        });
        setBootError(false);
        setCc(payload);
        setNarrative(payload?.narrative || null);
      } catch (_e) {
        setBootError(true);
        toast.error("Failed to load CFO command center");
      } finally {
        if (firstLoadRef.current) {
          setLoading(false);
          firstLoadRef.current = false;
        }
      }
    },
    [commandCenterParams],
  );

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setAuditPortfolioLoading(true);
      try {
        const { data } = await http.get("/audit-engagements/executive-review-cross-org", {
          params: { ...dashboardParams, limit: 6, pool: 40 },
        });
        if (!cancelled) setAuditPortfolio(Array.isArray(data) ? data : []);
      } catch {
        if (!cancelled) setAuditPortfolio([]);
      } finally {
        if (!cancelled) setAuditPortfolioLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [dashboardParams]);

  const runAll = async () => {
    setRefreshing(true);
    try {
      const { data: r } = await http.post("/controls/run-all");
      toast.success(`Re-ran ${r.runs.length} controls · ${r.total_exceptions} exceptions`);
      await load({ noCache: true });
    } catch (_e) {
      toast.error("Run failed");
    }
    setRefreshing(false);
  };

  const generateNarrative = async () => {
    setNarrativeLoading(true);
    try {
      const { data: res } = await http.post("/cfo/command-center/narrative", {
        ...dashboardParams,
        ...(processFilter !== "all" ? { process: processFilter } : {}),
      });
      setNarrative(res.narrative);
      toast.success("Executive briefing generated");
    } catch {
      toast.error("Narrative generation failed");
    } finally {
      setNarrativeLoading(false);
    }
  };

  const refreshQueue = async () => {
    try {
      await load({ noCache: true });
      toast.success("Command center refreshed");
    } catch {
      toast.error("Refresh failed");
    }
  };

  const queueAction = async (actionId, kind, note = "") => {
    const path =
      kind === "approve"
        ? `/cfo/action/${actionId}/approve`
        : kind === "reject"
          ? `/cfo/action/${actionId}/reject`
          : kind === "escalate"
            ? `/cfo/action/${actionId}/escalate`
            : `/cfo/action/${actionId}/comment`;
    const body = kind === "comment" ? { comment: note } : { note };
    await http.post(path, body);
    await load({ noCache: true });
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

  const filteredHeatmap = useMemo(() => data?.heatmap || [], [data]);

  const filteredTopRisks = useMemo(() => (data?.top_risks || []).slice(0, 10), [data]);

  const hero = useMemo(() => {
    const k = data?.kpis || {};
    if ((cc?.hero_kpis || []).length) return cc.hero_kpis;
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
        drill_path: "/app/cases?status=open",
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
  }, [data, cc]);

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

        <MastersFilterStrip
          className="mb-4"
          extraFilters={
            <>
              {/* Process-only facet: heatmap / top risks payload is multi-entity; this narrows client-side. */}
              <label className="flex min-w-0 flex-1 flex-col gap-1">
                <span className="crt-overline text-muted-foreground">Process view</span>
                <select
                  value={processFilter}
                  onChange={(e) => setProcessFilter(e.target.value)}
                  className="crt-num h-9 min-w-0 w-full max-w-full rounded-none border border-zinc-300 bg-white px-3 text-xs uppercase tracking-wider text-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100"
                  data-testid="process-filter"
                >
                  <option value="all">All processes</option>
                  {processes.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
              </label>
              {processFilter !== "all" ? (
                <button
                  type="button"
                  onClick={() => setProcessFilter("all")}
                  className="crt-num h-9 shrink-0 self-end rounded-none border border-zinc-300 bg-white px-3 text-[10px] uppercase tracking-wider text-muted-foreground transition-colors hover:bg-zinc-50 hover:text-foreground dark:border-zinc-600 dark:bg-zinc-900 dark:hover:bg-zinc-800"
                  data-testid="clear-process-filter"
                >
                  Clear process
                </button>
              ) : null}
            </>
          }
        />

        {/* KPI hero band — command-center BFF */}
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
            const deltaLabel =
              row.delta_pct != null
                ? `${row.delta_direction === "down" ? "▼" : row.delta_direction === "up" ? "▲" : ""} ${Math.abs(row.delta_pct).toFixed(1)}${row.unit === "pct" ? " pts" : "%"} vs prior`
                : null;
            const card = (
              <StatCard
                label={row.label}
                value={value}
                unit={unit}
                severity={row.severity || undefined}
                trend={row.trend_pct ?? row.delta_pct ?? undefined}
                subtle={deltaLabel}
              />
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

        <div className="crt-num mb-4 flex flex-wrap items-center justify-between gap-2 text-[10px] uppercase tracking-wider text-muted-foreground">
          <span data-testid="cfo-as-of">
            As of {cc?.as_of ? fmtDate(cc.as_of) : "—"}
            {cc?.cached ? " · cached" : ""}
          </span>
          <button
            type="button"
            onClick={() => load({ noCache: true })}
            className="text-primary hover:underline"
            data-testid="cfo-refresh-all"
          >
            Refresh data
          </button>
        </div>

        {whatChanged?.changes?.length > 0 ? (
          <div className="mb-4 rounded-sm border border-zinc-200 bg-zinc-50/80 p-3 dark:border-zinc-700 dark:bg-zinc-900/40" data-testid="cfo-what-changed">
            <div className="crt-overline mb-2 text-muted-foreground">Since your last visit</div>
            <ul className="crt-num space-y-1 text-xs text-foreground">
              {whatChanged.changes.map((ch) => (
                <li key={ch.kpi_id || ch.label}>
                  {ch.label || ch.kpi_id?.replaceAll("_", " ")}: {ch.prior} → {ch.current}
                  {ch.delta_abs != null ? ` (${ch.delta_abs > 0 ? "+" : ""}${ch.delta_abs})` : ""}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {(entityCode || periodExplicit || departmentId || costCenterId || processFilter !== "all") && (
          <p className="crt-num mb-4 text-[10px] uppercase tracking-wider text-muted-foreground">
            KPIs and lists follow the reporting context{processFilter !== "all" ? ` · process ${processFilter}` : ""}.
          </p>
        )}

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

        <SectionCard
          title="Operations"
          className="mb-6"
          bodyClassName="p-0 text-sm"
          collapsible
          defaultCollapsed
          collapseTestId="cfo-ops-collapse"
          data-testid="cfo-ops-section"
        >
          {opsKpis.length > 0 ? (
            <div className="grid grid-cols-2 gap-3 p-4 md:grid-cols-4" data-testid="cfo-ops-kpi-strip">
              {opsKpis.map((row) => {
                const val =
                  row.unit === "usd"
                    ? fmtUSD(row.value)
                    : row.unit === "pct"
                      ? fmtPct(row.value)
                      : row.value == null
                        ? "—"
                        : String(row.value);
                const linked = row.linked_queue_count ?? 0;
                const subtleParts = [row.subtle, linked > 0 ? `${linked} in queue` : null].filter(Boolean);
                return (
                  <div key={row.id}>
                    <StatCard
                      label={row.label}
                      value={val}
                      unit={row.unit === "weeks" ? "wks" : ""}
                      severity={row.severity}
                      trend={row.trend_pct ?? row.delta_pct}
                      subtle={subtleParts.length ? subtleParts.join(" · ") : null}
                      testId={`ops-kpi-${row.id}`}
                    />
                  </div>
                );
              })}
            </div>
          ) : null}

          <div
            className={clsx("overflow-x-auto", opsKpis.length > 0 && "border-t border-zinc-200 dark:border-zinc-800")}
            data-testid="cfo-exec-review-portfolio"
          >
            <div className="border-b border-zinc-200 px-4 py-3 dark:border-zinc-700">
              <div className="crt-overline text-muted-foreground">Statutory audit</div>
              <h4 className="font-display mt-1 text-base font-semibold tracking-tight text-foreground">
                Executive review portfolio
              </h4>
              <p className="mt-1 text-xs leading-snug text-muted-foreground">
                Lowest continuous assurance first (tie-break: open critical cases). Respects entity scope when RBAC is enforced.
              </p>
              <Link
                to={hrefWithMasterParams("/app/executive-review")}
                className="crt-num mt-2 inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-primary hover:underline"
              >
                Open executive review workspace <ArrowRight size={12} />
              </Link>
            </div>
            {auditPortfolioLoading ? (
              <div className="px-4 py-6 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Loading portfolio…</div>
            ) : auditPortfolio.length === 0 ? (
              <div className="px-4 py-6 text-xs text-muted-foreground">No statutory engagements in scope.</div>
            ) : (
              <table className="crt-num w-full min-w-[560px] border-collapse text-left text-xs">
                <thead>
                  <tr className="border-b border-zinc-200 bg-zinc-50 text-muted-foreground dark:border-zinc-700 dark:bg-zinc-900/60">
                    <th className="px-4 py-2 font-medium">Engagement</th>
                    <th className="px-4 py-2 font-medium">Entity</th>
                    <th className="px-4 py-2 font-medium">FY</th>
                    <th className="px-4 py-2 font-medium">Assurance</th>
                    <th className="px-4 py-2 font-medium">Crit. open</th>
                    <th className="px-4 py-2 font-medium" />
                  </tr>
                </thead>
                <tbody>
                  {auditPortfolio.map((row) => (
                    <tr key={row.engagement_id} className="border-b border-zinc-100 dark:border-zinc-800">
                      <td className="px-4 py-2 font-medium text-foreground">{row.engagement_id}</td>
                      <td className="px-4 py-2">{row.entity_name || "—"}</td>
                      <td className="px-4 py-2">{row.financial_year || "—"}</td>
                      <td className="px-4 py-2 tabular-nums">{row.continuous_assurance_score ?? "—"}</td>
                      <td className="px-4 py-2 tabular-nums">{row.open_critical_cases ?? "—"}</td>
                      <td className="px-4 py-2 text-right">
                        <Link
                          to={hrefWithMasterParams(
                            `/app/executive-review?engagement_id=${encodeURIComponent(row.engagement_id)}`,
                          )}
                          className="text-[10px] font-semibold uppercase tracking-wider text-primary hover:underline"
                        >
                          Review
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </SectionCard>

        {/* Slice 3 — CFO action queue */}
        <SectionCard
          kicker="ACTIONS"
          title="CFO action queue"
          subtitle="Prioritized items across cases, exceptions, approvals, and integrations."
          className="mb-8"
          collapsible
          defaultCollapsed
          collapseTestId="cfo-cockpit-action-queue-collapse"
          right={
            <div className="flex items-center gap-3">
              <Link
                to={hrefWithMasterParams("/app/cfo-action-queue")}
                className="crt-num text-[10px] uppercase tracking-wider text-primary hover:underline"
                data-testid="cfo-cockpit-view-all-queue"
              >
                View all ({actionQueueSummary?.open_total ?? actionQueue?.total ?? 0})
              </Link>
              <button
                type="button"
                onClick={refreshQueue}
                className="crt-num text-[10px] uppercase tracking-wider text-primary hover:underline"
                data-testid="cfo-cockpit-action-queue-refresh"
              >
                Refresh
              </button>
            </div>
          }
          bodyClassName="p-0"
        >
          {actionQueueSummary ? (
            <div className="grid grid-cols-2 gap-2 border-b border-zinc-200 p-3 sm:grid-cols-4 dark:border-zinc-800">
              {[
                { l: "Open", v: actionQueueSummary.open_total },
                { l: "P0", v: actionQueueSummary.p0_open },
                { l: "Exposure", v: fmtUSD(actionQueueSummary.queue_exposure_usd) },
                { l: "SLA %", v: `${actionQueueSummary.sla_compliance_pct}%` },
              ].map((t) => (
                <div key={t.l} className="text-center">
                  <p className="crt-num text-[9px] uppercase text-muted-foreground">{t.l}</p>
                  <p className="text-sm font-semibold tabular-nums">{t.v}</p>
                </div>
              ))}
            </div>
          ) : null}
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
                          await queueAction(it.id, "approve", "Approved from CFO cockpit");
                          toast.success("Approved");
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
                          await queueAction(it.id, "reject", "Rejected from CFO cockpit");
                          toast.success("Rejected");
                        } catch (e) {
                          toast.error(e?.response?.data?.detail || "Reject failed");
                        }
                      }}
                      className="crt-num rounded-sm border border-zinc-300 bg-white px-2 py-1 text-[9px] uppercase tracking-wider text-muted-foreground hover:bg-zinc-50 dark:border-zinc-600 dark:bg-zinc-900"
                    >
                      Reject
                    </button>
                    <button
                      type="button"
                      onClick={async () => {
                        try {
                          await queueAction(it.id, "escalate", "Escalated from CFO cockpit");
                          toast.success("Escalated");
                        } catch (e) {
                          toast.error(e?.response?.data?.detail || "Escalate failed");
                        }
                      }}
                      className="crt-num rounded-sm border border-zinc-300 bg-white px-2 py-1 text-[9px] uppercase tracking-wider text-muted-foreground hover:bg-zinc-50 dark:border-zinc-600 dark:bg-zinc-900"
                    >
                      Escalate
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </SectionCard>

        <InsightPanel section="cfo" title="CFO AI Insights" defaultCollapsed />

        {/* Two-column: Heatmap + AI narrative */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-8">
          <SectionCard
            className="lg:col-span-2"
            kicker="READINESS"
            title="Process × entity heatmap"
            bodyClassName="p-0"
            right={<span className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">lower = worse</span>}
          >
            <ReadinessHeatmap
              rows={filteredHeatmap}
              buildDrillHref={(p, e) =>
                hrefWithMasterParams(
                  `/app/cases?process=${encodeURIComponent(p)}&entity=${encodeURIComponent(e)}`,
                )
              }
            />
            {alerts.length > 0 ? (
              <div
                className="border-t border-amber-500/30 bg-amber-500/5 p-4"
                data-testid="cfo-alerts-strip"
              >
                <div className="crt-overline mb-2 text-amber-700 dark:text-amber-400">Threshold alerts</div>
                <ul className="space-y-1 text-sm text-foreground">
                  {alerts.map((a) => (
                    <li key={a.id} data-testid={`cfo-alert-${a.code}`}>
                      <SeverityBadge severity={a.severity === "critical" ? "critical" : "high"} />
                      {a.href ? (
                        <Link
                          to={hrefWithMasterParams(a.href)}
                          className="ml-2 text-foreground hover:text-primary hover:underline"
                        >
                          {a.message}
                        </Link>
                      ) : (
                        <span className="ml-2">{a.message}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </SectionCard>

          <SectionCard className="beam-border" data-testid="cfo-narrative-panel">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2 border-b border-zinc-200 pb-3 dark:border-zinc-700">
              <div className="flex flex-wrap items-center gap-2">
                <Sparkle size={14} weight="fill" className="text-[hsl(var(--chart-1))]" />
                <h3 className="font-display text-base font-semibold tracking-tight text-foreground">Data-driven narrative</h3>
                <span className="crt-num border border-[hsl(var(--chart-1)/0.35)] px-1.5 py-0.5 text-[9px] uppercase tracking-wider text-[hsl(var(--chart-1))]">
                  {narrative?.model || "onetouch-cfo-ml-v1"}
                </span>
              </div>
              <button
                type="button"
                disabled={narrativeLoading}
                onClick={generateNarrative}
                className="crt-num rounded-sm border border-primary bg-primary px-2 py-1 text-[9px] uppercase tracking-wider text-white disabled:opacity-50"
                data-testid="cfo-generate-narrative-btn"
              >
                {narrativeLoading ? "Computing…" : "Refresh briefing"}
              </button>
            </div>
            {narrative?.sections ? (
              <ExecutiveNarrativeBody narrative={narrative} hrefWithMasterParams={hrefWithMasterParams} />
            ) : narrative?.answer ? (
              <div className="space-y-3 text-sm leading-relaxed text-muted-foreground whitespace-pre-wrap" data-testid="cfo-narrative-text">
                {narrative.answer}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                Briefing is computed from KPIs, trends, heatmap, alerts, and open exceptions in your current filter scope.
              </p>
            )}
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
