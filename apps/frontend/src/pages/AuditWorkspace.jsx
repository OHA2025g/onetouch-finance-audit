import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { fmtDateTime, fmtPct, fmtUSD } from "../lib/format";
import { Play, CheckCircle, Warning, ArrowsClockwise, ListChecks, Gauge, Sparkle } from "@phosphor-icons/react";
import clsx from "clsx";
import InsightPanel from "../components/InsightPanel";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { useMastersFilters } from "../lib/MastersFilterContext";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useAuth } from "../lib/auth";
import {
  controlIsStale,
  controlListStatus,
  formatRelativeRun,
  kpiSeverityForPassRate,
  kpiSeverityForReadiness,
  postureSentence,
} from "../lib/auditWorkspaceSummary";
import { useAuditWorkspaceSummary } from "../lib/useAuditWorkspaceSummary";
import { AUDIT_WORKSPACE_V2 } from "../lib/auditWorkspaceFlags";
import { AuditChartsRow } from "../components/audit/AuditWorkspaceCharts";
import AuditWorkspaceSkeleton from "../components/audit/AuditWorkspaceSkeleton";
import AuditLinkStatCard from "../components/audit/AuditLinkStatCard";
import ControlRunSparkline from "../components/audit/ControlRunSparkline";

const STATUS_CHIPS = [
  { id: "", label: "All" },
  { id: "pass", label: "Pass" },
  { id: "fail", label: "Fail" },
  { id: "not_run", label: "Not run" },
  { id: "stale", label: "Stale" },
];


