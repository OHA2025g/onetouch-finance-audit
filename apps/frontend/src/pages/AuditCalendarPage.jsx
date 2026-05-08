import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { ArrowLeft } from "@phosphor-icons/react";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MilestoneTimeline from "../components/ca/MilestoneTimeline";

export default function AuditCalendarPage() {
  const [engagements, setEngagements] = useState([]);
  useEffect(() => {
    http.get("/audit-engagements").then((r) => setEngagements(r.data || [])).catch(() => toast.error("Failed to load"));
  }, []);

  return (
    <PageShell maxWidth="max-w-[1700px]">
      <Link to="/app/audit-planning" className="inline-flex items-center gap-2 text-xs font-mono uppercase text-[#737373] hover:text-white mb-3">
        <ArrowLeft size={14} /> Audit planning
      </Link>
      <PageHeader
        kicker="PLANNING"
        title="Audit calendar"
        subtitle="Milestones across engagements. Open an engagement hub for full planning, team assignment, and execution modules."
      />
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 md:gap-6">
        {engagements.map((e) => (
          <SectionCard key={e.id} kicker={e.engagement_id} title={e.entity_name} bodyClassName="p-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 font-mono text-[10px] text-[#737373] mb-3">
              <span>{e.start_date?.slice(0, 10)} → {e.end_date?.slice(0, 10)}</span>
              <Link className="text-[#0A84FF] hover:underline shrink-0" to={`/app/audit-planning/engagements/${encodeURIComponent(e.engagement_id)}`}>Open engagement hub</Link>
            </div>
            <MilestoneTimeline milestones={e.milestones} />
          </SectionCard>
        ))}
        {!engagements.length ? <div className="col-span-full font-mono text-xs text-[#737373]">No engagements.</div> : null}
      </div>
    </PageShell>
  );
}
