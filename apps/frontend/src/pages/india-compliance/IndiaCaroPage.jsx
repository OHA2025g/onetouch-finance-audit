import React, { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { http } from "../../lib/api";
import { toast } from "sonner";
import { useDashboardFilterParams } from "../../lib/useDashboardFilterParams";
import { SectionCard } from "../../components/PageShell";

const STATUSES = ["compliant", "non-compliant", "pending evidence", "not applicable"];

export default function IndiaCaroPage() {
  const { engagementId } = useParams();
  const dashboardParams = useDashboardFilterParams();
  const eid = decodeURIComponent(engagementId || "");
  const [clauses, setClauses] = useState([]);
  const [clauseInput, setClauseInput] = useState("3(i),3(ii),3(iii),3(vii)(a)");

  const load = useCallback(async () => {
    const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/caro/state`, { params: dashboardParams });
    setClauses(data.caro_clauses || []);
  }, [eid, dashboardParams]);

  useEffect(() => {
    load().catch(() => {});
  }, [load]);

  const init = async () => {
    const ids = clauseInput.split(/[\s,]+/).filter(Boolean);
    try {
      await http.post(`/audit-engagements/${encodeURIComponent(eid)}/caro/checklist`, { clause_ids: ids }, { params: dashboardParams });
      await load();
      toast.success("CARO checklist ready");
    } catch {
      toast.error("Init failed");
    }
  };

  const gen = async () => {
    try {
      await http.post(`/audit-engagements/${encodeURIComponent(eid)}/caro/generate`, {}, { params: dashboardParams });
      toast.success("CARO narrative generated (demo)");
    } catch {
      toast.error("Generate failed");
    }
  };

  const updateClause = async (clauseId, status) => {
    try {
      await http.post(`/audit-engagements/${encodeURIComponent(eid)}/caro/clause`, { clause_id: clauseId, status }, { params: dashboardParams });
      await load();
    } catch {
      toast.error("Update failed");
    }
  };

  return (
    <div className="space-y-6">
      <SectionCard kicker="CARO 2020" title="Reporting checklist" bodyClassName="p-4 space-y-4">
        <div className="flex flex-wrap gap-2 items-end">
          <div>
            <label className="block font-mono text-[9px] uppercase text-[#737373] mb-1">Clause ids</label>
            <input value={clauseInput} onChange={(e) => setClauseInput(e.target.value)} className="bg-black border border-[#262626] px-3 py-2 text-sm text-white font-mono w-72" />
          </div>
          <button type="button" onClick={init} className="h-10 px-4 bg-white text-black font-mono text-xs uppercase">
            Build checklist
          </button>
          <button type="button" onClick={gen} className="h-10 px-4 border border-white text-white font-mono text-xs uppercase">
            Generate annexure (demo)
          </button>
        </div>
        <ul className="space-y-2">
          {clauses.map((c) => (
            <li key={c.id} className="border border-[#262626] p-3 flex flex-wrap items-center gap-3 justify-between">
              <span className="font-mono text-white">{c.id}</span>
              <select
                value={c.status}
                onChange={(e) => updateClause(c.id, e.target.value)}
                className="bg-black border border-[#262626] text-xs text-white px-2 py-1 font-mono"
              >
                {STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </li>
          ))}
        </ul>
        {clauses.length === 0 ? <p className="text-sm text-[#737373]">No CARO clauses — build checklist.</p> : null}
      </SectionCard>
    </div>
  );
}
