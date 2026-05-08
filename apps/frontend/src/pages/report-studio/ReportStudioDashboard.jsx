import React, { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { http } from "../../lib/api";
import { toast } from "sonner";
import { SectionCard } from "../../components/PageShell";

export default function ReportStudioDashboard() {
  const { engagementId } = useParams();
  const eid = decodeURIComponent(engagementId || "");
  const base = `/app/audit-planning/engagements/${encodeURIComponent(eid)}/report-studio`;
  const [busy, setBusy] = useState(false);

  const run = async (fn, msg) => {
    setBusy(true);
    try {
      await fn();
      toast.success(msg);
    } catch {
      toast.error("Action failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <SectionCard kicker="PIPELINE" title="Generate draft artefacts" bodyClassName="p-4 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() =>
            run(() => http.post(`/audit-engagements/${encodeURIComponent(eid)}/opinion/generate`), "Opinion generated")
          }
          className="px-4 h-10 bg-white text-black font-mono text-xs uppercase disabled:opacity-50"
        >
          Generate opinion
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => run(() => http.post(`/audit-engagements/${encodeURIComponent(eid)}/caro/generate`), "CARO annexure")}
          className="px-4 h-10 border border-white text-white font-mono text-xs uppercase disabled:opacity-50"
        >
          Generate CARO
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => run(() => http.post(`/audit-engagements/${encodeURIComponent(eid)}/report/generate`), "Report draft")}
          className="px-4 h-10 border border-[#262626] text-[#A3A3A3] font-mono text-xs uppercase hover:text-white disabled:opacity-50"
        >
          Generate final report
        </button>
      </SectionCard>
      <SectionCard kicker="SCREENS" title="Continue in workspace" bodyClassName="p-4 flex flex-wrap gap-2">
        <Link to={`${base}/observations`} className="px-4 h-9 border border-[#262626] text-sm text-white inline-flex items-center">
          Observation builder
        </Link>
        <Link to={`${base}/opinion`} className="px-4 h-9 border border-[#262626] text-sm text-white inline-flex items-center">
          Opinion recommendation
        </Link>
        <Link to={`${base}/caro`} className="px-4 h-9 border border-[#262626] text-sm text-white inline-flex items-center">
          CARO checklist / annexure
        </Link>
        <Link to={`${base}/preview`} className="px-4 h-9 border border-[#262626] text-sm text-white inline-flex items-center">
          Final report preview &amp; export
        </Link>
      </SectionCard>
    </div>
  );
}
