import React, { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { http } from "../lib/api";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { StatCard } from "../components/StatCard";
import { SeverityBadge, StatusBadge, PriorityTag } from "../components/Badges";
import { fmtUSD, fmtDate, daysFromNow } from "../lib/format";
import { toast } from "sonner";
import { ArrowRight } from "@phosphor-icons/react";
import InsightPanel from "../components/InsightPanel";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";

export default function MyCases() {
  const [d, setD] = useState(null);
  const nav = useNavigate();
  const dashboardParams = useDashboardFilterParams();

  useEffect(() => {
    http
      .get("/dashboard/my-cases", { params: dashboardParams })
      .then((r) => setD(r.data))
      .catch(() => toast.error("Load failed"));
  }, [dashboardParams]);

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="my-cases-loading">
        Loading your queue…
      </div>
    );
  }

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="my-cases">
        <PageHeader
          kicker="MY WORK"
          title="My cases"
          subtitle="Your assigned remediation queue with SLA context and evidence-first drilldowns."
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-6">
          <StatCard label="Open cases" value={d.kpis.my_open_cases} testId="kpi-mine-open" />
          <StatCard label="Overdue" value={d.kpis.overdue} severity={d.kpis.overdue > 0 ? "critical" : "success"} testId="kpi-mine-overdue" />
          <StatCard label="Total assigned" value={d.kpis.total_assigned} testId="kpi-mine-total" />
        </div>

        <InsightPanel section="my-cases" title="My Work · AI Insights" />

        {d.cases.length === 0 ? (
          <SectionCard kicker="QUEUE" title="Assigned cases">
            <div className="crt-num py-10 text-center text-xs text-muted-foreground">
              No cases assigned to you.
            </div>
          </SectionCard>
        ) : (
          <SectionCard kicker="QUEUE" title={`Assigned cases (${d.cases.length})`} bodyClassName="p-0">
            <DataTable maxHeightClassName="max-h-[65vh]" testId="my-cases-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>Case</DataTableTh>
                  <DataTableTh className="w-24">Priority</DataTableTh>
                  <DataTableTh className="w-28">Severity</DataTableTh>
                  <DataTableTh className="w-32">Status</DataTableTh>
                  <DataTableTh className="w-36">Org slice</DataTableTh>
                  <DataTableTh align="right" className="w-32">Exposure</DataTableTh>
                  <DataTableTh className="w-32">Due</DataTableTh>
                  <DataTableTh className="w-36">Drill</DataTableTh>
                  <DataTableTh className="w-10" />
                </tr>
              </DataTableHead>
              <DataTableBody>
                {d.cases.map(c => {
                  const dd = daysFromNow(c.due_date);
                  return (
                    <DataTableRow
                      key={c.id}
                      onClick={() => nav(`/app/cases/${c.id}`)}
                      testId={`mycase-${c.id}`}
                    >
                      <DataTableTd>
                        <div className="max-w-lg truncate text-sm font-medium text-zinc-900 dark:text-zinc-50">{c.title}</div>
                        <div className="crt-num text-[10px] text-zinc-600 dark:text-zinc-400">{c.control_code} · {c.entity} · {c.process}</div>
                      </DataTableTd>
                      <DataTableTd><PriorityTag priority={c.priority} /></DataTableTd>
                      <DataTableTd><SeverityBadge severity={c.severity} /></DataTableTd>
                      <DataTableTd><StatusBadge status={c.status} /></DataTableTd>
                      <DataTableTd className="crt-num max-w-[9rem] text-[10px] leading-tight text-zinc-600 dark:text-zinc-400">
                        {c.department_id || c.cost_center_id ? (
                          <>
                            {c.department_id ? <div className="truncate" title={c.department_id}>dept · {String(c.department_id).slice(0, 10)}…</div> : null}
                            {c.cost_center_id ? <div className="truncate" title={c.cost_center_id}>cc · {String(c.cost_center_id).slice(0, 10)}…</div> : null}
                          </>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </DataTableTd>
                      <DataTableTd align="right" className="crt-num tabular-nums text-foreground">{fmtUSD(c.financial_exposure)}</DataTableTd>
                      <DataTableTd>
                        <div className="crt-num text-xs text-zinc-900 dark:text-zinc-50">{fmtDate(c.due_date)}</div>
                        <div
                          className={`crt-num text-[10px] ${
                            dd < 0
                              ? "text-[hsl(var(--destructive))]"
                              : dd < 3
                                ? "text-[hsl(var(--chart-3))]"
                                : "text-muted-foreground"
                          }`}
                        >
                          {dd < 0 ? `${Math.abs(dd)}d overdue` : `${dd}d remaining`}
                        </div>
                      </DataTableTd>
                      <DataTableTd onClick={(ev) => ev.stopPropagation()}>
                        <div className="crt-num flex flex-col gap-1 text-[9px] uppercase tracking-wider">
                          {c.exception_id ? (
                            <Link to={`/app/evidence/${encodeURIComponent(c.exception_id)}`} className="text-primary hover:underline">
                              Evidence
                            </Link>
                          ) : null}
                          {c.control_code ? (
                            <Link to={`/app/drill/control/${encodeURIComponent(c.control_code)}`} className="text-primary hover:underline">
                              Control
                            </Link>
                          ) : null}
                        </div>
                      </DataTableTd>
                      <DataTableTd><ArrowRight size={14} className="text-muted-foreground" /></DataTableTd>
                    </DataTableRow>
                  );
                })}
              </DataTableBody>
            </DataTable>
          </SectionCard>
        )}
      </div>
    </PageShell>
  );
}
