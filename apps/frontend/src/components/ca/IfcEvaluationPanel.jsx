import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { http } from "../../lib/api";
import { toast } from "sonner";
import { ArrowSquareOut } from "@phosphor-icons/react";
import { PageHeader, SectionCard } from "../PageShell";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../DataTable";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { Textarea } from "../ui/textarea";
import { useAuth } from "../../lib/auth";
import { controlLibraryItemsFromResponse } from "../../lib/controlLibraryResponse";
import { useDashboardFilterParams } from "../../lib/useDashboardFilterParams";

const VIEWS = [
  { id: "dashboard", label: "Dashboard" },
  { id: "library", label: "Control library" },
  { id: "testing", label: "Control testing" },
  { id: "deficiencies", label: "Deficiencies" },
  { id: "certification", label: "Owner certification" },
  { id: "heatmap", label: "Heatmap" },
];

function cellColor(n, max) {
  if (!max || !n) return "rgba(38,38,38,0.35)";
  const t = Math.min(1, n / max);
  const r = Math.round(40 + t * 180);
  const g = Math.round(120 - t * 70);
  const b = Math.round(60 + t * 40);
  return `rgba(${r},${g},${b},0.85)`;
}

export default function IfcEvaluationPanel({ engagementId, compact = false }) {
  const eid = engagementId;
  const { user } = useAuth();
  const dashboardParams = useDashboardFilterParams();
  const [view, setView] = useState("dashboard");
  const [dash, setDash] = useState(null);
  const [library, setLibrary] = useState([]);
  const [heatmap, setHeatmap] = useState(null);
  const [loading, setLoading] = useState(false);
  const [newLib, setNewLib] = useState({ code: "", name: "", control_type: "preventive", process: "", description: "" });
  const [newTest, setNewTest] = useState({ control_library_id: "", test_type: "design effectiveness", period: "", tester_email: "" });
  const [defForm, setDefForm] = useState({ control_test_id: "", description: "", severity: "medium" });
  const [mgmt, setMgmt] = useState({ deficiencyId: "", text: "", owner: "" });
  const [cert, setCert] = useState({ scope: "IFC cycle FY", text: "", control_library_id: "" });

  const loadDash = useCallback(async () => {
    if (!eid) return;
    try {
      const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/ifc-dashboard`, { params: dashboardParams });
      setDash(data);
    } catch {
      setDash(null);
    }
  }, [eid, dashboardParams]);

  const loadLibrary = useCallback(async () => {
    try {
      const { data } = await http.get("/control-library", { params: dashboardParams });
      setLibrary(controlLibraryItemsFromResponse(data));
    } catch {
      setLibrary([]);
    }
  }, [dashboardParams]);

  const loadHeatmap = useCallback(async () => {
    if (!eid) return;
    try {
      const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/ifc-heatmap`, { params: dashboardParams });
      setHeatmap(data);
    } catch {
      setHeatmap(null);
    }
  }, [eid, dashboardParams]);

  useEffect(() => {
    loadLibrary();
  }, [loadLibrary]);

  useEffect(() => {
    if (!eid) return;
    setLoading(true);
    (async () => {
      await loadDash();
      await loadHeatmap();
      setLoading(false);
    })();
  }, [eid, loadDash, loadHeatmap]);

  const refresh = async () => {
    await loadDash();
    await loadHeatmap();
    await loadLibrary();
  };

  const saveTestResult = async (testId, effectiveness_score) => {
    try {
      const body =
        effectiveness_score === "pending"
          ? { result: "pending", evidence_refs: [] }
          : { effectiveness_score, evidence_refs: [] };
      await http.put(`/control-tests/${encodeURIComponent(testId)}/result`, body, { params: dashboardParams });
      toast.success("Test result saved");
      await loadDash();
      await loadHeatmap();
    } catch {
      toast.error("Save failed");
    }
  };

  const createTest = async (ev) => {
    ev.preventDefault();
    if (!newTest.control_library_id.trim() || !newTest.period.trim() || !newTest.tester_email.trim()) {
      toast.error("Control id, period, and tester required");
      return;
    }
    try {
      await http.post(
        `/audit-engagements/${encodeURIComponent(eid)}/control-tests`,
        {
          control_library_id: newTest.control_library_id.trim(),
          test_type: newTest.test_type,
          period: newTest.period.trim(),
          tester_email: newTest.tester_email.trim(),
        },
        { params: dashboardParams },
      );
      toast.success("Control test created");
      setNewTest((s) => ({ ...s, control_library_id: "" }));
      await loadDash();
      await loadHeatmap();
    } catch {
      toast.error("Create failed");
    }
  };

  const createDeficiency = async (ev) => {
    ev.preventDefault();
    if (!defForm.control_test_id.trim() || !defForm.description.trim()) {
      toast.error("Test id and description required");
      return;
    }
    try {
      await http.post(
        "/control-deficiencies",
        {
          engagement_id: eid,
          control_test_id: defForm.control_test_id.trim(),
          description: defForm.description.trim(),
          severity: defForm.severity,
          create_case: true,
          status: "open",
        },
        { params: dashboardParams },
      );
      toast.success("Deficiency logged (case created)");
      setDefForm({ control_test_id: "", description: "", severity: "medium" });
      await loadDash();
    } catch {
      toast.error("Failed");
    }
  };

  const saveMgmt = async (ev) => {
    ev.preventDefault();
    if (!mgmt.deficiencyId.trim() || !mgmt.text.trim()) return;
    try {
      await http.post(
        `/control-deficiencies/${encodeURIComponent(mgmt.deficiencyId.trim())}/management-response`,
        {
          response_text: mgmt.text.trim(),
          owner_email: mgmt.owner.trim() || user?.email,
        },
        { params: dashboardParams },
      );
      toast.success("Management response saved");
      setMgmt({ deficiencyId: "", text: "", owner: "" });
      await loadDash();
    } catch {
      toast.error("Save failed");
    }
  };

  const closeDef = async (id) => {
    try {
      await http.put(
        `/control-deficiencies/${encodeURIComponent(id)}`,
        { status: "closed", closure_notes: "Closed in IFC register" },
        { params: dashboardParams },
      );
      toast.success("Marked closed");
      await loadDash();
    } catch {
      toast.error("Update failed");
    }
  };

  const submitCert = async (ev) => {
    ev.preventDefault();
    try {
      await http.post(
        "/control-certifications",
        {
          engagement_id: eid,
          owner_email: user?.email,
          certification_text: cert.text.trim(),
          scope: cert.scope.trim(),
          control_library_id: cert.control_library_id.trim() || null,
        },
        { params: dashboardParams },
      );
      toast.success("Certification recorded");
      setCert({ scope: "IFC cycle FY", text: "", control_library_id: "" });
      await loadDash();
    } catch {
      toast.error("Certification failed");
    }
  };

  const addLibraryRow = async (ev) => {
    ev.preventDefault();
    if (!newLib.code.trim() || !newLib.name.trim()) {
      toast.error("Code and name required");
      return;
    }
    try {
      await http.post("/control-library", { ...newLib, objectives: [], activities: [], owners: [] }, { params: dashboardParams });
      toast.success("Control added");
      setNewLib({ code: "", name: "", control_type: "preventive", process: "", description: "" });
      await loadLibrary();
    } catch {
      toast.error("Add failed");
    }
  };

  const header = compact ? null : (
    <PageHeader kicker="IFC ENGINE" title="Internal financial controls evaluation" subtitle={`Engagement ${eid}`} right={null} />
  );

  const processes = heatmap?.processes || [];
  const cols = heatmap?.columns || [];
  const matrix = heatmap?.matrix || {};
  let maxCell = 0;
  processes.forEach((p) => {
    cols.forEach((c) => {
      maxCell = Math.max(maxCell, Number(matrix[p]?.[c] || 0));
    });
  });

  const tests = dash?.control_tests || [];
  const defs = dash?.deficiencies || [];

  return (
    <div className="space-y-4">
      {header}
      <div className="flex flex-wrap justify-between gap-2 items-center">
        <div className="flex flex-wrap gap-1 items-center">
          {compact ? (
            <Link to={`/app/audit-planning/engagements/${encodeURIComponent(eid)}/ifc-engine`} className="text-[10px] font-mono uppercase text-[#0A84FF] mr-2 inline-flex items-center gap-1">
              Full IFC <ArrowSquareOut size={12} />
            </Link>
          ) : null}
          {VIEWS.map((v) => (
            <button
              key={v.id}
              type="button"
              onClick={() => setView(v.id)}
              className={`px-2.5 h-8 font-mono text-[10px] uppercase border ${view === v.id ? "bg-white text-black border-white" : "border-[#262626] text-[#A3A3A3] hover:text-white"}`}
            >
              {v.label}
            </button>
          ))}
          <Link to="/app/audit-planning/control-library" className="text-[10px] font-mono uppercase text-[#737373] hover:text-white ml-2">
            Global library →
          </Link>
        </div>
        <button type="button" onClick={refresh} className="px-2 h-8 border border-[#262626] text-[10px] font-mono uppercase text-[#737373] hover:text-white">
          Refresh
        </button>
      </div>

      {loading ? <div className="text-[10px] font-mono text-[#525252]">Loading…</div> : null}

      {view === "dashboard" && dash ? (
        <div className="grid gap-3 md:grid-cols-4 font-mono text-xs">
          {Object.entries(dash.effectiveness_summary || {}).map(([k, v]) => (
            <div key={k} className="border border-[#262626] p-3">
              <div className="text-[#737373] uppercase text-[10px]">{k.replace(/_/g, " ")}</div>
              <div className="text-2xl text-white mt-1">{v}</div>
            </div>
          ))}
          <div className="border border-[#262626] p-3 md:col-span-4 text-[#A3A3A3]">
            Tests: {tests.length} · Deficiencies: {defs.length} · Certifications: {(dash.certifications || []).length}
          </div>
        </div>
      ) : null}

      {view === "library" ? (
        <SectionCard kicker="LIBRARY" title="Controls (read-only snapshot)" bodyClassName="p-0">
          <DataTable className="rounded-none border-0 max-h-[360px] overflow-auto">
            <DataTableHead>
              <tr>
                <DataTableTh>Code</DataTableTh>
                <DataTableTh>Name</DataTableTh>
                <DataTableTh>Type</DataTableTh>
                <DataTableTh>Process</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {(dash?.control_library_sample?.length ? dash.control_library_sample : library).map((row) => (
                <DataTableRow key={row.id}>
                  <DataTableTd className="font-mono text-xs">{row.code}</DataTableTd>
                  <DataTableTd className="text-xs text-white">{row.name}</DataTableTd>
                  <DataTableTd className="text-[10px] uppercase">{row.control_type}</DataTableTd>
                  <DataTableTd className="text-xs">{row.process}</DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
          <div className="p-4 border-t border-[#262626] space-y-2">
            <div className="text-[10px] font-mono uppercase text-[#737373]">Quick add (global library)</div>
            <form className="grid md:grid-cols-5 gap-2 items-end" onSubmit={addLibraryRow}>
              <Input placeholder="Code" value={newLib.code} onChange={(e) => setNewLib((s) => ({ ...s, code: e.target.value }))} className="h-9 text-xs font-mono" />
              <Input placeholder="Name" value={newLib.name} onChange={(e) => setNewLib((s) => ({ ...s, name: e.target.value }))} className="h-9 text-xs" />
              <select value={newLib.control_type} onChange={(e) => setNewLib((s) => ({ ...s, control_type: e.target.value }))} className="h-9 bg-[#0A0A0A] border border-[#262626] text-xs font-mono uppercase">
                {["preventive", "detective", "automated", "manual", "IT-dependent"].map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
              <Input placeholder="Process" value={newLib.process} onChange={(e) => setNewLib((s) => ({ ...s, process: e.target.value }))} className="h-9 text-xs" />
              <Button type="submit" size="sm" variant="secondary" className="font-mono text-[10px] uppercase">Add</Button>
              <Input placeholder="Description" value={newLib.description} onChange={(e) => setNewLib((s) => ({ ...s, description: e.target.value }))} className="h-9 text-xs md:col-span-5" />
            </form>
          </div>
        </SectionCard>
      ) : null}

      {view === "testing" ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <SectionCard kicker="PLAN" title="New control test" bodyClassName="p-4 space-y-3">
            <form className="space-y-2 text-xs" onSubmit={createTest}>
              <div>
                <Label className="text-[10px] font-mono uppercase text-[#737373]">Control library id or code</Label>
                <Input className="mt-1 h-9 font-mono text-xs" value={newTest.control_library_id} onChange={(e) => setNewTest((s) => ({ ...s, control_library_id: e.target.value }))} placeholder="UUID or IFC-REV-01" />
              </div>
              <div>
                <Label className="text-[10px] font-mono uppercase text-[#737373]">Test type</Label>
                <select className="mt-1 w-full h-9 bg-[#0A0A0A] border border-[#262626] text-xs font-mono" value={newTest.test_type} onChange={(e) => setNewTest((s) => ({ ...s, test_type: e.target.value }))}>
                  <option value="design effectiveness">design effectiveness</option>
                  <option value="operating effectiveness">operating effectiveness</option>
                </select>
              </div>
              <div>
                <Label className="text-[10px] font-mono uppercase text-[#737373]">Period</Label>
                <Input className="mt-1 h-9 text-xs" value={newTest.period} onChange={(e) => setNewTest((s) => ({ ...s, period: e.target.value }))} placeholder="FY2025" />
              </div>
              <div>
                <Label className="text-[10px] font-mono uppercase text-[#737373]">Tester email</Label>
                <Input className="mt-1 h-9 text-xs" value={newTest.tester_email} onChange={(e) => setNewTest((s) => ({ ...s, tester_email: e.target.value }))} placeholder={user?.email || ""} />
              </div>
              <Button type="submit" className="font-mono text-[10px] uppercase">Create test</Button>
            </form>
          </SectionCard>
          <SectionCard kicker="RESULTS" title="Design / operating effectiveness" bodyClassName="p-0">
            <DataTable className="rounded-none border-0">
              <DataTableHead>
                <tr>
                  <DataTableTh>Period</DataTableTh>
                  <DataTableTh>Type</DataTableTh>
                  <DataTableTh>Effectiveness</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {tests.map((t) => (
                  <DataTableRow key={t.id}>
                    <DataTableTd className="font-mono text-xs">{t.period}</DataTableTd>
                    <DataTableTd className="text-xs">{t.test_type}</DataTableTd>
                    <DataTableTd>
                      <select
                        className="bg-[#0A0A0A] border border-[#262626] text-[10px] font-mono uppercase h-8 px-2"
                        value={t.effectiveness_score || t.result || "pending"}
                        onChange={(e) => saveTestResult(t.id, e.target.value)}
                      >
                        {["pending", "effective", "partially_effective", "ineffective"].map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
                      </select>
                    </DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          </SectionCard>
        </div>
      ) : null}

      {view === "deficiencies" ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <SectionCard kicker="REGISTER" title="Control deficiencies" bodyClassName="p-0">
            <DataTable className="rounded-none border-0 max-h-64 overflow-auto">
              <DataTableHead>
                <tr>
                  <DataTableTh>Id</DataTableTh>
                  <DataTableTh>Status</DataTableTh>
                  <DataTableTh>Case</DataTableTh>
                  <DataTableTh />
                </tr>
              </DataTableHead>
              <DataTableBody>
                {defs.map((d) => (
                  <DataTableRow key={d.id}>
                    <DataTableTd className="font-mono text-[10px]">{d.id.slice(0, 8)}…</DataTableTd>
                    <DataTableTd className="text-xs uppercase">{d.status}</DataTableTd>
                    <DataTableTd className="font-mono text-[10px]">{d.case_id || "—"}</DataTableTd>
                    <DataTableTd>
                      {d.status !== "closed" ? (
                        <button type="button" className="text-[10px] uppercase text-[#0A84FF]" onClick={() => closeDef(d.id)}>Close</button>
                      ) : null}
                    </DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
            <div className="p-4 border-t border-[#262626] space-y-2">
              <div className="text-[10px] font-mono uppercase text-[#737373]">Log deficiency</div>
              <form className="space-y-2" onSubmit={createDeficiency}>
                <Input placeholder="Control test id" value={defForm.control_test_id} onChange={(e) => setDefForm((s) => ({ ...s, control_test_id: e.target.value }))} className="h-9 text-xs font-mono" />
                <Textarea placeholder="Description" value={defForm.description} onChange={(e) => setDefForm((s) => ({ ...s, description: e.target.value }))} rows={2} className="text-xs" />
                <Button type="submit" size="sm" variant="outline" className="font-mono text-[10px] uppercase">Create + case</Button>
              </form>
            </div>
          </SectionCard>
          <SectionCard kicker="MANAGEMENT" title="Management response" bodyClassName="p-4 space-y-3">
            <form className="space-y-2 text-xs" onSubmit={saveMgmt}>
              <Input placeholder="Deficiency id" value={mgmt.deficiencyId} onChange={(e) => setMgmt((s) => ({ ...s, deficiencyId: e.target.value }))} className="h-9 font-mono" />
              <Textarea placeholder="Response" value={mgmt.text} onChange={(e) => setMgmt((s) => ({ ...s, text: e.target.value }))} rows={3} />
              <Input placeholder="Owner email" value={mgmt.owner} onChange={(e) => setMgmt((s) => ({ ...s, owner: e.target.value }))} className="h-9" />
              <Button type="submit" size="sm" className="font-mono text-[10px] uppercase">Save response</Button>
            </form>
          </SectionCard>
        </div>
      ) : null}

      {view === "certification" ? (
        <SectionCard kicker="CERTIFICATION" title="Control owner attestation" bodyClassName="p-6 space-y-3">
          <form className="space-y-3 max-w-xl text-xs" onSubmit={submitCert}>
            <div>
              <Label className="text-[10px] font-mono uppercase text-[#737373]">Scope</Label>
              <Input className="mt-1 h-9" value={cert.scope} onChange={(e) => setCert((s) => ({ ...s, scope: e.target.value }))} />
            </div>
            <div>
              <Label className="text-[10px] font-mono uppercase text-[#737373]">Control library id (optional)</Label>
              <Input className="mt-1 h-9 font-mono" value={cert.control_library_id} onChange={(e) => setCert((s) => ({ ...s, control_library_id: e.target.value }))} />
            </div>
            <Textarea rows={4} placeholder="Certification text" value={cert.text} onChange={(e) => setCert((s) => ({ ...s, text: e.target.value }))} />
            <Button type="submit" className="font-mono text-[10px] uppercase">Submit certification</Button>
          </form>
        </SectionCard>
      ) : null}

      {view === "heatmap" && heatmap ? (
        <SectionCard kicker="HEATMAP" title="Process vs control effectiveness (test counts)" bodyClassName="p-4 overflow-auto">
          <table className="w-full text-[10px] font-mono border-collapse">
            <thead>
              <tr>
                <th className="border border-[#262626] p-2 text-left text-[#737373]">Process</th>
                {cols.map((c) => (
                  <th key={c} className="border border-[#262626] p-2 text-[#737373] uppercase">{c.replace(/_/g, " ")}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {processes.map((p) => (
                <tr key={p}>
                  <td className="border border-[#262626] p-2 text-white">{p}</td>
                  {cols.map((c) => {
                    const n = Number(matrix[p]?.[c] || 0);
                    return (
                      <td key={c} className="border border-[#262626] p-2 text-center text-black" style={{ background: cellColor(n, maxCell) }}>
                        {n || "—"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </SectionCard>
      ) : null}
    </div>
  );
}
