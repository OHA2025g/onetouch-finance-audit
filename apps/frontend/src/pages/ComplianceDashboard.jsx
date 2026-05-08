import React, { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { http } from "../lib/api";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { buildDashboardFilterParams } from "../lib/mastersDashboardParams";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { StatCard } from "../components/StatCard";
import { SeverityBadge } from "../components/Badges";
import { fmtDate } from "../lib/format";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, CartesianGrid, Tooltip } from "recharts";
import InsightPanel from "../components/InsightPanel";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { RC_STROKE, RC_TICK, rcTooltipStyle } from "../lib/rechartsTheme";
import { exceptionSourceDrillPath } from "../lib/drillPaths";

export default function ComplianceDashboard() {
  const [d, setD] = useState(null);
  const nav = useNavigate();
  const { entityCode, periodYm, periodExplicit, departmentId, costCenterId, hrefWithMasterParams } = useMastersFilters();
  useEffect(() => {
    const params = buildDashboardFilterParams({
      entityCode,
      periodYm,
      periodExplicit,
      departmentId,
      costCenterId,
    });
    http.get("/dashboard/compliance", { params }).then((r) => setD(r.data));
  }, [entityCode, periodYm, periodExplicit, departmentId, costCenterId]);
  if (!d) return <div className="crt-overline text-muted-foreground p-8">Loading compliance…</div>;
  const k = d.kpis;

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="compliance-dashboard">
        <PageHeader
          kicker="COMPLIANCE & RISK"
          title="Access & policy"
          subtitle="Monitor SoD conflicts, access violations, and policy breach risk with evidence-first traceability."
          right={
            <Link
              to={hrefWithMasterParams("/app/risk-intelligence")}
              className="hidden items-center gap-2 rounded-sm border border-zinc-300 bg-white px-3 py-2 text-xs font-medium uppercase tracking-wider text-zinc-600 shadow-none transition-colors hover:bg-zinc-50 sm:inline-flex dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
              data-testid="compliance-risk-intelligence-link"
            >
              Risk intelligence
            </Link>
          }
        />

        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <StatCard label="SoD conflicts" value={k.sod_conflicts} severity="critical" testId="kpi-sod" />
          <StatCard label="Terminated user activity" value={k.terminated_user_activity} severity="critical" testId="kpi-term" />
          <StatCard label="Tax mismatch open" value={k.tax_mismatch_open} severity="warning" testId="kpi-tax" />
          <StatCard label="Total open breaches" value={k.policy_breach_total} testId="kpi-breach" />
        </div>

        <InsightPanel section="compliance" title="Compliance AI Insights" />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-8">
          <SectionCard className="lg:col-span-2" kicker="ACCESS" title="SoD conflicts">
          <div className="space-y-2">
            {d.sod_conflicts.length === 0 && (
              <div className="crt-num text-xs text-muted-foreground">No SoD conflicts.</div>
            )}
            {d.sod_conflicts.map(e => {
              const srcPath = exceptionSourceDrillPath(e);
              const linkChip =
                "crt-num rounded-sm border border-zinc-300 bg-white px-2 py-1 text-[9px] uppercase tracking-wider text-primary transition-colors hover:bg-zinc-50 dark:border-zinc-600 dark:bg-zinc-950 dark:hover:bg-zinc-900";
              return (
                <div
                  key={e.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => nav(`/app/evidence/${e.id}`)}
                  onKeyDown={(ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); nav(`/app/evidence/${e.id}`); } }}
                  className="w-full cursor-pointer rounded-sm border border-zinc-200 bg-zinc-50/80 p-4 text-left transition-colors hover:bg-zinc-100/90 dark:border-zinc-800 dark:bg-zinc-900/40 dark:hover:bg-zinc-900/70"
                  data-testid={`sod-${e.id}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium text-zinc-900 dark:text-zinc-50">{e.title}</div>
                      <div className="crt-num mt-0.5 text-[10px] text-zinc-600 dark:text-zinc-400">{e.entity} · {fmtDate(e.detected_at)}</div>
                    </div>
                    <SeverityBadge severity={e.severity} />
                  </div>
                  <div className="mt-2 text-xs leading-relaxed text-zinc-700 dark:text-zinc-300">{e.summary}</div>
                  <div className="crt-num mt-3 flex flex-wrap gap-2 text-[9px] uppercase tracking-wider" onClick={(ev) => ev.stopPropagation()}>
                    {e.control_code ? (
                      <Link to={`/app/drill/control/${encodeURIComponent(e.control_code)}`} className={linkChip}>Control</Link>
                    ) : null}
                    {srcPath ? (
                      <Link to={srcPath} className={linkChip}>Source</Link>
                    ) : null}
                    <Link to={`/app/drill/user/${encodeURIComponent(e.source_record_id || "")}`} className={linkChip}>User</Link>
                  </div>
                </div>
              );
            })}
          </div>
          </SectionCard>

          <SectionCard kicker="AGEING" title="Exception aging">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={d.exception_aging}>
              <CartesianGrid stroke={RC_STROKE} vertical={false} />
              <XAxis dataKey="bucket" stroke={RC_STROKE} tick={RC_TICK} />
              <YAxis stroke={RC_STROKE} tick={RC_TICK} />
              <Tooltip contentStyle={rcTooltipStyle()} />
              <Bar dataKey="count" fill="hsl(var(--chart-3))" />
            </BarChart>
          </ResponsiveContainer>
          </SectionCard>
        </div>

        <SectionCard kicker="ACTIVITY" title={`Terminated / dormant user activity (${d.access_violations.length})`} bodyClassName="p-0">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[55vh]" testId="compliance-access-violations-table">
            <DataTableHead>
              <tr>
                <DataTableTh>User</DataTableTh>
                <DataTableTh>Entity</DataTableTh>
                <DataTableTh>Event</DataTableTh>
                <DataTableTh>Severity</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {d.access_violations.slice(0, 12).map(e => (
                <DataTableRow
                  key={e.id}
                  onClick={() => nav(`/app/evidence/${e.id}`)}
                  testId={`access-${e.id}`}
                  className="cursor-pointer"
                >
                  <DataTableTd className="crt-num text-xs" onClick={(ev) => ev.stopPropagation()}>
                    <Link to={`/app/drill/user/${encodeURIComponent(e.source_record_id || "")}`} className="font-medium text-primary hover:underline">
                      {e.source_record_id || e.summary.split(" ").slice(2, 4).join(" ")}
                    </Link>
                  </DataTableTd>
                  <DataTableTd className="crt-num text-xs text-zinc-800 dark:text-zinc-200">{e.entity}</DataTableTd>
                  <DataTableTd className="text-xs text-zinc-800 dark:text-zinc-200">{e.title}</DataTableTd>
                  <DataTableTd><SeverityBadge severity={e.severity} /></DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>
      </div>
    </PageShell>
  );
}
