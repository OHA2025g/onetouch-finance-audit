import React from "react";
import { Link, NavLink, Outlet, useParams } from "react-router-dom";
import { ArrowLeft } from "@phosphor-icons/react";
import { PageShell, PageHeader } from "../components/PageShell";

function navCls({ isActive }) {
  return `px-3 h-9 font-mono text-[10px] uppercase tracking-wider border inline-flex items-center ${
    isActive ? "bg-white text-black border-white" : "border-[#262626] text-[#A3A3A3] hover:text-white"
  }`;
}

export default function WorkingPapersLayout() {
  const { engagementId } = useParams();
  const eid = decodeURIComponent(engagementId || "");
  const base = `/app/audit-planning/engagements/${encodeURIComponent(eid)}/working-papers`;

  return (
    <PageShell maxWidth="max-w-[1800px]">
      <Link
        to={`/app/audit-planning/engagements/${encodeURIComponent(eid)}?tab=wp`}
        className="inline-flex items-center gap-2 text-xs font-mono uppercase text-[#737373] hover:text-white mb-3"
      >
        <ArrowLeft size={14} /> Engagement hub
      </Link>
      <PageHeader
        kicker="CA WORKING PAPERS"
        title="Digital working papers"
        subtitle={`Engagement ${eid} · folders, sampling, vouching, and sign-off`}
      />
      <nav className="flex flex-wrap gap-2 mb-6">
        <NavLink to={base} end className={navCls}>
          Repository
        </NavLink>
        <NavLink to={`${base}/sampling`} className={navCls}>
          Sampling engine
        </NavLink>
        <NavLink to={`${base}/vouching`} className={navCls}>
          Vouching workbench
        </NavLink>
      </nav>
      <Outlet />
    </PageShell>
  );
}
