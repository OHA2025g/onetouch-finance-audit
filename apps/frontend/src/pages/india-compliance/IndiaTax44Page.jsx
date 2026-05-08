import React, { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { http } from "../../lib/api";
import { toast } from "sonner";
import { SectionCard } from "../../components/PageShell";

const STATUSES = ["compliant", "non-compliant", "pending evidence", "not applicable"];

export default function IndiaTax44Page() {
  const { engagementId } = useParams();
  const eid = decodeURIComponent(engagementId || "");
  const [clauses, setClauses] = useState([]);
  const [clauseInput, setClauseInput] = useState("10A,10B,34,43");

  const load = useCallback(async () => {
    const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/tax-audit-44ab/state`);
    setClauses(data.clauses || []);
  }, [eid]);

  useEffect(() => {
    load().catch(() => {});
  }, [load]);

  const init = async () => {
    const ids = clauseInput.split(/[\s,]+/).filter(Boolean);
    try {
      await http.post(`/audit-engagements/${encodeURIComponent(eid)}/tax-audit-44ab/checklist`, { clause_ids: ids });
      await load();
      toast.success("44AB checklist ready");
    } catch {
      toast.error("Init failed");
    }
  };

  const updateClause = async (clauseId, status) => {
    try {
      await http.post(`/audit-engagements/${encodeURIComponent(eid)}/tax-audit-44ab/clause`, {
        clause_id: clauseId,
        status,
      });
      await load();
    } catch {
      toast.error("Update failed");
    }
  };

  return (
    <SectionCard kicker="TAX AUDIT" title="Form 3CD / u/s 44AB" bodyClassName="p-4 space-y-4">
      <div className="flex flex-wrap gap-2 items-end">
        <div>
          <label className="block font-mono text-[9px] uppercase text-[#737373] mb-1">Clause ids (comma)</label>
          <input value={clauseInput} onChange={(e) => setClauseInput(e.target.value)} className="bg-black border border-[#262626] px-3 py-2 text-sm text-white font-mono w-64" />
        </div>
        <button type="button" onClick={init} className="h-10 px-4 bg-white text-black font-mono text-xs uppercase">
          Build checklist
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
      {clauses.length === 0 ? <p className="text-sm text-[#737373]">No clauses — build checklist above.</p> : null}
    </SectionCard>
  );
}