export default function AuditWorkspace() {
  const nav = useNavigate();
  const { user } = useAuth();
  const { hrefWithMasterParams } = useMastersFilters();
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [running, setRunning] = useState(false);
  const [runningAll, setRunningAll] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [trendDays, setTrendDays] = useState(30);
  const [searchInput, setSearchInput] = useState("");
  const [filter, setFilter] = useState({
    process: "",
    crit: "",
    status: "",
    q: "",
    sort: "code",
  });
  const scopeParams = useDashboardFilterParams();
  const detailRef = useRef(null);
  const canRun = user?.role !== "External Auditor";

  const load = useCallback(async ({ bustCache = false } = {}) => {
    const { data: d } = await http.get("/dashboard/audit", {
      params: {
        ...scopeParams,
        trend_days: trendDays,
        ...(bustCache ? { no_cache: true, _t: Date.now() } : {}),
      },
    });
    setData(d);
    const fromUrl = searchParams.get("control");
    setSelected((prev) => {
      if (!d.controls?.length) return null;
      if (fromUrl && d.controls.some((c) => c.id === fromUrl)) return fromUrl;
      if (prev && d.controls.some((c) => c.id === prev)) return prev;
      return d.controls[0].id;
    });
  }, [scopeParams, searchParams, trendDays]);

  useEffect(() => {
    load().catch(() => toast.error("Failed to load audit workspace"));
  }, [load]);

  useEffect(() => {
    const t = window.setTimeout(() => {
      setFilter((f) => ({ ...f, q: searchInput.trim() }));
    }, 200);
    return () => window.clearTimeout(t);
  }, [searchInput]);

  const selectControl = useCallback((controlId) => {
    if (!controlId) return;
    setSelected(controlId);
    window.requestAnimationFrame(() => {
      detailRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
  }, []);

  useEffect(() => {
    if (!selected) return;
    const next = new URLSearchParams(searchParams);
    next.set("control", selected);
    setSearchParams(next, { replace: true });
  }, [selected]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!selected) return;
    http
      .get(`/controls/${selected}`, { params: scopeParams })
      .then((r) => setDetail(r.data))
      .catch(() => toast.error("Failed to load control"));
  }, [selected, scopeParams]);

  const {
    controls,
    summary,
    listFiltered,
    catalogEmpty,
    filterEmpty,
    allGreen,
    sparklineByControl,
    controlIdByProcess,
  } = useAuditWorkspaceSummary(data, filter);

  useEffect(() => {
    if (!controls.length) {
      if (selected) setSelected(null);
      return;
    }
    if (!selected || !controls.some((c) => c.id === selected)) {
      setSelected(controls[0].id);
    }
  }, [controls, selected]);

  const selectControlByProcess = useCallback(
    (processName) => {
      const id = controlIdByProcess[processName];
      if (id) selectControl(id);
    },
    [controlIdByProcess, selectControl]
  );

  const processes = useMemo(() => [...new Set((data?.controls || []).map((c) => c.process))], [data?.controls]);
  const criticalities = useMemo(
    () => [...new Set((data?.controls || []).map((c) => c.criticality))],
    [data?.controls]
  );

  const run = async (controlId = selected) => {
    if (!controlId || !canRun) return;
    setRunning(true);
    try {
      const { data: r } = await http.post(`/controls/${controlId}/run`);
      toast.success(`Run complete · ${r.exceptions} exceptions`);
      await load();
      if (controlId === selected) {
        const { data: det } = await http.get(`/controls/${controlId}`, { params: scopeParams });
        setDetail(det);
      }
    } catch {
      toast.error("Run failed");
    }
    setRunning(false);
  };

  const runAllControls = async () => {
    if (!canRun) return;
    setRunningAll(true);
    try {
      const { data: r } = await http.post("/controls/run-all");
      const runCount = r?.runs?.length ?? 0;
      toast.success(`Re-ran ${runCount} controls · ${r?.total_exceptions ?? 0} exceptions`);
      await load();
      if (selected) {
        const { data: det } = await http.get(`/controls/${selected}`, { params: scopeParams });
        setDetail(det);
      }
    } catch {
      toast.error("Run all failed");
    }
    setRunningAll(false);
  };

  const onRefresh = async () => {
    setRefreshing(true);
    try {
      await load({ bustCache: true });
      if (selected) {
        const { data: det } = await http.get(`/controls/${selected}`, { params: scopeParams });
        setDetail(det);
      }
      toast.success("Audit workspace refreshed");
    } catch {
      toast.error("Refresh failed");
    }
    setRefreshing(false);
  };

  if (!data) {
    return (
      <PageShell maxWidth="max-w-[1800px]">
        <AuditWorkspaceSkeleton />
      </PageShell>
    );
  }

  const pfn = summary.pass_fail_not_run || { pass: 0, fail: 0, not_run: 0 };

  return (
    <PageShell maxWidth="max-w-[1800px]">
      <div data-testid="audit-workspace">
        <PageHeader
          kicker="FINANCE OPERATIONS"
          title="Audit workspace"
          subtitle="Continuous control testing: run the 23-rule pack, triage exceptions, and link evidence for close and committee reporting."
          right={
            <div className="flex flex-wrap items-center gap-2">
              <Link
                to={hrefWithMasterParams("/app/cases?status=open")}
                className="crt-num flex h-9 items-center gap-1.5 rounded-sm border border-zinc-300 px-3 text-[10px] uppercase tracking-wider text-foreground hover:bg-zinc-100 dark:border-zinc-600 dark:hover:bg-zinc-900"
                data-testid="audit-link-cases"
              >
                <ListChecks size={14} /> Cases
              </Link>
              <Link
                to={hrefWithMasterParams("/app/readiness")}
                className="crt-num flex h-9 items-center gap-1.5 rounded-sm border border-zinc-300 px-3 text-[10px] uppercase tracking-wider text-foreground hover:bg-zinc-100 dark:border-zinc-600 dark:hover:bg-zinc-900"
                data-testid="audit-link-readiness"
              >
                <Gauge size={14} /> Readiness
              </Link>
              <button
                type="button"
                onClick={onRefresh}
                disabled={refreshing}
                className="crt-num flex h-9 items-center gap-1.5 rounded-sm border border-zinc-300 px-3 text-[10px] uppercase tracking-wider text-foreground hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-600 dark:hover:bg-zinc-900"
                data-testid="audit-refresh-btn"
              >
                <ArrowsClockwise size={14} className={refreshing ? "animate-spin" : ""} /> Refresh
              </button>
              {canRun ? (
                <button
                  type="button"
                  onClick={runAllControls}
                  disabled={runningAll}
                  className="crt-num flex h-9 items-center gap-1.5 rounded-sm border border-primary bg-primary px-3 text-[10px] uppercase tracking-wider text-white disabled:opacity-50"
                  data-testid="audit-run-all-btn"
                >
                  <Play size={12} weight="fill" /> {runningAll ? "Running…" : "Run all controls"}
                </button>
              ) : null}
            </div>
          }
        />

        <MastersFilterStrip className="mb-4" />

        {data.filters_applied && Object.keys(data.filters_applied).length > 0 ? (
          <div className="crt-num mb-4 flex flex-wrap items-center gap-2" data-testid="audit-scope-chips">
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Reporting context</span>
            {Object.entries(data.filters_applied).map(([key, val]) => (
              <span
                key={key}
                className="rounded-sm border border-zinc-300 bg-zinc-50/90 px-2 py-1 text-[10px] uppercase tracking-wider text-foreground dark:border-zinc-600 dark:bg-zinc-900/60"
              >
                {key.replace(/_/g, " ")}: {String(val)}
              </span>
            ))}
          </div>
        ) : null}

        <p className="crt-num mb-4 text-xs text-muted-foreground" data-testid="audit-posture-sentence">
          {postureSentence(summary)}
        </p>

        <div
          className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5"
          data-testid="audit-kpi-strip"
        >
          <AuditLinkStatCard
            compact
            to={hrefWithMasterParams("/app/readiness")}
            label={summary.readiness_in_view ? "Readiness (in view)" : "Audit readiness"}
            value={summary.audit_readiness_pct != null ? fmtPct(summary.audit_readiness_pct) : "—"}
            subtle={
              summary.readiness_in_view && summary.catalog_readiness_pct != null
                ? `Catalog: ${fmtPct(summary.catalog_readiness_pct)}`
                : undefined
            }
            severity={kpiSeverityForReadiness(summary.audit_readiness_pct)}
            testId="audit-kpi-readiness"
          />
          <AuditLinkStatCard
            compact
            to={hrefWithMasterParams("/app/cases?status=open")}
            label="Controls in view"
            value={summary.controls_in_view ?? "—"}
            subtle={summary.view_filtered ? "List filters active" : "Full catalog"}
            testId="audit-kpi-controls-in-view"
          />
          <AuditLinkStatCard
            compact
            to={hrefWithMasterParams("/app/cases?status=open")}
            label="Open exceptions"
            value={summary.open_exceptions_count ?? "—"}
            severity={(summary.open_exceptions_count ?? 0) > 0 ? "warning" : "success"}
            testId="audit-kpi-open-exceptions"
          />
          <AuditLinkStatCard
            compact
            to={hrefWithMasterParams("/app/cases?status=open")}
            label="Open exposure"
            value={summary.open_exposure_usd != null ? fmtUSD(summary.open_exposure_usd) : "—"}
            severity={(summary.open_exposure_usd ?? 0) > 0 ? "warning" : "success"}
            testId="audit-kpi-open-exposure"
          />
          <AuditLinkStatCard
            compact
            label="Pass rate"
            value={summary.pass_rate_pct != null ? fmtPct(summary.pass_rate_pct) : "—"}
            severity={kpiSeverityForPassRate(summary.pass_rate_pct)}
            testId="audit-kpi-pass-rate"
          />
          <AuditLinkStatCard
            compact
            label="Pass / fail / not run"
            value={`${pfn.pass} / ${pfn.fail} / ${pfn.not_run}`}
            subtle={summary.view_filtered ? "Counts for filtered list" : undefined}
            testId="audit-kpi-pfn"
          />
          <AuditLinkStatCard
            compact
            label="Last-run exceptions"
            value={summary.last_run_exceptions_sum ?? 0}
            subtle="Sum on last test (in view)"
            severity={(summary.last_run_exceptions_sum ?? 0) > 0 ? "warning" : "success"}
            testId="audit-kpi-last-run-exc"
          />
          <AuditLinkStatCard
            compact
            label="Stale controls"
            value={summary.stale_control_count ?? 0}
            severity={(summary.stale_control_count ?? 0) > 0 ? "warning" : "success"}
            testId="audit-kpi-stale"
          />
          <AuditLinkStatCard
            compact
            label="Critical failing"
            value={summary.critical_failing_count ?? 0}
            severity={(summary.critical_failing_count ?? 0) > 0 ? "critical" : "success"}
            testId="audit-kpi-critical"
          />
        </div>

        <AuditChartsRow
          summary={summary}
          trends={data.trends}
          trendDays={trendDays}
          onTrendDaysChange={setTrendDays}
          onSelectControl={selectControl}
          onSelectProcess={selectControlByProcess}
        />

        {data.recent_runs?.length ? (
          <SectionCard className="mb-4" kicker="ACTIVITY" title="Latest test runs" bodyClassName="p-4">
            <div className="space-y-1" data-testid="audit-recent-runs-strip">
              {data.recent_runs.slice(0, 6).map((r) => (
                <button
                  key={r.id}
                  type="button"
                  className="crt-num flex w-full items-center justify-between rounded-sm border border-zinc-200 px-3 py-2 text-left text-xs hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900/60"
                  onClick={() => r.control_id && selectControl(r.control_id)}
                >
                  <span className="text-foreground">
                    {r.control_code || r.control_id} · {fmtDateTime(r.run_ts)}
                  </span>
                  <span className={r.exceptions_count > 0 ? "text-[hsl(var(--chart-3))]" : "text-[hsl(var(--chart-4))]"}>
                    {r.exceptions_count ?? 0} exc
                  </span>
                </button>
              ))}
            </div>
          </SectionCard>
        ) : null}

        <InsightPanel section="audit" title="Audit Workspace · AI Insights" />

        <div className="sticky top-0 z-20 -mx-1 mb-4 border-b border-zinc-200/80 bg-background/95 px-1 pb-1 backdrop-blur dark:border-zinc-800/80">
        <SectionCard
          kicker="FILTERS"
          title="Control selection"
          collapsible
          defaultCollapsed={false}
          collapseTestId="audit-filters-toggle"
          right={
            <span className="crt-num text-xs text-muted-foreground">
              {controls.length} / {data.controls.length} controls
            </span>
          }
          className="mb-0 shadow-sm"
          bodyClassName="p-4 space-y-3"
        >
          <div className="flex flex-wrap items-center gap-2" id="audit-filter-panel">
            <input
              type="search"
              placeholder="Search code or name…"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="crt-num h-10 min-w-[200px] flex-1 rounded-sm border border-zinc-300 bg-white px-3 text-xs text-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary dark:border-zinc-600 dark:bg-zinc-900"
              data-testid="audit-search-input"
            />
            <select
              data-testid="filter-process"
              value={filter.process}
              onChange={(e) => setFilter((f) => ({ ...f, process: e.target.value }))}
              className="crt-num h-10 rounded-sm border border-zinc-300 bg-white px-3 text-xs uppercase tracking-wider text-foreground outline-none focus:border-primary dark:border-zinc-600 dark:bg-zinc-900"
            >
              <option value="">All processes</option>
              {processes.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
            <select
              data-testid="filter-criticality"
              value={filter.crit}
              onChange={(e) => setFilter((f) => ({ ...f, crit: e.target.value }))}
              className="crt-num h-10 rounded-sm border border-zinc-300 bg-white px-3 text-xs uppercase tracking-wider text-foreground outline-none focus:border-primary dark:border-zinc-600 dark:bg-zinc-900"
            >
              <option value="">All criticality</option>
              {criticalities.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            <select
              value={filter.sort}
              onChange={(e) => setFilter((f) => ({ ...f, sort: e.target.value }))}
              className="crt-num h-10 rounded-sm border border-zinc-300 bg-white px-3 text-xs uppercase tracking-wider text-foreground outline-none focus:border-primary dark:border-zinc-600 dark:bg-zinc-900"
              data-testid="audit-sort-select"
            >
              <option value="code">Sort: code</option>
              <option value="code_desc">Sort: code (Z–A)</option>
              <option value="name">Sort: name</option>
              <option value="criticality">Sort: criticality</option>
              <option value="exceptions">Sort: exceptions</option>
              <option value="last_run">Sort: last run</option>
            </select>
          </div>
          <div className="flex flex-wrap gap-1.5" data-testid="audit-status-chips">
            {STATUS_CHIPS.map((chip) => (
              <button
                key={chip.id || "all"}
                type="button"
                onClick={() => setFilter((f) => ({ ...f, status: chip.id }))}
                className={clsx(
                  "crt-num rounded-sm border px-2.5 py-1 text-[10px] uppercase tracking-wider transition-colors",
                  filter.status === chip.id
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-zinc-300 text-muted-foreground hover:bg-zinc-100 dark:border-zinc-600 dark:hover:bg-zinc-900"
                )}
              >
                {chip.label}
              </button>
            ))}
          </div>
        </SectionCard>
        </div>

        {catalogEmpty ? (
          <div
            className="crt-num mb-4 rounded-sm border border-dashed border-zinc-300 p-8 text-center text-xs text-muted-foreground dark:border-zinc-700"
            data-testid="audit-empty-catalog"
          >
            No controls in catalog. Seed the environment or check admin configuration.
          </div>
        ) : null}

        {allGreen && !listFiltered && !catalogEmpty ? (
          <div
            className="crt-num mb-4 flex items-center gap-3 rounded-sm border border-[hsl(var(--chart-4))]/30 bg-[hsl(var(--chart-4))]/10 p-6 text-sm text-foreground"
            data-testid="audit-empty-all-green"
          >
            <Sparkle size={20} weight="fill" className="text-[hsl(var(--chart-4))]" />
            <div>
              <div className="font-medium">All controls green in scope</div>
              <div className="mt-1 text-xs text-muted-foreground">
                No failing, stale, or critical/high failures · {summary.open_exceptions_count ?? 0} open exceptions
              </div>
            </div>
          </div>
        ) : null}

        {filterEmpty ? (
          <div
            className="crt-num mb-4 rounded-sm border border-dashed border-zinc-300 p-6 text-center text-xs text-muted-foreground dark:border-zinc-700"
            data-testid="audit-empty-filters"
          >
            No controls match the current filters.
            {listFiltered ? (
              <button
                type="button"
                className="mt-2 block w-full text-primary hover:underline"
                onClick={() => {
                  setSearchInput("");
                  setFilter({ process: "", crit: "", status: "", q: "", sort: "code" });
                }}
              >
                Clear all filters
              </button>
            ) : null}
          </div>
        ) : null}

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
          <SectionCard
            className="lg:col-span-2"
            kicker="CONTROLS"
            title="Control list"
            bodyClassName="p-0"
            data-testid="control-list"
          >
            <DataTable
              className="rounded-none border-0 bg-transparent"
              maxHeightClassName="max-h-[70vh]"
              testId="audit-control-list-table"
            >
              <DataTableHead>
                <tr>
                  <DataTableTh>Code</DataTableTh>
                  <DataTableTh>Control</DataTableTh>
                  <DataTableTh align="center">Status</DataTableTh>
                  <DataTableTh align="right">Last run</DataTableTh>
                  <DataTableTh align="center">Exc</DataTableTh>
                  {AUDIT_WORKSPACE_V2 ? <DataTableTh align="center">Trend</DataTableTh> : null}
                </tr>
              </DataTableHead>
              <DataTableBody>
                {filterEmpty ? (
                  <tr>
                    <td colSpan={AUDIT_WORKSPACE_V2 ? 6 : 5} className="crt-num p-8 text-center text-xs text-muted-foreground">
                      Adjust filters to see controls.
                    </td>
                  </tr>
                ) : null}
                {controls.map((c) => {
                  const stale = controlIsStale(c);
                  const badge = controlListStatus(c);
                  const relativeRun = formatRelativeRun(c.last_run_at);
                  return (
                    <DataTableRow
                      key={c.id}
                      onClick={() => selectControl(c.id)}
                      testId={`control-row-${c.code}`}
                      className={clsx(
                        selected === c.id &&
                          "bg-zinc-100 ring-1 ring-inset ring-primary/20 dark:bg-zinc-900/80 dark:ring-primary/30",
                        stale && "border-l-2 border-l-[hsl(var(--chart-3))]"
                      )}
                    >
                      <DataTableTd className="crt-num text-xs text-zinc-800 dark:text-zinc-200">{c.code}</DataTableTd>
                      <DataTableTd>
                        <div className="max-w-xs truncate text-sm font-medium text-zinc-900 dark:text-zinc-50">
                          {c.name}
                        </div>
                        <div className="crt-num mt-0.5 flex flex-wrap gap-1 text-[10px] text-zinc-600 dark:text-zinc-400">
                          <span>{c.process}</span>
                          <span>·</span>
                          <span>{c.criticality}</span>
                        </div>
                      </DataTableTd>
                      <DataTableTd align="center">
                        <span
                          className={clsx(
                            "crt-num inline-block rounded-sm border px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wider",
                            badge.key === "pass" && "border-[hsl(var(--chart-4))]/40 text-[hsl(var(--chart-4))]",
                            badge.key === "fail" && "border-[hsl(var(--destructive))]/40 text-[hsl(var(--destructive))]",
                            badge.key === "stale" && "border-[hsl(var(--chart-3))]/40 text-[hsl(var(--chart-3))]",
                            badge.key === "not_run" && "border-zinc-300 text-muted-foreground dark:border-zinc-600"
                          )}
                        >
                          {badge.label}
                        </span>
                      </DataTableTd>
                      <DataTableTd align="right" className="crt-num text-[10px] text-muted-foreground whitespace-nowrap">
                        {relativeRun ?? "—"}
                      </DataTableTd>
                      <DataTableTd align="center">
                        {c.last_run_exceptions == null ? (
                          <span className="crt-num text-[10px] text-muted-foreground">—</span>
                        ) : c.last_run_exceptions === 0 ? (
                          <CheckCircle size={14} weight="fill" className="mx-auto text-[hsl(var(--chart-4))]" />
                        ) : (
                          <span className="crt-num text-xs tabular-nums text-[hsl(var(--chart-3))]">{c.last_run_exceptions}</span>
                        )}
                      </DataTableTd>
                      {AUDIT_WORKSPACE_V2 ? (
                        <DataTableTd align="center">
                          <ControlRunSparkline points={sparklineByControl[c.id]} />
                        </DataTableTd>
                      ) : null}
                    </DataTableRow>
                  );
                })}
              </DataTableBody>
            </DataTable>
          </SectionCard>

          <div ref={detailRef} className="lg:col-span-3">
          <SectionCard className="min-h-[500px]" kicker="DETAIL" title="Control detail" data-testid="control-detail">
            {detail?.control ? (
              <>
                <div className="mb-5 flex items-start justify-between gap-3">
                  <div>
                    <div className="crt-num text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                      <Link
                        to={`/app/drill/control/${encodeURIComponent(detail.control.code)}`}
                        className="text-primary hover:underline"
                      >
                        {detail.control.code}
                      </Link>
                      {" · "}
                      {detail.control.framework}
                    </div>
                    <h2 className="font-display mt-1 text-2xl tracking-tight text-foreground">{detail.control.name}</h2>
                    <div className="crt-num mt-1 text-[10px] uppercase tracking-wider text-zinc-600 dark:text-zinc-400">
                      {detail.control.process} · {detail.control.criticality} · {detail.control.frequency}
                    </div>
                  </div>
                  {canRun ? (
                    <button
                      data-testid="run-control-btn"
                      type="button"
                      onClick={() => run(selected)}
                      disabled={running}
                      className="flex h-10 shrink-0 items-center gap-2 rounded-sm border border-primary bg-primary px-4 text-xs font-medium uppercase tracking-wider text-white transition-opacity hover:opacity-90 disabled:opacity-50"
                    >
                      <Play size={12} weight="fill" /> {running ? "Running..." : "Run now"}
                    </button>
                  ) : (
                    <span className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground" data-testid="audit-run-disabled">
                      Run disabled (read-only)
                    </span>
                  )}
                </div>
                <p className="mb-6 text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">{detail.control.description}</p>

                <div className="mb-6 grid grid-cols-1 gap-3 md:grid-cols-3">
                  <div className="rounded-sm border border-zinc-200 bg-zinc-50/80 p-4 dark:border-zinc-800 dark:bg-zinc-900/40">
                    <div className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">Last run</div>
                    <div className="crt-num mt-1 text-sm text-foreground">{fmtDateTime(detail.control.last_run_at)}</div>
                  </div>
                  <div className="rounded-sm border border-zinc-200 bg-zinc-50/80 p-4 dark:border-zinc-800 dark:bg-zinc-900/40">
                    <div className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">Status</div>
                    <div
                      className={clsx(
                        "crt-num mt-1 text-sm font-medium",
                        detail.control.last_run_pass === true && "text-[hsl(var(--chart-4))]",
                        detail.control.last_run_pass === false && "text-[hsl(var(--destructive))]",
                        detail.control.last_run_pass !== true &&
                          detail.control.last_run_pass !== false &&
                          "text-muted-foreground"
                      )}
                    >
                      {detail.control.last_run_pass === true ? "PASS" : detail.control.last_run_pass === false ? "FAIL" : "—"}
                    </div>
                  </div>
                  <div className="rounded-sm border border-zinc-200 bg-zinc-50/80 p-4 dark:border-zinc-800 dark:bg-zinc-900/40">
                    <div className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">Exceptions</div>
                    <div className="crt-num mt-1 text-2xl tabular-nums text-foreground">{detail.control.last_run_exceptions ?? "—"}</div>
                  </div>
                </div>

                <h4 className="crt-num mb-3 text-[10px] uppercase tracking-[0.15em] text-muted-foreground">Recent runs</h4>
                <div className="mb-6 space-y-1">
                  {detail.recent_runs.slice(0, 8).map((r) => (
                    <div key={r.id} className="flex items-center justify-between border-b border-zinc-200 py-1.5 text-xs dark:border-zinc-800">
                      <span className="crt-num text-zinc-700 dark:text-zinc-300">{fmtDateTime(r.run_ts)}</span>
                      <span className="crt-num text-muted-foreground">{r.status}</span>
                      <span
                        className={clsx(
                          "crt-num tabular-nums",
                          r.exceptions_count > 0 ? "text-[hsl(var(--chart-3))]" : "text-[hsl(var(--chart-4))]"
                        )}
                      >
                        {r.exceptions_count} exc
                      </span>
                    </div>
                  ))}
                </div>

                <h4 className="crt-num mb-3 text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
                  Open exceptions ({detail.open_exceptions.length})
                  {detail.filters_applied && Object.keys(detail.filters_applied).length > 0 ? (
                    <span className="ml-2 font-mono normal-case text-muted-foreground"> · master filters</span>
                  ) : null}
                </h4>
                <div className="max-h-80 space-y-2 overflow-y-auto">
                  {detail.open_exceptions.map((e) => (
                    <div
                      key={e.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => nav(`/app/evidence/${e.id}`)}
                      onKeyDown={(ev) => {
                        if (ev.key === "Enter" || ev.key === " ") {
                          ev.preventDefault();
                          nav(`/app/evidence/${e.id}`);
                        }
                      }}
                      className="cursor-pointer rounded-sm border border-zinc-200 bg-zinc-50/80 p-4 text-xs transition-colors hover:bg-zinc-100/90 dark:border-zinc-800 dark:bg-zinc-900/40 dark:hover:bg-zinc-900/70"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-foreground">{e.title}</div>
                          <div className="crt-num mt-0.5 text-[10px] text-muted-foreground">
                            {e.entity} · {e.source_record_id}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Warning
                            size={12}
                            className={e.severity === "critical" ? "text-[hsl(var(--destructive))]" : "text-[hsl(var(--chart-3))]"}
                          />
                          <span className="crt-num tabular-nums text-foreground">
                            {e.financial_exposure ? fmtUSD(e.financial_exposure) : "—"}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="crt-num text-xs text-muted-foreground">Select a control to view details</div>
            )}
          </SectionCard>
          </div>
        </div>
      </div>
    </PageShell>
  );
}
