import React from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "@phosphor-icons/react";
import { PageShell } from "../components/PageShell";
import RacmBuilderPanel from "../components/ca/RacmBuilderPanel";

export default function RacmBuilderPage() {
  const { engagementId } = useParams();
  const eid = decodeURIComponent(engagementId || "");

  return (
    <PageShell maxWidth="max-w-[1800px]">
      <Link to={`/app/audit-planning/engagements/${encodeURIComponent(eid)}`} className="inline-flex items-center gap-2 text-xs font-mono uppercase text-[#737373] hover:text-white mb-4">
        <ArrowLeft size={14} /> Engagement hub
      </Link>
      <RacmBuilderPanel engagementId={eid} compact={false} />
    </PageShell>
  );
}
