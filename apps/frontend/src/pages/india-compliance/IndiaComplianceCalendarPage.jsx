import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { http } from "../../lib/api";
import { toast } from "sonner";
import { SectionCard } from "../../components/PageShell";
import { PenaltyRiskBadge } from "../../components/Badges";

export default function IndiaComplianceCalendarPage() {
  const { engagementId } = useParams();
  const eid = decodeURIComponent(engagementId || "");
  const [data, setData] = useState({ events: [], filings: [] });

  useEffect(() => {
    http
      .get(`/audit-engagements/${encodeURIComponent(eid)}/compliance-calendar`)
      .then((r) => setData(r.data))
      .catch(() => toast.error("Calendar load failed"));
  }, [eid]);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <SectionCard kicker="CADENCE" title="Milestone events" bodyClassName="p-4 space-y-3">
        {(data.events || []).map((ev, i) => (
          <div key={i} className="border border-[#262626] p-3 text-sm">
            <div className="text-white">{ev.title}</div>
            <div className="font-mono text-[10px] text-[#737373] mt-1">{ev.due}</div>
          </div>
        ))}
      </SectionCard>
      <SectionCard kicker="FILINGS" title="Filing due dates &amp; penalty risk" bodyClassName="p-4 space-y-3">
        {(data.filings || []).map((f) => (
          <div key={f.id} className="border border-[#262626] p-3 flex justify-between gap-2 items-start">
            <div>
              <div className="text-white text-sm">{f.title}</div>
              <div className="font-mono text-[10px] text-[#0A84FF] mt-1">
                {f.law_code} · {f.form_code}
              </div>
              <div className="font-mono text-[10px] text-[#737373] mt-1">Due {f.due_date}</div>
            </div>
            <PenaltyRiskBadge risk={f.penalty_risk} />
          </div>
        ))}
      </SectionCard>
    </div>
  );
}
