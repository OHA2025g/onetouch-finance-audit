import React, { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { http } from "../../lib/api";
import { toast } from "sonner";
import { useDashboardFilterParams } from "../../lib/useDashboardFilterParams";
import { SectionCard } from "../../components/PageShell";
import ComplianceReqTable from "./ComplianceReqTable";

export default function IndiaCompaniesActPage() {
  const { engagementId } = useParams();
  const dashboardParams = useDashboardFilterParams();
  const eid = decodeURIComponent(engagementId || "");
  const [requirements, setRequirements] = useState([]);

  const load = useCallback(async () => {
    const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/compliance/status`, { params: dashboardParams });
    setRequirements(data.requirements || []);
  }, [eid, dashboardParams]);

  useEffect(() => {
    load().catch(() => toast.error("Load failed"));
  }, [load]);

  const seedCa = async () => {
    try {
      await http.post(`/audit-engagements/${encodeURIComponent(eid)}/compliance/checklist`, { law_codes: ["CA2013"] }, { params: dashboardParams });
      await load();
      toast.success("Companies Act checklist loaded");
    } catch {
      toast.error("Could not build CA2013-only checklist");
    }
  };

  return (
    <SectionCard
      kicker="COMPANIES ACT 2013"
      title="Statutory checklist"
      right={
        <button type="button" onClick={seedCa} className="px-3 h-8 border border-[#262626] text-[10px] font-mono uppercase text-[#A3A3A3] hover:text-white" title="Replaces stored checklist with Companies Act rows only">
          Replace with CA-only checklist
        </button>
      }
      bodyClassName="p-0"
    >
      <div className="p-4 text-sm text-[#A3A3A3] border-b border-[#262626]">
        Lines scoped to <span className="text-white font-mono">CA2013</span>. Use status and evidence columns; export the full register from the dashboard.
      </div>
      <ComplianceReqTable engagementId={eid} requirements={requirements} lawCodes={["CA2013"]} onChanged={load} />
    </SectionCard>
  );
}
