import React, { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { http } from "../../lib/api";
import { toast } from "sonner";
import { useDashboardFilterParams } from "../../lib/useDashboardFilterParams";
import { SectionCard } from "../../components/PageShell";

export default function IndiaTdsAuditPage() {
  const { engagementId } = useParams();
  const dashboardParams = useDashboardFilterParams();
  const eid = decodeURIComponent(engagementId || "");
  const [ledger, setLedger] = useState("");
  const [challan, setChallan] = useState("");
  const [days, setDays] = useState("0");
  const [expRate, setExpRate] = useState("");
  const [appRate, setAppRate] = useState("");
  const [history, setHistory] = useState([]);

  const load = useCallback(async () => {
    const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/tds/reconciliation`, { params: dashboardParams });
    setHistory(data.items || []);
  }, [eid, dashboardParams]);

  useEffect(() => {
    load().catch(() => {});
  }, [load]);

  const submit = async (e) => {
    e.preventDefault();
    const n = (v) => (v === "" ? 0 : parseFloat(v));
    try {
      await http.post(
        `/audit-engagements/${encodeURIComponent(eid)}/tds/reconciliation`,
        {
          ledger_tds: n(ledger),
          challan_tds: n(challan),
          delayed_payment_days: parseInt(days, 10) || 0,
          expected_deduction_rate_pct: expRate === "" ? null : n(expRate),
          applied_deduction_rate_pct: appRate === "" ? null : n(appRate),
        },
        { params: dashboardParams },
      );
      await load();
      toast.success("TDS reconciliation saved");
    } catch {
      toast.error("Save failed");
    }
  };

  return (
    <div className="space-y-6">
      <SectionCard kicker="TDS/TCS" title="Reconciliation" bodyClassName="p-4 space-y-3">
        <p className="text-sm text-[#A3A3A3]">
          Ledger vs challan, unpaid TDS, delayed deposit (days), and optional deduction rate mismatch (expected vs applied %).
        </p>
        <form onSubmit={submit} className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <div>
            <label className="block font-mono text-[9px] uppercase text-[#737373] mb-1">Ledger TDS</label>
            <input type="number" step="any" value={ledger} onChange={(e) => setLedger(e.target.value)} className="w-full bg-black border border-[#262626] px-2 py-2 text-sm text-white" />
          </div>
          <div>
            <label className="block font-mono text-[9px] uppercase text-[#737373] mb-1">Challan TDS</label>
            <input type="number" step="any" value={challan} onChange={(e) => setChallan(e.target.value)} className="w-full bg-black border border-[#262626] px-2 py-2 text-sm text-white" />
          </div>
          <div>
            <label className="block font-mono text-[9px] uppercase text-[#737373] mb-1">Delayed payment (days)</label>
            <input type="number" value={days} onChange={(e) => setDays(e.target.value)} className="w-full bg-black border border-[#262626] px-2 py-2 text-sm text-white" />
          </div>
          <div>
            <label className="block font-mono text-[9px] uppercase text-[#737373] mb-1">Expected rate %</label>
            <input type="number" step="any" value={expRate} onChange={(e) => setExpRate(e.target.value)} className="w-full bg-black border border-[#262626] px-2 py-2 text-sm text-white" />
          </div>
          <div>
            <label className="block font-mono text-[9px] uppercase text-[#737373] mb-1">Applied rate %</label>
            <input type="number" step="any" value={appRate} onChange={(e) => setAppRate(e.target.value)} className="w-full bg-black border border-[#262626] px-2 py-2 text-sm text-white" />
          </div>
          <div className="col-span-full">
            <button type="submit" className="px-4 h-10 bg-white text-black font-mono text-xs uppercase">
              Run &amp; store
            </button>
          </div>
        </form>
      </SectionCard>
      <SectionCard kicker="HISTORY" title="Recent TDS runs" bodyClassName="p-4 space-y-3 font-mono text-[11px]">
        {(history || []).slice(0, 8).map((h) => (
          <div key={h.id} className="border border-[#262626] p-3 text-[#A3A3A3]">
            <div className="text-[10px] text-[#737373]">{h.at}</div>
            <pre className="mt-2 text-white whitespace-pre-wrap break-all">{JSON.stringify(h.checks, null, 2)}</pre>
          </div>
        ))}
        {history.length === 0 ? <div className="text-[#737373]">No reconciliations yet.</div> : null}
      </SectionCard>
    </div>
  );
}
