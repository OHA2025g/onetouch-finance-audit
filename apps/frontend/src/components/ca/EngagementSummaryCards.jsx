import React from "react";
import { Link } from "react-router-dom";
function Card({ label, value, sub, to }) {
  const inner = (
    <>
      <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-1 font-display text-2xl text-foreground">{value}</div>
      {sub ? <div className="mt-1 text-xs text-muted-foreground">{sub}</div> : null}
      {to ? <div className="mt-2 font-mono text-[9px] uppercase text-primary">Open →</div> : null}
    </>
  );
  const cls =
    "block h-full rounded-xl border border-zinc-200 bg-zinc-50/80 p-4 transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900/50 dark:hover:bg-zinc-900/80";
  if (to) {
    return (
      <Link to={to} className={cls} data-testid={`summary-card-${label}`}>
        {inner}
      </Link>
    );
  }
  return (
    <div className={cls} data-testid={`summary-card-${label}`}>
      {inner}
    </div>
  );
}

export default function EngagementSummaryCards({ summary, engagementId }) {
  if (!summary) return null;
  const hi = summary.high_risks?.length ?? 0;
  const e = engagementId ? encodeURIComponent(engagementId) : "";
  const racm = engagementId ? `/app/audit-planning/engagements/${e}?tab=racm` : null;
  const cases = engagementId ? `/app/cases?engagement_id=${e}` : null;
  const evidence = "/app/evidence";
  const controls = engagementId ? `/app/audit-planning/engagements/${e}?tab=racm` : null;
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3" data-testid="engagement-summary-cards">
      <Card label="Risks" value={summary.risk_count ?? 0} sub={hi ? `${hi} high / critical` : "RACM register"} to={racm || undefined} />
      <Card label="Open cases" value={summary.cases_open ?? 0} sub={`${summary.cases_total ?? 0} total`} to={cases || undefined} />
      <Card label="Exceptions" value={summary.exceptions_count ?? 0} sub="Linked to engagement" to={evidence} />
      <Card label="Controls mapped" value={(summary.linked_controls || []).length} sub="From risk register" to={controls || undefined} />
    </div>
  );
}
