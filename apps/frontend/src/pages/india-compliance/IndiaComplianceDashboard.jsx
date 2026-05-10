import React, { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { http, API } from "../../lib/api";
import { toast } from "sonner";
import { useDashboardFilterParams } from "../../lib/useDashboardFilterParams";
import { SectionCard } from "../../components/PageShell";
import { PenaltyRiskBadge } from "../../components/Badges";

export default function IndiaComplianceDashboard() {
  const { engagementId } = useParams();
  const dashboardParams = useDashboardFilterParams();
  const eid = decodeURIComponent(engagementId || "");
  const base = `/app/audit-planning/engagements/${encodeURIComponent(eid)}/india-compliance`;
  const [status, setStatus] = useState(null);
  const [library, setLibrary] = useState(null);
  const [findings, setFindings] = useState([]);
  const [findingForm, setFindingForm] = useState({ law_code: "CA2013", title: "", notes: "" });

  const load = useCallback(async () => {
    const qp = { params: dashboardParams };
    const [eng, st, fin] = await Promise.all([
      http.get(`/audit-engagements/${encodeURIComponent(eid)}`, qp),
      http.get(`/audit-engagements/${encodeURIComponent(eid)}/compliance/status`, qp),
      http.get(`/audit-engagements/${encodeURIComponent(eid)}/compliance/findings`, qp),
    ]);
    const entityCode = eng.data?.entity_code;
    const lib = await http.get("/compliance/library", {
      params: { ...dashboardParams, ...(entityCode ? { entity_code: entityCode } : {}) },
    });
    setStatus(st.data);
    setLibrary(lib.data);
    setFindings(fin.data?.items || []);
  }, [eid, dashboardParams]);

  useEffect(() => {
    load().catch(() => toast.error("Failed to load compliance"));
  }, [load]);

  const buildChecklist = async () => {
    try {
      await http.post(`/audit-engagements/${encodeURIComponent(eid)}/compliance/checklist`, { law_codes: [] }, { params: dashboardParams });
      await load();
      toast.success("Full India checklist built");
    } catch {
      toast.error("Checklist build failed");
    }
  };

  const exportCsv = () => {
    const token = localStorage.getItem("ota_token");
    const qs = new URLSearchParams(dashboardParams).toString();
    const url = `${API}/audit-engagements/${encodeURIComponent(eid)}/compliance/export${qs ? `?${qs}` : ""}`;
    fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then((r) => r.blob())
      .then((blob) => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `compliance-${eid}.csv`;
        a.click();
        URL.revokeObjectURL(a.href);
      })
      .catch(() => toast.error("Export failed"));
  };

  const addFinding = async (e) => {
    e.preventDefault();
    if (!findingForm.title.trim()) {
      toast.error("Title required");
      return;
    }
    try {
      await http.post(
        `/audit-engagements/${encodeURIComponent(eid)}/compliance/findings`,
        {
          law_code: findingForm.law_code,
          title: findingForm.title.trim(),
          notes: findingForm.notes.trim() || null,
          severity: "medium",
        },
        { params: dashboardParams },
      );
      setFindingForm((f) => ({ ...f, title: "", notes: "" }));
      await load();
      toast.success("Finding logged");
    } catch {
      toast.error("Could not add finding");
    }
  };

  const s = status?.summary || {};
  const laws = library?.laws || [];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="border border-[#262626] p-4">
          <div className="font-mono text-[10px] uppercase text-[#737373]">Total lines</div>
          <div className="text-2xl text-white mt-1">{s.total ?? 0}</div>
        </div>
        <div className="border border-[#262626] p-4">
          <div className="font-mono text-[10px] uppercase text-[#737373]">Compliant</div>
          <div className="text-2xl text-green-400 mt-1">{s.compliant ?? 0}</div>
        </div>
        <div className="border border-[#262626] p-4">
          <div className="font-mono text-[10px] uppercase text-[#737373]">Non-compliant</div>
          <div className="text-2xl text-red-400 mt-1">{s.non_compliant ?? 0}</div>
        </div>
        <div className="border border-[#262626] p-4">
          <div className="font-mono text-[10px] uppercase text-[#737373]">Findings</div>
          <div className="text-2xl text-white mt-1">{status?.findings_count ?? findings.length}</div>
        </div>
      </div>

      <SectionCard kicker="ACTIONS" title="Checklist &amp; export" bodyClassName="p-4 flex flex-wrap gap-2">
        <button type="button" onClick={buildChecklist} className="px-4 h-10 bg-white text-black font-mono text-xs uppercase">
          Build / refresh checklist
        </button>
        <button type="button" onClick={exportCsv} className="px-4 h-10 border border-white text-white font-mono text-xs uppercase">
          Export CSV
        </button>
        <Link to={`${base}/companies-act`} className="px-4 h-10 border border-[#262626] text-[#A3A3A3] font-mono text-xs uppercase inline-flex items-center hover:text-white">
          Companies Act
        </Link>
        <Link to={`${base}/gst`} className="px-4 h-10 border border-[#262626] text-[#A3A3A3] font-mono text-xs uppercase inline-flex items-center hover:text-white">
          GST
        </Link>
        <Link to={`${base}/tds`} className="px-4 h-10 border border-[#262626] text-[#A3A3A3] font-mono text-xs uppercase inline-flex items-center hover:text-white">
          TDS
        </Link>
      </SectionCard>

      <SectionCard kicker="LIBRARY" title="India laws in engine" bodyClassName="p-4">
        <ul className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
          {laws.map((law) => (
            <li key={law.code} className="border border-[#262626] p-3">
              <div className="text-white font-medium">{law.name}</div>
              <div className="font-mono text-[10px] text-[#737373] mt-1">{law.code}</div>
              <ul className="mt-2 space-y-1 text-[#A3A3A3] text-xs">
                {(law.sections || []).map((sec) => (
                  <li key={sec.code}>
                    <span className="text-[#0A84FF] font-mono">{sec.code}</span> — {sec.title}
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      </SectionCard>

      <SectionCard kicker="FINDINGS" title="Compliance findings register" bodyClassName="p-4 space-y-4">
        <form onSubmit={addFinding} className="grid grid-cols-1 md:grid-cols-4 gap-2">
          <select
            value={findingForm.law_code}
            onChange={(ev) => setFindingForm((f) => ({ ...f, law_code: ev.target.value }))}
            className="bg-black border border-[#262626] px-3 py-2 text-sm text-white"
          >
            {["CA2013", "IT1961", "GST", "TDS", "CARO", "44AB"].map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <input
            placeholder="Finding title"
            value={findingForm.title}
            onChange={(ev) => setFindingForm((f) => ({ ...f, title: ev.target.value }))}
            className="md:col-span-2 bg-black border border-[#262626] px-3 py-2 text-sm text-white"
          />
          <button type="submit" className="h-10 bg-white text-black font-mono text-xs uppercase">
            Log finding
          </button>
          <textarea
            placeholder="Notes"
            value={findingForm.notes}
            onChange={(ev) => setFindingForm((f) => ({ ...f, notes: ev.target.value }))}
            className="md:col-span-4 bg-black border border-[#262626] px-3 py-2 text-sm text-white"
            rows={2}
          />
        </form>
        <ul className="space-y-2 text-sm max-h-48 overflow-y-auto">
          {findings.map((f) => (
            <li key={f.id} className="border border-[#262626] p-2 flex justify-between gap-2">
              <div>
                <span className="font-mono text-[10px] text-[#0A84FF]">{f.law_code}</span>
                <div className="text-white">{f.title}</div>
                {f.notes ? <div className="text-xs text-[#737373] mt-1">{f.notes}</div> : null}
              </div>
              <PenaltyRiskBadge risk={f.severity || "medium"} />
            </li>
          ))}
        </ul>
      </SectionCard>
    </div>
  );
}
