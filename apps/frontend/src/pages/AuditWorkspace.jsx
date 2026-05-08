import React, { useCallback, useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { fmtDateTime } from "../lib/format";
import { Play, CheckCircle, Warning } from "@phosphor-icons/react";
import clsx from "clsx";
import InsightPanel from "../components/InsightPanel";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { buildDashboardFilterParams } from "../lib/mastersDashboardParams";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";

export default function AuditWorkspace() {
  const nav = useNavigate();
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [running, setRunning] = useState(false);
  const [filter, setFilter] = useState({ process: "", crit: "" });
  const { entityCode, periodYm, periodExplicit, departmentId, costCenterId } = useMastersFilters();

  const scopeParams = useCallback(
    () =>
      buildDashboardFilterParams({
        entityCode,
        periodYm,
        periodExplicit,
        departmentId,
        costCenterId,
      }),
    [entityCode, periodYm, periodExplicit, departmentId, costCenterId]
  );

  const load = useCallback(async () => {
    const { data: d } = await http.get("/dashboard/audit", { params: scopeParams() });
    setData(d);
    setSelected((prev) => {
      if (!d.controls.length) return null;
      if (prev && d.controls.some((c) => c.id === prev)) return prev;
      return d.controls[0].id;
    });
  }, [scopeParams]);

  useEffect(() => {
    load().catch(() => toast.error("Failed to load audit workspace"));
  }, [load]);

  useEffect(() => {
    if (!selected) return;
    http
      .get(`/controls/${selected}`, { params: scopeParams() })
      .then((r) => setDetail(r.data))
      .catch(() => toast.error("Failed to load control"));
  }, [selected, scopeParams]);

  const run = async () => {
    if (!selected) return;
    setRunning(true);
    try {
      const { data: r } = await http.post(`/controls/${selected}/run`);
      toast.success(`Run complete · ${r.exceptions} exceptions`);
      await load();
      const { data: det } = await http.get(`/controls/${selected}`, { params: scopeParams() });
      setDetail(det);
    } catch {
      toast.error("Run failed");
    }
    setRunning(false);
  };

  if (!data) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="audit-workspace-loading">
        Loading audit workspace…
      </div>
    );
  }

  const controls = data.controls.filter(
    (c) => (!filter.process || c.process === filter.process) && (!filter.crit || c.criticality === filter.crit)
  );
  const processes = [...new Set(data.controls.map((c) => c.process))];
  const criticalities = [...new Set(data.controls.map((c) => c.criticality))];

  return (
    <PageShell maxWidth="max-w-[1800px]">
      <div data-testid="audit-workspace">
        <PageHeader
          kicker="INTERNAL AUDIT"
          title="Control library"
          subtitle="Browse controls, run tests, review exceptions, and capture evidence-ready documentation."
        />

        <MastersFilterStrip className="mb-4" />

        <InsightPanel section="audit" title="Audit Workspace · AI Insights" />

        <SectionCard
          kicker="FILTERS"
          title="Control selection"
          right={
            <span className="crt-num text-xs text-muted-foreground">
              {controls.length} / {data.controls.length} controls
            </span>
          }
          className="mb-4"
          bodyClassName="p-4"
        >
          <div className="flex flex-wrap items-center gap-2">
            <select
              data-testid="filter-process"
              value={filter.process}
              onChange={(e) => setFilter((f) => ({ ...f, process: e.target.value }))}
              className="crt-num h-10 rounded-sm border border-zinc-300 bg-white px-3 text-xs uppercase tracking-wider text-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100"
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
              className="crt-num h-10 rounded-sm border border-zinc-300 bg-white px-3 text-xs uppercase tracking-wider text-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100"
            >
              <option value="">All criticality</option>
              {criticalities.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
        </SectionCard>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
          {/* Control list */}
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
                  <DataTableTh align="center">Last</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {controls.map((c) => (
                  <DataTableRow
                    key={c.id}
                    onClick={() => setSelected(c.id)}
                    testId={`control-row-${c.code}`}
                    className={clsx(
                      selected === c.id &&
                        "bg-zinc-100 ring-1 ring-inset ring-primary/20 dark:bg-zinc-900/80 dark:ring-primary/30"
                    )}
                  >
                    <DataTableTd className="crt-num text-xs text-zinc-800 dark:text-zinc-200">{c.code}</DataTableTd>
                    <DataTableTd>
                      <div className="max-w-xs truncate text-sm font-medium text-zinc-900 dark:text-zinc-50">{c.name}</div>
                      <div className="crt-num mt-0.5 text-[10px] text-zinc-600 dark:text-zinc-400">
                        {c.process} · {c.criticality}
                      </div>
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
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          </SectionCard>

          {/* Detail */}
          <SectionCard className="min-h-[500px] lg:col-span-3" kicker="DETAIL" title="Control detail" data-testid="control-detail">
            {detail?.control ? (
              <>
                <div className="mb-5 flex items-start justify-between">
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
                  <button
                    data-testid="run-control-btn"
                    type="button"
                    onClick={run}
                    disabled={running}
                    className="flex h-10 items-center gap-2 rounded-sm border border-primary bg-primary px-4 text-xs font-medium uppercase tracking-wider text-white transition-opacity hover:opacity-90 disabled:opacity-50"
                  >
                    <Play size={12} weight="fill" /> {running ? "Running..." : "Run now"}
                  </button>
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
                            {e.financial_exposure ? `$${(e.financial_exposure / 1000).toFixed(1)}K` : "—"}
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
    </PageShell>
  );
}
