import React from "react";
import { Link, NavLink, Outlet, useParams } from "react-router-dom";
import { ArrowLeft } from "@phosphor-icons/react";
import { PageShell, PageHeader } from "../../components/PageShell";

function navCls({ isActive }) {
  return `px-2.5 h-8 font-mono text-[9px] uppercase tracking-wider border inline-flex items-center whitespace-nowrap ${
    isActive ? "bg-white text-black border-white" : "border-[#262626] text-[#A3A3A3] hover:text-white"
  }`;
}

export default function IndiaComplianceLayout() {
  const { engagementId } = useParams();
  const eid = decodeURIComponent(engagementId || "");
  const base = `/app/audit-planning/engagements/${encodeURIComponent(eid)}/india-compliance`;

  return (
    <PageShell maxWidth="max-w-[1800px]">
      <Link
        to={`/app/audit-planning/engagements/${encodeURIComponent(eid)}?tab=compliance`}
        className="inline-flex items-center gap-2 text-xs font-mono uppercase text-[#737373] hover:text-white mb-3"
      >
        <ArrowLeft size={14} /> Engagement hub
      </Link>
      <PageHeader
        kicker="INDIA REGULATORY"
        title="Statutory compliance engine"
        subtitle={`Engagement ${eid} · Companies Act, GST, TDS, Tax Audit 44AB, CARO, filings`}
      />
      <nav className="flex flex-wrap gap-1.5 mb-6">
        <NavLink to={base} end className={navCls}>
          Dashboard
        </NavLink>
        <NavLink to={`${base}/companies-act`} className={navCls}>
          Companies Act
        </NavLink>
        <NavLink to={`${base}/gst`} className={navCls}>
          GST audit
        </NavLink>
        <NavLink to={`${base}/tds`} className={navCls}>
          TDS/TCS
        </NavLink>
        <NavLink to={`${base}/tax-44ab`} className={navCls}>
          Tax 44AB
        </NavLink>
        <NavLink to={`${base}/caro`} className={navCls}>
          CARO
        </NavLink>
        <NavLink to={`${base}/calendar`} className={navCls}>
          Calendar
        </NavLink>
      </nav>
      <Outlet />
    </PageShell>
  );
}
