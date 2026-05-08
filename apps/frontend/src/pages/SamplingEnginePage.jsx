import React, { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { SectionCard } from "../components/PageShell";

const METHODS = [
  "random",
  "monetary unit sampling",
  "judgmental",
  "high-value selection",
  "exception-based selection",
];

export default function SamplingEnginePage() {
  const { engagementId } = useParams();
  const eid = decodeURIComponent(engagementId || "");
  const [plans, setPlans] = useState([]);
  const [papers, setPapers] = useState([]);
  const [selectedPlanId, setSelectedPlanId] = useState(null);
  const [samples, setSamples] = useState([]);
  const [method, setMethod] = useState("random");
  const [popSize, setPopSize] = useState(500);
  const [sampleSize, setSampleSize] = useState(25);
  const [seed, setSeed] = useState(42);
  const [wpLink, setWpLink] = useState("");

  const loadPlans = useCallback(async () => {
    const [{ data: p }, { data: wb }] = await Promise.all([
      http.get(`/audit-engagements/${encodeURIComponent(eid)}/sampling-plans`),
      http.get(`/audit-engagements/${encodeURIComponent(eid)}/wp-workbench`),
    ]);
    setPlans(p.items || []);
    setPapers(wb.working_papers || []);
  }, [eid]);

  useEffect(() => {
    if (!eid) return;
    loadPlans().catch(() => toast.error("Failed to load sampling"));
  }, [eid, loadPlans]);

  useEffect(() => {
    if (!selectedPlanId) {
      setSamples([]);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const { data } = await http.get(`/sampling-plans/${encodeURIComponent(selectedPlanId)}/samples`);
        if (!cancelled) setSamples(data.items || []);
      } catch {
        if (!cancelled) setSamples([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedPlanId]);

  const createPlan = async (e) => {
    e.preventDefault();
    try {
      const body = {
        engagement_id: eid,
        method,
        population_size: Number(popSize) || 0,
        sample_size: Number(sampleSize) || 0,
        seed: seed === "" ? null : Number(seed),
        working_paper_id: wpLink || null,
      };
      await http.post("/sampling-plans", body);
      await loadPlans();
      toast.success("Sampling plan created");
    } catch {
      toast.error("Create plan failed");
    }
  };

  const generate = async () => {
    if (!selectedPlanId) {
      toast.error("Select a plan");
      return;
    }
    try {
      const { data } = await http.post(`/sampling-plans/${encodeURIComponent(selectedPlanId)}/generate`);
      setSamples(data.samples || []);
      await loadPlans();
      toast.success(`Generated ${(data.samples || []).length} selections`);
    } catch {
      toast.error("Generate failed");
    }
  };

  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
      <SectionCard kicker="PLAN" title="New sampling plan" bodyClassName="p-4 space-y-3">
        <form onSubmit={createPlan} className="space-y-3">
          <div>
            <label className="block font-mono text-[10px] uppercase text-[#737373] mb-1">Method</label>
            <select value={method} onChange={(ev) => setMethod(ev.target.value)} className="w-full bg-black border border-[#262626] px-3 py-2 text-sm text-white">
              {METHODS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block font-mono text-[10px] uppercase text-[#737373] mb-1">Population size</label>
              <input
                type="number"
                value={popSize}
                onChange={(ev) => setPopSize(ev.target.value)}
                className="w-full bg-black border border-[#262626] px-3 py-2 text-sm text-white"
              />
            </div>
            <div>
              <label className="block font-mono text-[10px] uppercase text-[#737373] mb-1">Sample size</label>
              <input
                type="number"
                value={sampleSize}
                onChange={(ev) => setSampleSize(ev.target.value)}
                className="w-full bg-black border border-[#262626] px-3 py-2 text-sm text-white"
              />
            </div>
          </div>
          <div>
            <label className="block font-mono text-[10px] uppercase text-[#737373] mb-1">Seed (optional)</label>
            <input
              type="number"
              value={seed}
              onChange={(ev) => setSeed(ev.target.value)}
              className="w-full bg-black border border-[#262626] px-3 py-2 text-sm text-white"
            />
          </div>
          <div>
            <label className="block font-mono text-[10px] uppercase text-[#737373] mb-1">Link to working paper (optional)</label>
            <select value={wpLink} onChange={(ev) => setWpLink(ev.target.value)} className="w-full bg-black border border-[#262626] px-3 py-2 text-sm text-white">
              <option value="">—</option>
              {papers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.reference} — {p.title}
                </option>
              ))}
            </select>
          </div>
          <button type="submit" className="px-4 h-10 bg-white text-black font-mono text-xs uppercase">
            Save plan
          </button>
        </form>
      </SectionCard>

      <SectionCard kicker="RUN" title="Plans &amp; generated sample" bodyClassName="p-4 space-y-4">
        <div>
          <label className="block font-mono text-[10px] uppercase text-[#737373] mb-1">Active plan</label>
          <select
            value={selectedPlanId || ""}
            onChange={(ev) => setSelectedPlanId(ev.target.value || null)}
            className="w-full bg-black border border-[#262626] px-3 py-2 text-sm text-white"
          >
            <option value="">— select —</option>
            {plans.map((pl) => (
              <option key={pl.id} value={pl.id}>
                {pl.method} · n={pl.sample_size} / N={pl.population_size}
                {pl.generated_at ? " · generated" : ""}
              </option>
            ))}
          </select>
        </div>
        <button type="button" onClick={generate} className="px-4 h-10 border border-white text-white font-mono text-xs uppercase">
          Generate / refresh sample
        </button>
        <div className="max-h-[420px] overflow-y-auto border border-[#262626] rounded-none">
          <table className="w-full text-left text-xs font-mono">
            <thead className="sticky top-0 bg-[#0a0a0a] text-[#737373] uppercase">
              <tr>
                <th className="p-2">#</th>
                <th className="p-2">Ref</th>
                <th className="p-2">Amount</th>
                <th className="p-2">Reason</th>
              </tr>
            </thead>
            <tbody>
              {samples.map((s) => (
                <tr key={s.id} className="border-t border-[#262626] text-[#A3A3A3]">
                  <td className="p-2 text-white">{s.idx}</td>
                  <td className="p-2">{s.transaction_ref || "—"}</td>
                  <td className="p-2">{s.amount != null ? String(s.amount) : "—"}</td>
                  <td className="p-2 max-w-[200px] truncate" title={s.selection_reason}>
                    {s.selection_reason || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {samples.length === 0 ? <div className="p-4 text-sm text-[#737373]">No rows yet — pick a plan and generate.</div> : null}
        </div>
      </SectionCard>
    </div>
  );
}
