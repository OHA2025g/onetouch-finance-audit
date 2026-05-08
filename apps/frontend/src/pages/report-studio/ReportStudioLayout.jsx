import React from "react";
import { Link, NavLink, Outlet, useParams } from "react-router-dom";
import { ArrowLeft } from "@phosphor-icons/react";
import { PageShell, PageHeader } from "../../components/PageShell";

function navCls({ isActive }) {
  return `px-2.5 h-8 font-mono text-[9px] uppercase tracking-wider border inline-flex items-center whitespace-nowrap ${
    isActive ? "bg-white text-black border-white" : "border-[#262626] text-[#A3A3A3] hover:text-white"
  }`;
}

export default function ReportStudioLayout() {
  const { engagementId } = useParams();
  const eid = decodeURIComponent(engagementId || "");
  const base = `/app/audit-planning/engagements/${encodeURIComponent(eid)}/report-studio`;

  return (
    <PageShell maxWidth="max-w-[1800px]">
      <Link
        to={`/app/audit-planning/engagements/${encodeURIComponent(eid)}?tab=reporting`}
        className="inline-flex items-center gap-2 text-xs font-mono uppercase text-[#737373] hover:text-white mb-3"
      >
        <ArrowLeft size={14} /> Engagement hub
      </Link>
      <PageHeader
        kicker="AUDIT REPORTING"
        title="Report &amp; opinion engine"
        subtitle={`Engagement ${eid} · observations, opinion, CARO annexure, final report draft &amp; exports`}
      />
      <nav className="flex flex-wrap gap-1.5 mb-6">
        <NavLink to={base} end className={navCls}>
          Builder
        </NavLink>
        <NavLink to={`${base}/observations`} className={navCls}>
          Observations
        </NavLink>
        <NavLink to={`${base}/opinion`} className={navCls}>
          Opinion
        </NavLink>
        <NavLink to={`${base}/caro`} className={navCls}>
          CARO
        </NavLink>
        <NavLink to={`${base}/preview`} className={navCls}>
          Final preview
        </NavLink>
      </nav>
      <Outlet />
    </PageShell>
  );
}
