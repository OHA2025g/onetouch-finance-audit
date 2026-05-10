import React, { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { drillTargetFromTxnId, useWorkbenchRowDrill } from "../lib/workbenchDrillNav";
import { SectionCard } from "../components/PageShell";

const TICKS = [
  "agreed to invoice",
  "agreed to bank",
  "recalculated",
  "verified",
  "exception noted",
  "pending clarification",
];

export default function VouchingWorkbenchPage() {
  const { engagementId } = useParams();
  const dashboardParams = useDashboardFilterParams();
  const { drillToTarget } = useWorkbenchRowDrill();
  const eid = decodeURIComponent(engagementId || "");
  const [bundle, setBundle] = useState({ working_papers: [], vouching_items: [] });
  const [wpId, setWpId] = useState("");
  const [txRef, setTxRef] = useState("");
  const [amount, setAmount] = useState("");
  const [tick, setTick] = useState("pending clarification");
  const [evidenceRef, setEvidenceRef] = useState("");
  const [conclusion, setConclusion] = useState("");
  const [notes, setNotes] = useState("");

  const load = useCallback(async () => {
    const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/wp-workbench`, { params: dashboardParams });
    setBundle(data);
    setWpId((prev) => prev || data.working_papers?.[0]?.id || "");
  }, [eid, dashboardParams]);

  useEffect(() => {
    if (!eid) return;
    load().catch(() => toast.error("Failed to load workbench"));
  }, [eid, load]);

  const papers = bundle.working_papers || [];
  const items = bundle.vouching_items || [];

  const createItem = async (e) => {
    e.preventDefault();
    if (!wpId || !txRef.trim()) {
      toast.error("Working paper and transaction reference required");
      return;
    }
    try {
      await http.post(
        "/vouching-items",
        {
          engagement_id: eid,
          working_paper_id: wpId,
          transaction_ref: txRef.trim(),
          amount: amount === "" ? null : Number(amount),
          tick_mark: tick,
          evidence_reference: evidenceRef.trim() || null,
          conclusion: conclusion.trim() || null,
          notes: notes.trim() || null,
        },
        { params: dashboardParams },
      );
      setTxRef("");
      setAmount("");
      setEvidenceRef("");
      setConclusion("");
      setNotes("");
      await load();
      toast.success("Vouching line added");
    } catch {
      toast.error("Create failed");
    }
  };

  const patchItem = async (id, patch) => {
    try {
      await http.put(`/vouching-items/${encodeURIComponent(id)}`, patch, { params: dashboardParams });
      await load();
    } catch {
      toast.error("Update failed");
    }
  };

  return (
    <div className="space-y-6">
      <SectionCard kicker="NEW LINE" title="Vouching — transaction, evidence, tick, conclusion" bodyClassName="p-4">
        {papers.length === 0 ? (
          <p className="text-sm text-[#737373]">Create at least one working paper in the Repository tab before adding vouching lines.</p>
        ) : null}
        <form onSubmit={createItem} className={`grid grid-cols-1 md:grid-cols-2 gap-3 ${papers.length === 0 ? "opacity-50 pointer-events-none" : ""}`}>
          <div className="md:col-span-2">
            <label className="block font-mono text-[10px] uppercase text-[#737373] mb-1">Working paper</label>
            <select value={wpId} onChange={(ev) => setWpId(ev.target.value)} className="w-full bg-black border border-[#262626] px-3 py-2 text-sm text-white">
              {papers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.reference} — {p.title}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block font-mono text-[10px] uppercase text-[#737373] mb-1">Transaction</label>
            <input
              value={txRef}
              onChange={(ev) => setTxRef(ev.target.value)}
              placeholder="JE-1024 / INV-8832"
              className="w-full bg-black border border-[#262626] px-3 py-2 text-sm text-white font-mono"
            />
          </div>
          <div>
            <label className="block font-mono text-[10px] uppercase text-[#737373] mb-1">Amount (optional)</label>
            <input
              type="number"
              value={amount}
              onChange={(ev) => setAmount(ev.target.value)}
              className="w-full bg-black border border-[#262626] px-3 py-2 text-sm text-white"
            />
          </div>
          <div>
            <label className="block font-mono text-[10px] uppercase text-[#737373] mb-1">Tick mark</label>
            <select value={tick} onChange={(ev) => setTick(ev.target.value)} className="w-full bg-black border border-[#262626] px-3 py-2 text-sm text-white">
              {TICKS.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block font-mono text-[10px] uppercase text-[#737373] mb-1">Evidence reference</label>
            <input
              value={evidenceRef}
              onChange={(ev) => setEvidenceRef(ev.target.value)}
              placeholder="Scan ref / exhibit B-12"
              className="w-full bg-black border border-[#262626] px-3 py-2 text-sm text-white"
            />
          </div>
          <div className="md:col-span-2">
            <label className="block font-mono text-[10px] uppercase text-[#737373] mb-1">Conclusion</label>
            <input
              value={conclusion}
              onChange={(ev) => setConclusion(ev.target.value)}
              placeholder="Agreed, no exception"
              className="w-full bg-black border border-[#262626] px-3 py-2 text-sm text-white"
            />
          </div>
          <div className="md:col-span-2">
            <label className="block font-mono text-[10px] uppercase text-[#737373] mb-1">Notes</label>
            <textarea
              value={notes}
              onChange={(ev) => setNotes(ev.target.value)}
              rows={2}
              className="w-full bg-black border border-[#262626] px-3 py-2 text-sm text-white"
            />
          </div>
          <div className="md:col-span-2">
            <button type="submit" className="px-4 h-10 bg-white text-black font-mono text-xs uppercase">
              Add vouching line
            </button>
          </div>
        </form>
      </SectionCard>

      <SectionCard kicker="REGISTER" title="Vouching lines" bodyClassName="p-0 overflow-x-auto">
        <table className="w-full text-left text-xs min-w-[720px]">
          <thead className="font-mono uppercase text-[#737373] border-b border-[#262626]">
            <tr>
              <th className="p-3">Transaction</th>
              <th className="p-3">Evidence</th>
              <th className="p-3">Tick</th>
              <th className="p-3">Conclusion</th>
              <th className="p-3 w-40">Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((v) => (
              <tr
                key={v.id}
                className="border-b border-[#262626] text-[#A3A3A3] align-top cursor-pointer hover:bg-[#141414]"
                onClick={(e) => {
                  if (e.target.closest("input,select,textarea,button")) return;
                  drillToTarget(drillTargetFromTxnId(v.transaction_ref));
                }}
              >
                <td className="p-3 font-mono text-white">{v.transaction_ref}</td>
                <td className="p-3">
                  <input
                    defaultValue={v.evidence_reference || ""}
                    onBlur={(ev) => {
                      const val = ev.target.value.trim();
                      if (val !== (v.evidence_reference || "")) patchItem(v.id, { evidence_reference: val || null });
                    }}
                    className="w-full bg-black border border-[#262626] px-2 py-1 text-[11px] text-white"
                  />
                </td>
                <td className="p-3">
                  <select
                    defaultValue={v.tick_mark}
                    onChange={(ev) => patchItem(v.id, { tick_mark: ev.target.value })}
                    className="w-full max-w-[180px] bg-black border border-[#262626] px-2 py-1 text-[11px] text-white"
                  >
                    {TICKS.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="p-3">
                  <textarea
                    defaultValue={v.conclusion || ""}
                    onBlur={(ev) => {
                      const val = ev.target.value.trim();
                      if (val !== (v.conclusion || "")) patchItem(v.id, { conclusion: val || null });
                    }}
                    rows={2}
                    className="w-full bg-black border border-[#262626] px-2 py-1 text-[11px] text-white"
                  />
                </td>
                <td className="p-3 text-[10px] font-mono text-[#737373]">{v.working_paper_id?.slice(0, 8)}…</td>
              </tr>
            ))}
          </tbody>
        </table>
        {items.length === 0 ? <div className="p-6 text-sm text-[#737373]">No vouching lines yet.</div> : null}
      </SectionCard>
    </div>
  );
}
