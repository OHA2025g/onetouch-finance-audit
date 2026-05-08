import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { http } from "../../lib/api";
import { toast } from "sonner";
import { FileXls, Lightning, Plus } from "@phosphor-icons/react";
import { PageHeader, SectionCard } from "../PageShell";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../DataTable";
import { RiskBadge } from "./AuditCaBadges";

const RISK_CATEGORIES = [
  "Financial Reporting Risk",
  "Fraud Risk",
  "Compliance Risk",
  "Operational Risk",
  "IT/ERP Risk",
  "Tax Risk",
];

function heatColor(score, max) {
  if (!max) return "rgba(38,38,38,0.5)";
  const t = Math.min(1, score / max);
  const r = Math.round(10 + t * 200);
  const g = Math.round(30 + (1 - t) * 80);
  const b = Math.round(40 + (1 - t) * 120);
  return `rgba(${r},${g},${b},0.85)`;
}

export default function RacmBuilderPanel({ engagementId, compact = false }) {
  const eid = engagementId;
  const [risks, setRisks] = useState([]);
  const [heatmap, setHeatmap] = useState(null);
  const [planPreview, setPlanPreview] = useState([]);
  const [controls, setControls] = useState([]);
  const [loading, setLoading] = useState(true);
  const [highOnly, setHighOnly] = useState(false);
  const [owner, setOwner] = useState("");
  const [processFilter, setProcessFilter] = useState("");
  const [fsFilter, setFsFilter] = useState("");
  const [newRiskOpen, setNewRiskOpen] = useState(false);

  const load = useCallback(async () => {
    if (!eid) return;
    setLoading(true);
    try {
      const params = {};
      if (highOnly) params.high_risk_only = true;
      if (owner.trim()) params.owner = owner.trim();
      if (processFilter.trim()) params.process_area = processFilter.trim();
      if (fsFilter.trim()) params.financial_statement_area = fsFilter.trim();
      const [rRes, hRes, pRes, cRes] = await Promise.all([
        http.get(`/audit-engagements/${encodeURIComponent(eid)}/risks`, { params }),
        http.get(`/audit-engagements/${encodeURIComponent(eid)}/risk-heatmap`),
        http.get(`/audit-engagements/${encodeURIComponent(eid)}/risks/audit-plan-preview`),
        http.get("/controls").catch(() => ({ data: [] })),
      ]);
      setRisks(rRes.data || []);
      setHeatmap(hRes.data || null);
      setPlanPreview(pRes.data?.auto_plan_items || []);
      setControls(Array.isArray(cRes.data) ? cRes.data : []);
    } catch {
      toast.error("Failed to load RACM");
    } finally {
      setLoading(false);
    }
  }, [eid, highOnly, owner, processFilter, fsFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const matrix = heatmap?.matrix || {};
  const categories = heatmap?.risk_categories || RISK_CATEGORIES;
  const processes = useMemo(() => Object.keys(matrix).sort(), [matrix]);
  const maxCell = useMemo(() => {
    let m = 0;
    processes.forEach((p) => {
      const row = matrix[p] || {};
      categories.forEach((c) => {
        m = Math.max(m, Number(row[c] || 0));
      });
    });
    return m || 1;
  }, [matrix, processes, categories]);

  const exportXlsx = async () => {
    try {
      const resp = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/risks/export.xlsx`, { responseType: "blob" });
      const url = URL.createObjectURL(resp.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `rACM-${eid}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Export started");
    } catch {
      toast.error("Export failed");
    }
  };

  const generateHighRiskProcedures = async () => {
    try {
      const { data } = await http.post(`/audit-engagements/${encodeURIComponent(eid)}/risks/generate-procedures-from-high-risk`);
      setRisks(data.risks || []);
      toast.success(`Updated ${data.updated_risks || 0} high-risk row(s)`);
      const pRes = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/risks/audit-plan-preview`);
      setPlanPreview(pRes.data?.auto_plan_items || []);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Generate failed");
    }
  };

  const createRisk = async (ev) => {
    ev.preventDefault();
    const fd = new FormData(ev.target);
    const ceRaw = fd.get("control_effectiveness_score");
    const ce = ceRaw && String(ceRaw).trim() ? parseInt(String(ceRaw), 10) : null;
    const body = {
      risk_title: fd.get("risk_title"),
      risk_description: fd.get("risk_description"),
      process_area: fd.get("process_area"),
      financial_statement_area: fd.get("financial_statement_area"),
      risk_category: fd.get("risk_category"),
      likelihood_score: parseInt(fd.get("likelihood_score") || "3", 10),
      impact_score: parseInt(fd.get("impact_score") || "3", 10),
      control_effectiveness_score: Number.isFinite(ce) ? ce : null,
      owner: fd.get("owner"),
      linked_controls: [],
      audit_procedures: [],
      procedures: [],
      status: "open",
    };
    try {
      await http.post(`/audit-engagements/${encodeURIComponent(eid)}/risks`, body);
      toast.success("Risk created");
      setNewRiskOpen(false);
      ev.target.reset();
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Create failed");
    }
  };

  const mapControl = async (riskId, controlId) => {
    if (!controlId) return;
    try {
      await http.post(`/risks/${encodeURIComponent(riskId)}/controls`, { control_id: controlId });
      toast.success("Control mapped");
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Map failed");
    }
  };

  const addProcedure = async (riskId, title, description) => {
    if (!title?.trim()) return;
    try {
      await http.post(`/risks/${encodeURIComponent(riskId)}/procedures`, { title: title.trim(), description: description || "" });
      toast.success("Procedure added");
      load();
    } catch {
      toast.error("Add procedure failed");
    }
  };

  if (!eid) return null;

  if (loading && !risks.length) {
    return <div className="p-6 font-mono text-xs text-[#737373]">Loading RACM…</div>;
  }

  return (
    <div className="space-y-6" data-testid="racm-builder-panel">
      {!compact ? (
        <PageHeader
          kicker="RACM"
          title="RACM builder"
          subtitle="Risk and control matrix: define risks, map controls from the library, attach procedures, and drive the audit plan from high-risk areas."
          right={
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={exportXlsx} className="inline-flex items-center gap-2 px-3 h-9 border border-[#262626] text-xs font-mono uppercase text-[#A3A3A3] hover:text-white">
                <FileXls size={16} /> Export Excel
              </button>
              <Link to={`/app/audit-planning/engagements/${encodeURIComponent(eid)}`} className="inline-flex items-center px-3 h-9 border border-[#262626] text-xs font-mono uppercase text-[#0A84FF] hover:border-white">
                Engagement hub
              </Link>
            </div>
          }
        />
      ) : (
        <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
          <div className="font-mono text-[10px] uppercase text-[#737373]">RACM · compact</div>
          <div className="flex flex-wrap gap-2">
            <Link to={`/app/audit-planning/engagements/${encodeURIComponent(eid)}/racm`} className="text-[10px] font-mono uppercase text-[#0A84FF] hover:underline">Open full builder</Link>
            <button type="button" onClick={exportXlsx} className="inline-flex items-center gap-1 px-2 h-8 border border-[#262626] text-[10px] font-mono uppercase text-[#A3A3A3] hover:text-white">
              <FileXls size={14} /> Export
            </button>
          </div>
        </div>
      )}

      <SectionCard kicker="FILTERS" title="Risk register filters" bodyClassName="p-4">
        <div className="flex flex-col lg:flex-row flex-wrap gap-3 lg:items-end">
          <label className="flex items-center gap-2 text-xs font-mono text-[#A3A3A3]">
            <input type="checkbox" checked={highOnly} onChange={(e) => setHighOnly(e.target.checked)} />
            High / critical only
          </label>
          <label className="text-xs font-mono text-[#737373]">Owner<input className="mt-1 block w-full min-w-[140px] bg-[#141414] border border-[#262626] px-2 h-9 text-sm" value={owner} onChange={(e) => setOwner(e.target.value)} placeholder="email" /></label>
          <label className="text-xs font-mono text-[#737373]">Process<input className="mt-1 block w-full min-w-[140px] bg-[#141414] border border-[#262626] px-2 h-9 text-sm" value={processFilter} onChange={(e) => setProcessFilter(e.target.value)} /></label>
          <label className="text-xs font-mono text-[#737373]">FS area<input className="mt-1 block w-full min-w-[140px] bg-[#141414] border border-[#262626] px-2 h-9 text-sm" value={fsFilter} onChange={(e) => setFsFilter(e.target.value)} /></label>
          <button type="button" onClick={() => load()} className="px-3 h-9 bg-white text-black font-mono text-xs uppercase">Apply</button>
        </div>
      </SectionCard>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <SectionCard kicker="HEATMAP" title="Inherent risk by process × category" bodyClassName="p-2 overflow-x-auto">
          <table className="text-xs min-w-[520px] w-full border-collapse">
            <thead>
              <tr>
                <th className="p-2 text-left font-mono text-[10px] uppercase text-[#737373] border border-[#262626]">Process</th>
                {categories.map((c) => (
                  <th key={c} className="p-2 text-left font-mono text-[9px] uppercase text-[#737373] border border-[#262626] max-w-[100px]">{c.replace(" Risk", "")}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {processes.length ? processes.map((p) => (
                <tr key={p}>
                  <td className="p-2 font-mono text-[10px] text-white border border-[#262626] whitespace-nowrap max-w-[140px] truncate" title={p}>{p}</td>
                  {categories.map((c) => {
                    const v = Number((matrix[p] || {})[c] || 0);
                    return (
                      <td key={c} className="p-0 border border-[#262626] text-center font-mono text-[10px]" style={{ background: heatColor(v, maxCell) }}>
                        {v || "—"}
                      </td>
                    );
                  })}
                </tr>
              )) : (
                <tr><td colSpan={1 + categories.length} className="p-4 text-[#737373] font-mono text-xs">No matrix data — add risks.</td></tr>
              )}
            </tbody>
          </table>
        </SectionCard>

        <SectionCard
          kicker="AUDIT PLAN"
          title="High-risk plan emphasis"
          right={
            <button type="button" onClick={generateHighRiskProcedures} className="inline-flex items-center gap-1 px-2 h-8 border border-[#262626] text-[10px] font-mono uppercase text-[#A3A3A3] hover:text-white">
              <Lightning size={14} /> Seed procedures
            </button>
          }
          bodyClassName="p-4 max-h-[320px] overflow-y-auto text-sm"
        >
          <p className="text-xs text-[#737373] mb-3">Items below pull from high / critical risks so the audit plan highlights where work is concentrated.</p>
          <ul className="space-y-2">
            {planPreview.map((it, i) => (
              <li key={`${it.risk_id}-${it.procedure_id || i}`} className="border-b border-[#262626]/80 pb-2">
                <div className="text-white text-sm">{it.procedure_title}</div>
                <div className="text-[10px] font-mono text-[#737373]">{it.risk_title} · {it.process_area} · {it.procedure_source}</div>
              </li>
            ))}
          </ul>
          {!planPreview.length ? <div className="text-[#737373] font-mono text-xs">No high-risk procedures yet.</div> : null}
        </SectionCard>
      </div>

      <SectionCard
        kicker="REGISTER"
        title="Risk · control · procedure"
        right={
          <button type="button" onClick={() => setNewRiskOpen((o) => !o)} className="inline-flex items-center gap-1 px-3 h-9 border border-[#262626] text-xs font-mono uppercase text-white">
            <Plus size={16} /> New risk
          </button>
        }
        bodyClassName="p-0"
      >
        {newRiskOpen ? (
          <form className="p-4 border-b border-[#262626] grid grid-cols-1 md:grid-cols-2 gap-3 bg-[#0A0A0A]/40" onSubmit={createRisk}>
            <input required name="risk_title" placeholder="Risk title" className="bg-[#141414] border border-[#262626] px-2 h-9 text-sm md:col-span-2" />
            <textarea required name="risk_description" placeholder="Description" className="bg-[#141414] border border-[#262626] px-2 py-2 text-sm min-h-[60px] md:col-span-2" />
            <input required name="process_area" placeholder="Process area" className="bg-[#141414] border border-[#262626] px-2 h-9 text-sm" />
            <input required name="financial_statement_area" placeholder="FS area" className="bg-[#141414] border border-[#262626] px-2 h-9 text-sm" />
            <select name="risk_category" className="bg-[#141414] border border-[#262626] px-2 h-9 text-sm">
              {RISK_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <input required name="owner" type="email" placeholder="Owner email" className="bg-[#141414] border border-[#262626] px-2 h-9 text-sm" />
            <label className="text-xs text-[#737373]">L (1–5)<input name="likelihood_score" type="number" min={1} max={5} defaultValue={3} className="mt-1 w-full bg-[#141414] border border-[#262626] px-2 h-9 text-sm" /></label>
            <label className="text-xs text-[#737373]">I (1–5)<input name="impact_score" type="number" min={1} max={5} defaultValue={3} className="mt-1 w-full bg-[#141414] border border-[#262626] px-2 h-9 text-sm" /></label>
            <label className="text-xs text-[#737373] md:col-span-2">Control eff. (1–5, optional)<input name="control_effectiveness_score" type="number" min={1} max={5} className="mt-1 w-full bg-[#141414] border border-[#262626] px-2 h-9 text-sm" /></label>
            <button type="submit" className="md:col-span-2 px-4 h-10 bg-white text-black font-mono text-xs uppercase">Create</button>
          </form>
        ) : null}
        <DataTable className="rounded-none border-0" maxHeightClassName={compact ? "max-h-[50vh]" : "max-h-[65vh]"}>
          <DataTableHead>
            <tr>
              <DataTableTh>Risk</DataTableTh>
              <DataTableTh>Scores</DataTableTh>
              <DataTableTh>Rating</DataTableTh>
              <DataTableTh>Controls</DataTableTh>
              <DataTableTh>Procedures</DataTableTh>
            </tr>
          </DataTableHead>
          <DataTableBody>
            {risks.map((r) => (
              <DataTableRow key={r.id}>
                <DataTableTd>
                  <div className="text-white text-sm">{r.risk_title}</div>
                  <div className="text-[10px] font-mono text-[#737373]">{r.process_area} · {r.financial_statement_area}</div>
                  <div className="text-[10px] text-[#A3A3A3]">{r.risk_category}</div>
                </DataTableTd>
                <DataTableTd className="font-mono text-[10px] text-[#D4D4D4]">
                  L{r.likelihood_score} I{r.impact_score} inh {r.inherent_risk_score}
                  <div>res {r.residual_risk_score}</div>
                </DataTableTd>
                <DataTableTd><RiskBadge level={r.risk_rating} /></DataTableTd>
                <DataTableTd className="align-top">
                  <div className="flex flex-wrap gap-1 mb-1">
                    {(r.linked_controls || []).map((cid) => (
                      <span key={cid} className="px-1.5 py-0.5 border border-[#404040] font-mono text-[9px] text-[#A3A3A3]">{cid.slice(0, 8)}…</span>
                    ))}
                  </div>
                  <select className="w-full max-w-[200px] bg-[#141414] border border-[#262626] text-[10px] h-8" defaultValue="" onChange={(e) => { mapControl(r.id, e.target.value); e.target.value = ""; }}>
                    <option value="">+ Map control…</option>
                    {controls.map((c) => (
                      <option key={c.id} value={c.id}>{c.code || c.id} — {c.name}</option>
                    ))}
                  </select>
                </DataTableTd>
                <DataTableTd className="align-top text-[10px] text-[#A3A3A3]">
                  <ul className="list-disc pl-4 mb-2 space-y-0.5">
                    {(r.racm_procedures || []).map((p) => (
                      <li key={p.id}>{p.title}{p.source === "high_risk_auto" ? <span className="text-[#737373]"> (auto)</span> : null}</li>
                    ))}
                  </ul>
                  <form className="flex flex-col gap-1" onSubmit={(ev) => { ev.preventDefault(); const fd = new FormData(ev.target); addProcedure(r.id, fd.get("pt"), fd.get("pd")); ev.target.reset(); }}>
                    <input name="pt" placeholder="Procedure title" className="bg-[#141414] border border-[#262626] px-1 h-7 text-[10px]" />
                    <input name="pd" placeholder="Description (optional)" className="bg-[#141414] border border-[#262626] px-1 h-7 text-[10px]" />
                    <button type="submit" className="h-7 border border-[#262626] font-mono text-[9px] uppercase text-white">Add</button>
                  </form>
                </DataTableTd>
              </DataTableRow>
            ))}
          </DataTableBody>
        </DataTable>
        {!risks.length ? <div className="p-6 font-mono text-xs text-[#737373]">No risks — create one or run seed.</div> : null}
      </SectionCard>
    </div>
  );
}
