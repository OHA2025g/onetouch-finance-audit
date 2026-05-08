import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { ArrowLeft } from "@phosphor-icons/react";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import AuditTeamCard from "../components/ca/AuditTeamCard";

export default function AuditTeamPage() {
  const { engagementId } = useParams();
  const eid = decodeURIComponent(engagementId || "");
  const [eng, setEng] = useState(null);

  useEffect(() => {
    if (!eid) return;
    http.get(`/audit-engagements/${encodeURIComponent(eid)}`).then((r) => setEng(r.data)).catch(() => toast.error("Load failed"));
  }, [eid]);

  const addMember = async (ev) => {
    ev.preventDefault();
    const fd = new FormData(ev.target);
    try {
      await http.post(`/audit-engagements/${encodeURIComponent(eid)}/team`, {
        user_email: fd.get("email"),
        role: fd.get("role") || "staff",
        allocation_pct: parseFloat(fd.get("pct") || "100"),
      });
      const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}`);
      setEng(data);
      toast.success("Team member added");
      ev.target.reset();
    } catch {
      toast.error("Add failed");
    }
  };

  if (!eng) return <div className="p-8 font-mono text-xs text-[#737373]">Loading…</div>;

  return (
    <PageShell maxWidth="max-w-[900px]">
      <Link to={`/app/audit-planning/engagements/${encodeURIComponent(eid)}`} className="inline-flex items-center gap-2 text-xs font-mono uppercase text-[#737373] hover:text-white mb-3">
        <ArrowLeft size={14} /> Engagement
      </Link>
      <PageHeader kicker="TEAM" title="Audit team assignment" subtitle={eng.engagement_id} />
      <SectionCard kicker="ROSTER" title="Members" bodyClassName="p-6">
        <AuditTeamCard members={eng.team_members} />
      </SectionCard>
      <SectionCard kicker="ADD" title="Assign member" bodyClassName="p-6 mt-4">
        <form className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end" onSubmit={addMember}>
          <label className="text-xs font-mono text-[#737373]">Email<input required name="email" type="email" className="mt-1 w-full bg-[#141414] border border-[#262626] px-2 h-9 text-sm" /></label>
          <label className="text-xs font-mono text-[#737373]">Role<input name="role" className="mt-1 w-full bg-[#141414] border border-[#262626] px-2 h-9 text-sm" placeholder="senior" /></label>
          <label className="text-xs font-mono text-[#737373]">%<input name="pct" type="number" className="mt-1 w-full bg-[#141414] border border-[#262626] px-2 h-9 text-sm" defaultValue={100} /></label>
          <button type="submit" className="md:col-span-3 px-4 h-10 bg-white text-black font-mono text-xs uppercase">Add</button>
        </form>
      </SectionCard>
    </PageShell>
  );
}
