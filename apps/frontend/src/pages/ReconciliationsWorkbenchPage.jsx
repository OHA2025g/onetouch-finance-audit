import React, { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import { useNavigate } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { StatCard } from "../components/StatCard";
import { SeverityBadge } from "../components/Badges";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { fmtUSD, fmtDate } from "../lib/format";
import { errorMessageFromAxios } from "../lib/apiErrorMessage";

function workflowSeverity(status) {
  const s = (status || "open").toLowerCase();
  if (s === "approved") return "low";
  if (s === "submitted") return "medium";
  return "warning";
}

export default function ReconciliationsWorkbenchPage() {
  const navigate = useNavigate();
  const { hrefWithMasterParams } = useMastersFilters();
  const [items, setItems] = useState(null);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);

  const params = useDashboardFilterParams();

  const refresh = useCallback(() => {
    setLoading(true);
    const qp = { ...params, limit: 50, offset: 0 };
    return Promise.all([http.get("/reconciliations/summary", { params }), http.get("/reconciliations", { params: qp })])
      .then(([sumRes, listRes]) => {
        setSummary(sumRes.data || {});
        setItems(listRes.data?.items || []);
      })
      .catch((e) => toast.error(errorMessageFromAxios(e, "Failed to load reconciliations")))
      .finally(() => setLoading(false));
  }, [params]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const openRecon = useCallback(
    (rec) => {
      if (!rec?.id) return;
      navigate(hrefWithMasterParams(`/app/reconciliations/${encodeURIComponent(rec.id)}`));
    },
    [hrefWithMasterParams, navigate],
  );

  if (loading && items === null) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="recon-workbench-loading">
        Loading reconciliation suite…
      </div>
    );
  }

  const k = summary?.kpis || {};
  const byType = summary?.by_type || [];
  const byEntity = summary?.by_entity || [];
  const topVariance = summary?.top_entities_by_variance || [];
  const topOverdue = summary?.top_entities_by_overdue || [];
  const rows = items || [];

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="recon-workbench-page" data-reconciliation-suite-surface="true">
        <PageHeader
          kicker="RECONCILIATIONS · PHASE 17"
          title="Reconciliation management suite"
          subtitle="Portfolio KPIs, workflow queue, and drill-down — submit · approve · evidence · cases on detail."
        />

        <MastersFilterStrip className="mb-6" />

        {params.entity_code || params.period_ym ? (
          <p className="crt-num mb-4 text-[10px] uppercase tracking-wider text-muted-foreground">
            Scope: {params.entity_code || "All entities"}
            {params.period_ym ? ` · period ${params.period_ym}` : ""}
            {k.scanned != null && k.total_reconciliations != null ? (
              <span>
                {" "}
                · scanned {k.scanned} of {k.total_reconciliations}
              </span>
            ) : null}
          </p>
        ) : null}

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-4" data-testid="recon-kpi-strip">
          <StatCard label="Total in scope" value={k.total_reconciliations ?? rows.length} testId="recon-kpi-total" />
          <StatCard label="Open" value={k.open_count ?? 0} severity="warning" testId="recon-kpi-open" />
          <StatCard label="Submitted" value={k.submitted_count ?? 0} severity="medium" testId="recon-kpi-submitted" />
          <StatCard label="Approved" value={k.approved_count ?? 0} severity="low" testId="recon-kpi-approved" />
          <StatCard label="Overdue" value={k.overdue_count ?? 0} severity="critical" testId="recon-kpi-overdue" />
          <StatCard
            label="% overdue"
            value={k.pct_overdue != null ? `${k.pct_overdue}%` : "—"}
            severity={Number(k.pct_overdue) >= 20 ? "critical" : "warning"}
            testId="recon-kpi-pct-overdue"
          />
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-4">
          <StatCard
            label="Outside tolerance"
            value={k.outside_tolerance_count ?? 0}
            severity="critical"
            testId="recon-kpi-outside-tolerance"
          />
          <StatCard
            label="% outside tol."
            value={k.pct_outside_tolerance != null ? `${k.pct_outside_tolerance}%` : "—"}
            severity="warning"
            testId="recon-kpi-pct-outside"
          />
          <StatCard label="$ abs variance (scan)" value={fmtUSD(k.abs_variance_total)} testId="recon-kpi-abs-variance" />
          <StatCard
            label="$ outside tolerance"
            value={fmtUSD(k.outside_tolerance_variance)}
            severity="critical"
            testId="recon-kpi-outside-variance"
          />
          <StatCard label="Missing evidence" value={k.no_evidence_count ?? 0} severity="warning" testId="recon-kpi-no-evidence" />
          <StatCard
            label="Avg days to approve"
            value={k.avg_days_to_approve != null ? k.avg_days_to_approve : "—"}
            testId="recon-kpi-avg-approve-days"
          />
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <StatCard label="Escalated to case" value={k.escalated_to_case_count ?? 0} testId="recon-kpi-escalated" />
          <StatCard
            label="Open linked cases"
            value={k.open_linked_cases_count ?? 0}
            severity="warning"
            testId="recon-kpi-open-cases"
          />
          <StatCard label="Recs w/ open case" value={k.reconciliations_with_open_case_count ?? 0} testId="recon-kpi-recs-open-case" />
          <StatCard label="In table view" value={rows.length} testId="recon-kpi-table-rows" />
        </div>

        <div className="mb-6 flex flex-wrap gap-2" data-testid="recon-status-chips">
          <span className="crt-num inline-flex items-center gap-1.5 rounded-full border border-amber-300/70 bg-amber-50 px-3 py-1 text-[10px] uppercase tracking-wider text-amber-900 dark:border-amber-800/50 dark:bg-amber-950/40 dark:text-amber-100">
            Open {k.open_count ?? 0}
          </span>
          <span className="crt-num inline-flex items-center gap-1.5 rounded-full border border-sky-300/70 bg-sky-50 px-3 py-1 text-[10px] uppercase tracking-wider text-sky-900 dark:border-sky-800/50 dark:bg-sky-950/40 dark:text-sky-100">
            Submitted {k.submitted_count ?? 0}
          </span>
          <span className="crt-num inline-flex items-center gap-1.5 rounded-full border border-emerald-300/70 bg-emerald-50 px-3 py-1 text-[10px] uppercase tracking-wider text-emerald-900 dark:border-emerald-800/50 dark:bg-emerald-950/40 dark:text-emerald-100">
            Approved {k.approved_count ?? 0}
          </span>
          <span className="crt-num inline-flex items-center gap-1.5 rounded-full border border-rose-300/70 bg-rose-50 px-3 py-1 text-[10px] uppercase tracking-wider text-rose-900 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-100">
            Overdue {k.overdue_count ?? 0}
          </span>
        </div>

        {byType.length > 0 ? (
          <SectionCard kicker="MIX" title="By reconciliation type" className="mb-6">
            <div className="flex flex-wrap gap-2 p-4" data-testid="recon-by-type">
              {byType.map((row) => (
                <span
                  key={row.type}
                  className="crt-num rounded-full border border-zinc-200 bg-zinc-50 px-3 py-1 text-[10px] uppercase tracking-wider text-zinc-800 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200"
                >
                  {row.type} · {row.count} · {fmtUSD(row.abs_variance)} · {fmtUSD(row.abs_variance)}
                </span>
              ))}
            </div>
          </SectionCard>
        ) : null}

        {byEntity.length > 0 ? (
          <div className="mb-6 grid grid-cols-1 gap-4 xl:grid-cols-2">
            <SectionCard kicker="ENTITY" title="By entity">
              <div className="space-y-2 p-4" data-testid="recon-by-entity">
                {byEntity.slice(0, 8).map((row) => (
                  <div key={row.entity} className="flex justify-between text-xs">
                    <span className="text-foreground">{row.entity}</span>
                    <span className="crt-num text-muted-foreground">
                      {row.count} · {fmtUSD(row.abs_variance)}
                      {row.overdue_count > 0 ? ` · ${row.overdue_count} overdue` : ""}
                    </span>
                  </div>
                ))}
              </div>
            </SectionCard>
            <SectionCard kicker="TOP" title="Largest variance entities">
              <div className="space-y-2 p-4" data-testid="recon-top-entities-variance">
                {topVariance.map((row) => (
                  <div key={row.entity} className="flex justify-between text-xs">
                    <span className="text-foreground">{row.entity}</span>
                    <span className="crt-num tabular-nums text-foreground">{fmtUSD(row.abs_variance)}</span>
                  </div>
                ))}
              </div>
              {topOverdue.length > 0 ? (
                <div className="mt-4 border-t border-zinc-200 pt-4 dark:border-zinc-700">
                  <p className="crt-num mb-2 text-[10px] uppercase text-muted-foreground">Most overdue</p>
                  {topOverdue.map((row) => (
                    <div key={`od-${row.entity}`} className="flex justify-between text-xs py-1">
                      <span>{row.entity}</span>
                      <span className="crt-num text-rose-600 dark:text-rose-400">{row.overdue_count} overdue</span>
                    </div>
                  ))}
                </div>
              ) : null}
            </SectionCard>
          </div>
        ) : null}

        <SectionCard kicker="QUEUE" title="Reconciliations">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[62vh]" testId="recon-list-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Type</DataTableTh>
                <DataTableTh>Entity</DataTableTh>
                <DataTableTh>Period</DataTableTh>
                <DataTableTh>Workflow</DataTableTh>
                <DataTableTh>Flags</DataTableTh>
                <DataTableTh>Due</DataTableTh>
                <DataTableTh align="right">Variance</DataTableTh>
                <DataTableTh align="right">Evidence</DataTableTh>
                <DataTableTh />
              </tr>
            </DataTableHead>
            <DataTableBody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={9} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                    No reconciliations in scope.
                  </td>
                </tr>
              ) : null}
              {rows.map((rec) => {
                const wf = rec.workflow_status || rec.status || "open";
                return (
                  <DataTableRow key={rec.id} testId={`recon-row-${rec.id}`} onClick={() => openRecon(rec)}>
                    <DataTableTd className="text-sm text-foreground">{rec.reconciliation_type || "—"}</DataTableTd>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{rec.entity || "—"}</DataTableTd>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{rec.period || "—"}</DataTableTd>
                    <DataTableTd>
                      <SeverityBadge severity={workflowSeverity(wf)} />
                      <span className="crt-num ml-2 text-[10px] uppercase text-muted-foreground">{wf}</span>
                    </DataTableTd>
                    <DataTableTd>
                      <div className="flex flex-wrap gap-1">
                        {rec.is_overdue ? (
                          <span className="crt-num rounded border border-rose-400/60 px-1.5 py-0.5 text-[9px] uppercase text-rose-700 dark:text-rose-300">
                            Overdue
                          </span>
                        ) : null}
                        {rec.outside_tolerance ? (
                          <span className="crt-num rounded border border-amber-400/60 px-1.5 py-0.5 text-[9px] uppercase text-amber-800 dark:text-amber-200">
                            O/T tol
                          </span>
                        ) : null}
                        {!rec.has_evidence ? (
                          <span className="crt-num rounded border border-zinc-300 px-1.5 py-0.5 text-[9px] uppercase text-muted-foreground">
                            No ev
                          </span>
                        ) : null}
                      </div>
                    </DataTableTd>
                    <DataTableTd className="crt-num text-xs text-muted-foreground">{fmtDate(rec.due_date)}</DataTableTd>
                    <DataTableTd
                      align="right"
                      className={clsx(
                        "crt-num tabular-nums",
                        rec.outside_tolerance ? "font-medium text-rose-700 dark:text-rose-300" : "text-foreground",
                      )}
                    >
                      {fmtUSD(rec.variance_amount)}
                    </DataTableTd>
                    <DataTableTd align="right" className="crt-num tabular-nums text-xs text-muted-foreground">
                      {rec.evidence_count ?? 0}
                    </DataTableTd>
                    <DataTableTd className="w-[120px]">
                      {rec.id ? (
                        <span className="crt-num text-[10px] uppercase tracking-wider text-primary">Open →</span>
                      ) : (
                        "—"
                      )}
                    </DataTableTd>
                  </DataTableRow>
                );
              })}
            </DataTableBody>
          </DataTable>
        </SectionCard>
      </div>
    </PageShell>
  );
}
