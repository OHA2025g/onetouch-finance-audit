import React, { useEffect, useMemo, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { buildDashboardFilterParams } from "../lib/mastersDashboardParams";
import { StatCard } from "../components/StatCard";
import { Link } from "react-router-dom";

export default function FinanceTeamPerformancePage() {
  const { entityCode, periodYm, periodExplicit, departmentId, costCenterId } = useMastersFilters();
  const [d, setD] = useState(null);

  const params = useMemo(
    () =>
      buildDashboardFilterParams({
        entityCode,
        periodYm,
        periodExplicit,
        departmentId,
        costCenterId,
      }),
    [entityCode, periodYm, periodExplicit, departmentId, costCenterId],
  );

  useEffect(() => {
    http
      .get("/finance-team/summary", { params })
      .then((r) => setD(r.data))
      .catch(() => toast.error("Failed to load finance team dashboard"));
  }, [params]);

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="finance-team-loading">
        Loading finance team view…
      </div>
    );
  }

  const ck = d.cockpit_kpis || {};
  const ctrl = (d.controller || {}).kpis || {};

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="finance-team-page">
        <PageHeader
          kicker="FINANCE OPERATIONS"
          title="Finance team performance"
          subtitle="Close cycles, controller signals, CFO cockpit KPIs, and action queue depth (Phase 7 BFF)."
        />
        <MastersFilterStrip className="mb-6" />

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <StatCard label="Close cycles" value={d.cycles?.count ?? 0} testId="ft-cycles" />
          <StatCard label="Open close tasks" value={d.close_tasks_open} testId="ft-tasks" />
          <StatCard label="Action queue (total)" value={d.action_queue_total} testId="ft-aq" />
          <StatCard label="Audit readiness %" value={ck.audit_readiness_pct} testId="ft-readiness" />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-8">
          <StatCard label="Close blockers (exceptions)" value={ctrl.close_blockers} severity="warning" />
          <StatCard label="AP exceptions" value={ctrl.ap_exception_count} />
          <StatCard label="Reconciliations overdue" value={ctrl.reconciliations_overdue} severity="critical" />
        </div>

        <SectionCard kicker="DRILL" title="Next steps">
          <ul className="text-sm space-y-2 text-muted-foreground">
            <li>
              <Link className="text-primary hover:underline" to={d.drill_paths?.close || "/app/finance-operations/month-end-close"}>
                Month-end close
              </Link>
            </li>
            <li>
              <Link className="text-primary hover:underline" to={d.drill_paths?.cases || "/app/cases"}>
                Open cases
              </Link>
            </li>
            <li>
              <Link className="text-primary hover:underline" to={d.drill_paths?.exceptions || "/app/audit"}>
                Controls & exceptions
              </Link>
            </li>
          </ul>
        </SectionCard>
      </div>
    </PageShell>
  );
}
