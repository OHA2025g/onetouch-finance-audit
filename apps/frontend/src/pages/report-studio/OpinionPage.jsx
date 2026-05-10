import React, { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { http } from "../../lib/api";
import { toast } from "sonner";
import { useDashboardFilterParams } from "../../lib/useDashboardFilterParams";
import { SectionCard } from "../../components/PageShell";

export default function OpinionPage() {
  const { engagementId } = useParams();
  const dashboardParams = useDashboardFilterParams();
  const eid = decodeURIComponent(engagementId || "");
  const [op, setOp] = useState(null);

  const load = useCallback(async () => {
    const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/opinion`, { params: dashboardParams });
    setOp(data);
  }, [eid, dashboardParams]);

  useEffect(() => {
    load().catch(() => setOp(null));
  }, [load]);

  const gen = async () => {
    try {
      const { data } = await http.post(`/audit-engagements/${encodeURIComponent(eid)}/opinion/generate`, {}, { params: dashboardParams });
      setOp(data);
      toast.success("Opinion regenerated");
    } catch {
      toast.error("Generate failed");
    }
  };

  return (
    <div className="space-y-6">
      <SectionCard kicker="ENGINE" title="Opinion recommendation" bodyClassName="p-4 space-y-4">
        <button type="button" onClick={gen} className="px-4 h-10 bg-white text-black font-mono text-xs uppercase">
          Regenerate from observations + engagement signals
        </button>
        {!op ? (
          <p className="text-sm text-[#737373]">No opinion stored yet.</p>
        ) : (
          <div className="space-y-3 text-sm">
            <div>
              <div className="font-mono text-[10px] uppercase text-[#737373]">Display</div>
              <div className="text-xl text-white">{op.opinion_display || op.suggested_opinion}</div>
            </div>
            <div>
              <div className="font-mono text-[10px] uppercase text-[#737373]">Classification</div>
              <div className="font-mono text-[#0A84FF]">{op.suggested_opinion}</div>
            </div>
            <div>
              <div className="font-mono text-[10px] uppercase text-[#737373]">Rationale</div>
              <div className="text-[#A3A3A3]">{op.rationale}</div>
            </div>
            {op.signals_summary ? (
              <div>
                <div className="font-mono text-[10px] uppercase text-[#737373] mb-1">Signals</div>
                <pre className="text-xs text-white bg-black border border-[#262626] p-3 overflow-x-auto">{JSON.stringify(op.signals_summary, null, 2)}</pre>
              </div>
            ) : null}
            {op.counts ? (
              <div>
                <div className="font-mono text-[10px] uppercase text-[#737373] mb-1">Counts</div>
                <pre className="text-xs text-white bg-black border border-[#262626] p-3 overflow-x-auto">{JSON.stringify(op.counts, null, 2)}</pre>
              </div>
            ) : null}
          </div>
        )}
      </SectionCard>
    </div>
  );
}
