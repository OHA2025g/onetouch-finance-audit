import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { CheckCircle, XCircle, Clock } from "@phosphor-icons/react";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";

export default function ApprovalsQueue() {
  const [items, setItems] = useState([]);
  const [status, setStatus] = useState("pending");

  const load = async () => {
    const { data } = await http.get("/governance/approvals", { params: { status } });
    setItems(data);
  };

  useEffect(() => { load(); }, [status]); // eslint-disable-line

  const decide = async (id, decision) => {
    try {
      if (decision === "approve") await http.post(`/governance/approvals/${id}/approve`, { note: "Approved in UI" });
      else await http.post(`/governance/approvals/${id}/reject`, { note: "Rejected in UI" });
      toast.success(`Request ${decision}d`);
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Decision failed");
    }
  };

  return (
    <PageShell maxWidth="max-w-[1400px]">
      <div data-testid="approvals-queue">
        <PageHeader
          kicker="GOVERNANCE"
          title="Approval queue"
          icon={<Clock size={18} />}
          subtitle="Review and approve sensitive operations (connectors, retention, legal holds, copilot indexing) with a clear audit trail."
        />

        <div className="flex gap-2 mt-6">
          {["pending", "approved", "rejected"].map((s) => (
            <button
              key={s}
              onClick={() => setStatus(s)}
              className={`px-4 h-10 text-xs font-mono uppercase rounded-full transition-colors ${
                status === s ? "bg-white text-black" : "bg-[#141414]/70 text-[#A3A3A3] hover:bg-[#1F1F1F]/70 border border-[#262626]"
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        <SectionCard className="mt-6" kicker="REQUESTS" title="Approval requests" bodyClassName="p-0">
          <div className="divide-y divide-[#262626]/60">
            {items.map((it) => (
              <div key={it.id} className="p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="text-white text-sm font-mono">{it.request_type}</div>
                    <div className="text-[#737373] text-xs font-mono">
                      {it.subject_type} · {it.subject_id}
                      {it.subject_type === "exception" && it.subject_id ? (
                        <Link to={`/app/evidence/${encodeURIComponent(it.subject_id)}`} className="ml-2 text-[#0A84FF] hover:underline">Evidence</Link>
                      ) : null}
                      {it.subject_type === "case" && it.subject_id ? (
                        <Link to={`/app/cases/${encodeURIComponent(it.subject_id)}`} className="ml-2 text-[#0A84FF] hover:underline">Case</Link>
                      ) : null}
                    </div>
                    <div className="text-[#A3A3A3] text-xs mt-2">{it.reason || "—"}</div>
                  </div>
                  {status === "pending" && (
                    <div className="flex gap-2">
                      <button
                        onClick={() => decide(it.id, "approve")}
                        className="flex items-center gap-2 px-4 h-10 rounded-full border border-[#30D158] text-[#30D158] text-xs font-mono uppercase hover:bg-[#30D158]/10 transition-colors"
                      >
                        <CheckCircle size={14} /> Approve
                      </button>
                      <button
                        onClick={() => decide(it.id, "reject")}
                        className="flex items-center gap-2 px-4 h-10 rounded-full border border-[#FF3B30] text-[#FF3B30] text-xs font-mono uppercase hover:bg-[#FF3B30]/10 transition-colors"
                      >
                        <XCircle size={14} /> Reject
                      </button>
                    </div>
                  )}
                </div>
                <pre className="mt-3 text-[10px] text-[#A3A3A3] overflow-x-auto bg-[#0A0A0A]/55 backdrop-blur border border-[#262626] rounded-xl p-3">
                  {JSON.stringify(it.proposed_change || {}, null, 2)}
                </pre>
              </div>
            ))}
            {!items.length && <div className="p-5 text-xs font-mono text-[#737373]">No requests.</div>}
          </div>
        </SectionCard>
      </div>
    </PageShell>
  );
}

