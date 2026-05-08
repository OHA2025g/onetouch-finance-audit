import React, { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { http } from "../../lib/api";
import { toast } from "sonner";
import { SectionCard } from "../../components/PageShell";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../../components/DataTable";

const SEVERITIES = ["low", "medium", "high", "critical"];
const SOURCES = ["manual", "case", "control", "compliance", "fs", "schedule"];

export default function ObservationBuilderPage() {
  const { engagementId } = useParams();
  const eid = decodeURIComponent(engagementId || "");
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState({
    title: "",
    description: "",
    severity: "medium",
    material: false,
    pervasive: false,
    source: "manual",
  });

  const load = useCallback(async () => {
    const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/observations`);
    setRows(Array.isArray(data) ? data : []);
  }, [eid]);

  useEffect(() => {
    load().catch(() => toast.error("Failed to load observations"));
  }, [load]);

  const create = async (e) => {
    e.preventDefault();
    if (!form.title.trim() || !form.description.trim()) {
      toast.error("Title and description required");
      return;
    }
    try {
      await http.post(`/audit-engagements/${encodeURIComponent(eid)}/observations`, {
        title: form.title.trim(),
        description: form.description.trim(),
        severity: form.severity,
        material: form.material,
        pervasive: form.pervasive,
        source: form.source,
      });
      setForm((f) => ({ ...f, title: "", description: "" }));
      await load();
      toast.success("Observation added");
    } catch {
      toast.error("Create failed");
    }
  };

  const toggleResolved = async (row) => {
    try {
      await http.put(`/audit-engagements/${encodeURIComponent(eid)}/observations/${encodeURIComponent(row.id)}`, {
        resolved: !row.resolved,
      });
      await load();
    } catch {
      toast.error("Update failed");
    }
  };

  return (
    <div className="space-y-6">
      <SectionCard kicker="KAM / OTHER" title="New observation" bodyClassName="p-4">
        <form onSubmit={create} className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <input
            placeholder="Title"
            value={form.title}
            onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
            className="md:col-span-2 bg-black border border-[#262626] px-3 py-2 text-sm text-white"
          />
          <textarea
            placeholder="Description"
            value={form.description}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            className="md:col-span-2 bg-black border border-[#262626] px-3 py-2 text-sm text-white min-h-[80px]"
          />
          <select value={form.severity} onChange={(e) => setForm((f) => ({ ...f, severity: e.target.value }))} className="bg-black border border-[#262626] px-3 py-2 text-sm text-white">
            {SEVERITIES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <select value={form.source} onChange={(e) => setForm((f) => ({ ...f, source: e.target.value }))} className="bg-black border border-[#262626] px-3 py-2 text-sm text-white">
            {SOURCES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <label className="flex items-center gap-2 text-sm text-[#A3A3A3]">
            <input type="checkbox" checked={form.material} onChange={(e) => setForm((f) => ({ ...f, material: e.target.checked }))} /> Material
          </label>
          <label className="flex items-center gap-2 text-sm text-[#A3A3A3]">
            <input type="checkbox" checked={form.pervasive} onChange={(e) => setForm((f) => ({ ...f, pervasive: e.target.checked }))} /> Pervasive
          </label>
          <div className="md:col-span-2">
            <button type="submit" className="px-4 h-10 bg-white text-black font-mono text-xs uppercase">
              Add observation
            </button>
          </div>
        </form>
      </SectionCard>
      <SectionCard kicker="REGISTER" title="Observations" bodyClassName="p-0">
        <DataTable className="rounded-none border-0 max-h-[60vh]">
          <DataTableHead>
            <tr>
              <DataTableTh>Title</DataTableTh>
              <DataTableTh>Severity</DataTableTh>
              <DataTableTh>Flags</DataTableTh>
              <DataTableTh>Resolved</DataTableTh>
            </tr>
          </DataTableHead>
          <DataTableBody>
            {rows.map((r) => (
              <DataTableRow key={r.id}>
                <DataTableTd className="text-sm text-white max-w-md">{r.title}</DataTableTd>
                <DataTableTd className="font-mono text-[10px]">{r.severity}</DataTableTd>
                <DataTableTd className="text-[10px] text-[#737373]">
                  {r.material ? "M " : ""}
                  {r.pervasive ? "P " : ""}
                  {r.source}
                </DataTableTd>
                <DataTableTd>
                  <button type="button" onClick={() => toggleResolved(r)} className="text-xs font-mono uppercase text-[#0A84FF] hover:underline">
                    {r.resolved ? "Reopen" : "Resolve"}
                  </button>
                </DataTableTd>
              </DataTableRow>
            ))}
          </DataTableBody>
        </DataTable>
      </SectionCard>
    </div>
  );
}
