import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { Plus, CalendarBlank, UsersThree, GridFour } from "@phosphor-icons/react";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { AuditStatusBadge, RiskBadge } from "../components/ca/AuditCaBadges";
import { StatCard } from "../components/StatCard";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";

export default function AuditEngagementList() {
  const nav = useNavigate();
  const dashboardParams = useDashboardFilterParams();
  const [rows, setRows] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  /** Statutory / internal / all other audit_type values (GST, tax, IFC, special audit, …). */
  const [auditKindFilter, setAuditKindFilter] = useState("statutory");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [listRes, metRes] = await Promise.all([
        http.get("/audit-engagements", { params: dashboardParams }),
        http.get("/audit-engagements/planning-metrics", { params: dashboardParams }),
      ]);
      setRows(listRes.data || []);
      setMetrics(metRes.data || null);
    } catch {
      toast.error("Failed to load audit planning");
    } finally {
      setLoading(false);
    }
  }, [dashboardParams]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      await load();
      if (cancelled) return;
    })();
    return () => { cancelled = true; };
  }, [load]);

  const filteredRows = useMemo(() => {
    return rows.filter((e) => {
      const t = String(e.audit_type || "").trim().toLowerCase();
      if (auditKindFilter === "statutory") return t === "statutory";
      if (auditKindFilter === "internal") return t === "internal";
      return t !== "statutory" && t !== "internal";
    });
  }, [rows, auditKindFilter]);

  if (loading) {
    return <div className="p-8 font-mono text-xs text-[#737373] uppercase tracking-wider">Loading audit planning…</div>;
  }

  return (
    <PageShell maxWidth="max-w-[1700px]">
      <PageHeader
        kicker="AUDIT ENGAGEMENT & PLANNING"
        title="Audit Planning"
        subtitle="Create, edit, and track engagements — the parent object for materiality, RACM, FS, schedules, IFC, working papers, compliance, and reporting."
        right={
          <div className="flex flex-wrap gap-2">
            <Link
              to="/app/audit-planning/calendar"
              className="inline-flex h-10 items-center gap-2 border border-zinc-300 px-3 text-xs font-mono uppercase tracking-wider text-zinc-600 transition-colors hover:border-zinc-400 hover:bg-zinc-50 hover:text-foreground dark:border-zinc-600 dark:text-zinc-300 dark:hover:border-zinc-500 dark:hover:bg-zinc-900"
            >
              <CalendarBlank size={16} /> Calendar
            </Link>
            <Link
              to="/app/audit-planning/new"
              className="inline-flex items-center gap-2 px-3 h-10 bg-white text-black text-xs font-mono uppercase tracking-wider hover:opacity-90"
            >
              <Plus size={16} weight="bold" /> New engagement
            </Link>
          </div>
        }
      />

      {metrics ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3 mb-6" data-testid="planning-metric-cards">
          <StatCard
            label="Active audits"
            value={metrics.active_audit_count}
            subtle="Draft, planned, or in progress"
            testId="metric-active-audits"
          />
          <StatCard
            label="Upcoming milestones"
            value={metrics.upcoming_milestone_count}
            subtle="Next 14 days · pending"
            severity="warning"
            testId="metric-upcoming-milestones"
          />
          <StatCard
            label="Overdue engagements"
            value={metrics.overdue_engagement_count}
            subtle="Past end date · not completed"
            severity={metrics.overdue_engagement_count ? "critical" : undefined}
            testId="metric-overdue"
          />
          <StatCard
            label="High-risk engagements"
            value={metrics.high_risk_engagement_count}
            subtle="Risk high or critical"
            severity={metrics.high_risk_engagement_count ? "warning" : undefined}
            testId="metric-high-risk"
          />
        </div>
      ) : null}

      {(metrics?.upcoming_milestones?.length > 0 || metrics?.overdue_engagements?.length > 0) ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
          {metrics?.upcoming_milestones?.length ? (
            <SectionCard kicker="NEXT 14 DAYS" title="Upcoming milestones" bodyClassName="p-4">
              <ul className="space-y-2 text-sm">
                {metrics.upcoming_milestones.map((m) => (
                  <li key={`${m.engagement_id}-${m.milestone_id}`} className="flex flex-col gap-1 border-b border-zinc-200 pb-2 sm:flex-row sm:items-center sm:justify-between dark:border-zinc-800">
                    <div>
                      <span className="text-foreground">{m.title}</span>
                      <div className="font-mono text-[10px] text-muted-foreground">{m.entity_name}</div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="font-mono text-[10px] text-muted-foreground">{m.due_date?.slice(0, 10)}</span>
                      <Link to={`/app/audit-planning/engagements/${encodeURIComponent(m.engagement_id)}`} className="text-[10px] font-mono uppercase text-[#0A84FF] hover:underline">Open</Link>
                    </div>
                  </li>
                ))}
              </ul>
            </SectionCard>
          ) : null}
          {metrics?.overdue_engagements?.length ? (
            <SectionCard kicker="ATTENTION" title="Overdue engagements" bodyClassName="p-4">
              <ul className="space-y-2 text-sm">
                {metrics.overdue_engagements.map((e) => (
                  <li key={e.engagement_id} className="flex flex-col gap-1 border-b border-zinc-200 pb-2 sm:flex-row sm:items-center sm:justify-between dark:border-zinc-800">
                    <div>
                      <span className="text-foreground">{e.entity_name}</span>
                      <div className="font-mono text-[10px] text-muted-foreground">{e.engagement_id}</div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <AuditStatusBadge status={e.status} />
                      <Link to={`/app/audit-planning/engagements/${encodeURIComponent(e.engagement_id)}`} className="text-[10px] font-mono uppercase text-[#0A84FF] hover:underline">Open</Link>
                    </div>
                  </li>
                ))}
              </ul>
            </SectionCard>
          ) : null}
        </div>
      ) : null}

      {metrics?.high_risk_engagements?.length ? (
        <SectionCard kicker="RISK" title="High-risk engagements" bodyClassName="p-4 mb-6">
          <div className="flex flex-wrap gap-2">
            {metrics.high_risk_engagements.map((e) => (
              <Link
                key={e.engagement_id}
                to={`/app/audit-planning/engagements/${encodeURIComponent(e.engagement_id)}`}
                className="inline-flex items-center gap-2 rounded-md border border-orange-200 bg-orange-50 px-3 py-2 text-xs text-orange-950 transition-colors hover:border-orange-300 hover:bg-orange-100 dark:border-orange-900/50 dark:bg-orange-950/40 dark:text-orange-100 dark:hover:border-orange-800"
              >
                <span className="text-foreground dark:text-orange-50">{e.entity_name}</span>
                <RiskBadge level={e.risk_level} />
              </Link>
            ))}
          </div>
        </SectionCard>
      ) : null}

      <div
        className="mb-4 rounded-sm border border-zinc-200 bg-zinc-50/90 px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900/50"
        data-testid="audit-engagement-type-filter"
      >
        <div className="crt-overline mb-2 text-muted-foreground">Statutory audit scope</div>
        <fieldset className="flex flex-wrap gap-6 border-0 p-0 m-0">
          <legend className="sr-only">Filter engagements by audit type</legend>
          {[
            { value: "statutory", label: "Statutory audit" },
            { value: "internal", label: "Internal audit" },
            { value: "others", label: "Others" },
          ].map(({ value, label }) => (
            <label
              key={value}
              className="flex cursor-pointer items-center gap-2 font-mono text-xs uppercase tracking-wider text-foreground"
            >
              <input
                type="radio"
                name="audit-engagement-kind"
                value={value}
                checked={auditKindFilter === value}
                onChange={() => setAuditKindFilter(value)}
                className="h-3.5 w-3.5 accent-primary"
                data-testid={`audit-kind-${value}`}
              />
              <span>{label}</span>
            </label>
          ))}
        </fieldset>
        <p className="mt-2 font-mono text-[10px] leading-snug text-muted-foreground">
          Others includes GST, tax, IFC, special audit, and any non-statutory / non-internal type.
        </p>
      </div>

      <SectionCard
        kicker="ENGAGEMENTS"
        title="All engagements"
        right={
          <Link to="/app/audit-planning/calendar" className="hidden sm:inline-flex items-center gap-1 text-[10px] font-mono uppercase text-[#0A84FF] hover:underline">
            <CalendarBlank size={12} /> Calendar view
          </Link>
        }
        bodyClassName="p-0"
      >
        <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[70vh]">
          <DataTableHead>
            <tr>
              <DataTableTh>ID</DataTableTh>
              <DataTableTh>Entity</DataTableTh>
              <DataTableTh>FY</DataTableTh>
              <DataTableTh>Type</DataTableTh>
              <DataTableTh>Status</DataTableTh>
              <DataTableTh>Risk</DataTableTh>
              <DataTableTh className="w-[120px] text-right">Modules</DataTableTh>
              <DataTableTh className="w-[88px] text-right">RACM</DataTableTh>
              <DataTableTh className="w-[88px] text-right">Team</DataTableTh>
            </tr>
          </DataTableHead>
          <DataTableBody>
            {filteredRows.map((e) => (
              <DataTableRow key={e.id} onClick={() => nav(`/app/audit-planning/engagements/${encodeURIComponent(e.engagement_id)}`)} className="cursor-pointer">
                <DataTableTd className="font-mono text-xs text-foreground">{e.engagement_id}</DataTableTd>
                <DataTableTd>{e.entity_name}</DataTableTd>
                <DataTableTd className="font-mono text-xs">{e.financial_year}</DataTableTd>
                <DataTableTd className="font-mono text-xs uppercase">{e.audit_type}</DataTableTd>
                <DataTableTd><AuditStatusBadge status={e.status} /></DataTableTd>
                <DataTableTd><RiskBadge level={e.risk_level} /></DataTableTd>
                <DataTableTd className="text-right font-mono text-[9px] uppercase" onClick={(ev) => ev.stopPropagation()}>
                  <div className="flex flex-wrap justify-end gap-1">
                    <Link
                      to={`/app/audit-planning/engagements/${encodeURIComponent(e.engagement_id)}/fs-audit`}
                      className="text-[#0A84FF] hover:underline px-1"
                    >FS</Link>
                    <Link
                      to={`/app/audit-planning/engagements/${encodeURIComponent(e.engagement_id)}/working-papers`}
                      className="text-[#0A84FF] hover:underline px-1"
                    >WP</Link>
                    <Link
                      to={`/app/audit-planning/engagements/${encodeURIComponent(e.engagement_id)}/india-compliance`}
                      className="text-[#0A84FF] hover:underline px-1"
                    >IN</Link>
                  </div>
                </DataTableTd>
                <DataTableTd className="text-right" onClick={(ev) => ev.stopPropagation()}>
                  <Link
                    to={`/app/audit-planning/engagements/${encodeURIComponent(e.engagement_id)}/racm`}
                    className="inline-flex h-8 items-center justify-center gap-1 border border-zinc-300 px-2 text-[10px] font-mono uppercase text-primary transition-colors hover:border-primary/50 hover:bg-zinc-50 dark:border-zinc-600 dark:hover:bg-zinc-900"
                    title="RACM builder"
                  >
                    <GridFour size={14} />
                  </Link>
                </DataTableTd>
                <DataTableTd className="text-right" onClick={(ev) => ev.stopPropagation()}>
                  <Link
                    to={`/app/audit-planning/engagements/${encodeURIComponent(e.engagement_id)}/team`}
                    className="inline-flex h-8 items-center justify-center gap-1 border border-zinc-300 px-2 text-[10px] font-mono uppercase text-muted-foreground transition-colors hover:border-zinc-400 hover:bg-zinc-50 hover:text-foreground dark:border-zinc-600 dark:hover:bg-zinc-900"
                    title="Team assignment"
                  >
                    <UsersThree size={14} />
                  </Link>
                </DataTableTd>
              </DataTableRow>
            ))}
          </DataTableBody>
        </DataTable>
        {!rows.length ? (
          <div className="p-8 font-mono text-xs text-[#737373]">No engagements yet. After first backend boot, seed creates demo engagements, or create one above.</div>
        ) : !filteredRows.length ? (
          <div className="p-8 font-mono text-xs text-[#737373]">
            No engagements match this filter (
            {auditKindFilter === "statutory"
              ? "statutory audit"
              : auditKindFilter === "internal"
                ? "internal audit"
                : "others"}
            ). Try another audit type above.
          </div>
        ) : null}
      </SectionCard>
    </PageShell>
  );
}
