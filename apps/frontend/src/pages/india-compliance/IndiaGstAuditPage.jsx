import React, { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { http } from "../../lib/api";
import { toast } from "sonner";
import { SectionCard } from "../../components/PageShell";

const empty = {
  gstr1_sales: "",
  gstr3b_sales: "",
  gstr2b_purchases: "",
  purchase_register: "",
  itc_claimed: "",
  itc_eligible: "",
  gstr3b_output_tax_liability: "",
  books_output_tax_liability: "",
};

export default function IndiaGstAuditPage() {
  const { engagementId } = useParams();
  const eid = decodeURIComponent(engagementId || "");
  const [form, setForm] = useState(empty);
  const [history, setHistory] = useState([]);

  const load = useCallback(async () => {
    const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/gst/reconciliation`);
    setHistory(data.items || []);
  }, [eid]);

  useEffect(() => {
    load().catch(() => {});
  }, [load]);

  const submit = async (e) => {
    e.preventDefault();
    const n = (v) => (v === "" ? 0 : parseFloat(v));
    try {
      await http.post(`/audit-engagements/${encodeURIComponent(eid)}/gst/reconciliation`, {
        gstr1_sales: n(form.gstr1_sales),
        gstr3b_sales: n(form.gstr3b_sales),
        gstr2b_purchases: n(form.gstr2b_purchases),
        purchase_register: n(form.purchase_register),
        itc_claimed: n(form.itc_claimed),
        itc_eligible: n(form.itc_eligible),
        gstr3b_output_tax_liability: form.gstr3b_output_tax_liability === "" ? null : n(form.gstr3b_output_tax_liability),
        books_output_tax_liability: form.books_output_tax_liability === "" ? null : n(form.books_output_tax_liability),
      });
      setForm(empty);
      await load();
      toast.success("GST reconciliation saved");
    } catch {
      toast.error("Save failed");
    }
  };

  return (
    <div className="space-y-6">
      <SectionCard kicker="GST" title="Reconciliation engine" bodyClassName="p-4 space-y-3">
        <p className="text-sm text-[#A3A3A3]">
          Checks: GSTR-1 vs GSTR-3B sales, GSTR-2B vs purchase register, ITC mismatch, optional output tax liability mismatch (3B vs books).
        </p>
        <form onSubmit={submit} className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {[
            ["gstr1_sales", "GSTR-1 sales"],
            ["gstr3b_sales", "GSTR-3B sales"],
            ["gstr2b_purchases", "GSTR-2B purchases"],
            ["purchase_register", "Purchase register"],
            ["itc_claimed", "ITC claimed"],
            ["itc_eligible", "ITC eligible"],
            ["gstr3b_output_tax_liability", "Output tax (3B) — optional"],
            ["books_output_tax_liability", "Output tax (books) — optional"],
          ].map(([k, label]) => (
            <div key={k}>
              <label className="block font-mono text-[9px] uppercase text-[#737373] mb-1">{label}</label>
              <input
                type="number"
                step="any"
                value={form[k]}
                onChange={(ev) => setForm((f) => ({ ...f, [k]: ev.target.value }))}
                className="w-full bg-black border border-[#262626] px-2 py-2 text-sm text-white"
              />
            </div>
          ))}
          <div className="col-span-full">
            <button type="submit" className="px-4 h-10 bg-white text-black font-mono text-xs uppercase">
              Run &amp; store reconciliation
            </button>
          </div>
        </form>
      </SectionCard>
      <SectionCard kicker="HISTORY" title="Recent GST runs" bodyClassName="p-4 space-y-3 font-mono text-[11px]">
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
