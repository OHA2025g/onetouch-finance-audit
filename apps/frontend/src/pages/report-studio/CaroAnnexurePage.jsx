import React, { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { http } from "../../lib/api";
import { toast } from "sonner";
import { SectionCard } from "../../components/PageShell";

export default function CaroAnnexurePage() {
  const { engagementId } = useParams();
  const eid = decodeURIComponent(engagementId || "");
  const [state, setState] = useState(null);
  const [responses, setResponses] = useState(null);

  const load = useCallback(async () => {
    const [{ data: st }, { data: resp }] = await Promise.all([
      http.get(`/audit-engagements/${encodeURIComponent(eid)}/caro/state`),
      http.get(`/audit-engagements/${encodeURIComponent(eid)}/caro/responses`),
    ]);
    setState(st);
    setResponses(resp);
  }, [eid]);

  useEffect(() => {
    load().catch(() => {});
  }, [load]);

  const gen = async () => {
    try {
      await http.post(`/audit-engagements/${encodeURIComponent(eid)}/caro/generate`);
      await load();
      toast.success("CARO annexure refreshed");
    } catch {
      toast.error("Generate failed");
    }
  };

  const ic = `/app/audit-planning/engagements/${encodeURIComponent(eid)}/india-compliance/caro`;

  return (
    <div className="space-y-6">
      <SectionCard kicker="CARO" title="Annexure &amp; clause status" bodyClassName="p-4 space-y-4">
        <p className="text-sm text-[#A3A3A3]">
          Edit clause-level status in the India compliance module, then generate annexure text here.
        </p>
        <div className="flex flex-wrap gap-2">
          <Link to={ic} className="px-4 h-9 border border-[#0A84FF] text-[#0A84FF] text-xs font-mono uppercase inline-flex items-center">
            Open CARO checklist
          </Link>
          <button type="button" onClick={gen} className="px-4 h-9 bg-white text-black text-xs font-mono uppercase">
            Generate annexure
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <div className="font-mono text-[10px] uppercase text-[#737373] mb-2">Checklist state</div>
            <ul className="text-sm space-y-1 text-[#A3A3A3]">
              {(state?.caro_clauses || []).map((c) => (
                <li key={c.id}>
                  <span className="text-white font-mono">{c.id}</span> — {c.status}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <div className="font-mono text-[10px] uppercase text-[#737373] mb-2">Annexure responses</div>
            <ul className="text-sm space-y-2 text-[#A3A3A3]">
              {(responses?.responses || []).map((r) => (
                <li key={r.clause_id} className="border border-[#262626] p-2">
                  <div className="font-mono text-white text-xs">{r.clause_id}</div>
                  <div className="mt-1">{r.response}</div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </SectionCard>
    </div>
  );
}
