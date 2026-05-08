import React, { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { http } from "../lib/api";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { buildDashboardFilterParams } from "../lib/mastersDashboardParams";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { StatCard } from "../components/StatCard";
import { SeverityBadge } from "../components/Badges";
import { fmtUSD, fmtDate } from "../lib/format";
import { toast } from "sonner";
import InsightPanel from "../components/InsightPanel";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { exceptionSourceDrillPath } from "../lib/drillPaths";
import clsx from "clsx";

export default function ControllerDashboard() {
  const [d, setD] = useState(null);
  const nav = useNavigate();
  const { entityCode, periodYm, periodExplicit, departmentId, costCenterId } = useMastersFilters();

  useEffect(() => {
    const params = buildDashboardFilterParams({
      entityCode,
      periodYm,
      periodExplicit,
      departmentId,
      costCenterId,
    });
    http
      .get("/dashboard/controller", { params })
      .then((r) => setD(r.data))
      .catch(() => toast.error("Load failed"));
  }, [entityCode, periodYm, periodExplicit, departmentId, costCenterId]);

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="controller-loading">
        Loading controller view…
      </div>
    );
  }
  const k = d.kpis;

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="controller-dashboard">
        <PageHeader
          kicker="FINANCIAL CONTROLLER"
          title="Close control room"
          subtitle="Stay ahead of close-impacting exceptions, reconciliations, and AP risk."
        />

        <MastersFilterStrip className="mb-6" />
        {(entityCode || periodExplicit || departmentId || costCenterId) && (
          <p className="crt-num mb-4 text-[10px] uppercase tracking-wider text-muted-foreground">
            KPIs and lists are scoped on the server when reporting context is set (Phase 4).
          </p>
        )}

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
          <StatCard label="Close blockers" value={k.close_blockers} severity="critical" testId="kpi-blockers" />
          <StatCard label="Manual JE breaches" value={k.manual_je_breaches} severity="warning" testId="kpi-je" />
          <StatCard label="Backdated journals" value={k.backdated_journals} severity="critical" testId="kpi-backdated" />
          <StatCard label="AP exception queue" value={k.ap_exception_count} testId="kpi-ap" />
          <StatCard label="Recons overdue" value={k.reconciliations_overdue} unit={`/${k.reconciliations_total}`} severity="warning" testId="kpi-recons" />
          <StatCard label="Total recons" value={k.reconciliations_total} testId="kpi-recons-total" />
        </div>

        <InsightPanel section="controller" title="Controller AI Insights" />

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <SectionCard kicker="CLOSE" title="Reconciliations">
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[55vh]" testId="controller-reconciliations-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>Type / Entity</DataTableTh>
                  <DataTableTh>Period</DataTableTh>
                  <DataTableTh align="right">Variance</DataTableTh>
                  <DataTableTh>Status</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {d.reconciliations.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                      No reconciliations match the current reporting context.
                    </td>
                  </tr>
                ) : null}
                {d.reconciliations.map(r => (
                  <DataTableRow
                    key={r.id}
                    testId={`recon-${r.id}`}
                    onClick={() => nav(`/app/reconciliations/${encodeURIComponent(r.id)}`)}
                    className="cursor-pointer"
                  >
                    <DataTableTd>
                      <div className="truncate font-medium text-zinc-900 dark:text-zinc-50">
                        {r.reconciliation_type}
                      </div>
                      <div className="crt-num mt-0.5 text-[10px] text-zinc-600 dark:text-zinc-400">{r.entity}</div>
                    </DataTableTd>
                    <DataTableTd className="crt-num text-xs text-zinc-700 dark:text-zinc-300">{r.period}</DataTableTd>
                    <DataTableTd
                      align="right"
                      className={clsx(
                        "crt-num tabular-nums",
                        Math.abs(r.variance_amount) > 5000 ? "text-[hsl(var(--destructive))]" : "text-muted-foreground"
                      )}
                    >
                      {fmtUSD(r.variance_amount)}
                    </DataTableTd>
                    <DataTableTd>
                      <span
                        className={clsx(
                          "crt-num rounded-sm px-2 py-0.5 text-[10px] uppercase tracking-wider",
                          r.status === "overdue" && "bg-[hsl(var(--destructive)/0.12)] text-[hsl(var(--destructive))]",
                          r.status === "closed" && "bg-[hsl(var(--chart-4)/0.12)] text-[hsl(var(--chart-4))]",
                          r.status !== "overdue" && r.status !== "closed" && "bg-[hsl(var(--chart-3)/0.12)] text-[hsl(var(--chart-3))]"
                        )}
                      >
                        {r.status}
                      </span>
                    </DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          </SectionCard>

          <SectionCard kicker="ACCOUNTS PAYABLE" title="Top AP exceptions">
          <div className="space-y-2">
            {d.ap_exceptions.length === 0 ? (
              <p className="crt-num px-2 py-6 text-center text-xs text-muted-foreground">
                No AP exceptions match the current reporting context.
              </p>
            ) : null}
            {d.ap_exceptions.map(e => {
              const srcPath = exceptionSourceDrillPath(e);
              return (
                <div
                  key={e.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => nav(`/app/evidence/${e.id}`)}
                  onKeyDown={(ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); nav(`/app/evidence/${e.id}`); } }}
                  className="w-full cursor-pointer rounded-sm border border-zinc-200 bg-zinc-50/80 p-4 text-left transition-colors hover:bg-zinc-100/90 dark:border-zinc-800 dark:bg-zinc-900/40 dark:hover:bg-zinc-900/70"
                  data-testid={`ap-exc-${e.id}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm text-foreground">{e.title}</div>
                      <div className="crt-num mt-0.5 text-[10px] text-muted-foreground">
                        {e.control_code ? (
                          <Link
                            to={`/app/drill/control/${encodeURIComponent(e.control_code)}`}
                            onClick={(ev) => ev.stopPropagation()}
                            className="text-primary hover:underline"
                          >
                            {e.control_code}
                          </Link>
                        ) : "—"}
                        {" · "}{e.entity} · {fmtDate(e.detected_at)}
                      </div>
                    </div>
                    <SeverityBadge severity={e.severity} />
                  </div>
                  <div className="crt-num mt-2 text-sm tabular-nums text-[hsl(var(--destructive))]">{fmtUSD(e.financial_exposure)}</div>
                  <div className="crt-num mt-3 flex flex-wrap gap-2 text-[9px] uppercase tracking-wider" onClick={(ev) => ev.stopPropagation()}>
                    {srcPath ? (
                      <Link
                        to={srcPath}
                        className="rounded-sm border border-zinc-300 bg-white px-2 py-1 text-primary transition-colors hover:bg-zinc-50 dark:border-zinc-600 dark:bg-zinc-950 dark:hover:bg-zinc-900"
                      >
                        Source record
                      </Link>
                    ) : null}
                  </div>
                </div>
              );
            })}
          </div>
          </SectionCard>
        </div>
      </div>
    </PageShell>
  );
}
