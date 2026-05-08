import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft } from "@phosphor-icons/react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageShell, SectionCard, PageHeader } from "../components/PageShell";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";

export default function ControlLibraryPage() {
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState({
    code: "",
    name: "",
    control_type: "preventive",
    process: "",
    description: "",
  });

  const load = useCallback(async () => {
    try {
      const { data } = await http.get("/control-library");
      setRows(Array.isArray(data) ? data : []);
    } catch {
      toast.error("Failed to load library");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const submit = async (ev) => {
    ev.preventDefault();
    if (!form.code.trim() || !form.name.trim()) {
      toast.error("Code and name required");
      return;
    }
    try {
      await http.post("/control-library", { ...form, objectives: [], activities: [], owners: [] });
      toast.success("Control added");
      setForm({ code: "", name: "", control_type: "preventive", process: "", description: "" });
      await load();
    } catch {
      toast.error("Save failed");
    }
  };

  return (
    <PageShell maxWidth="max-w-[1200px]">
      <Link to="/app/audit-planning" className="inline-flex items-center gap-2 text-xs font-mono uppercase text-[#737373] hover:text-white mb-4">
        <ArrowLeft size={14} /> Audit planning
      </Link>
      <PageHeader kicker="IFC" title="Control library" subtitle="Enterprise control inventory for IFC evaluation" />
      <div className="grid gap-6 lg:grid-cols-3">
        <SectionCard kicker="NEW" title="Add control" bodyClassName="p-6 space-y-3">
          <form className="space-y-3 text-xs" onSubmit={submit}>
            <div>
              <Label className="text-[10px] font-mono uppercase text-[#737373]">Code</Label>
              <Input className="mt-1 h-9 font-mono" value={form.code} onChange={(e) => setForm((s) => ({ ...s, code: e.target.value }))} />
            </div>
            <div>
              <Label className="text-[10px] font-mono uppercase text-[#737373]">Name</Label>
              <Input className="mt-1 h-9" value={form.name} onChange={(e) => setForm((s) => ({ ...s, name: e.target.value }))} />
            </div>
            <div>
              <Label className="text-[10px] font-mono uppercase text-[#737373]">Type</Label>
              <select className="mt-1 w-full h-9 bg-[#0A0A0A] border border-[#262626] font-mono text-[10px] uppercase" value={form.control_type} onChange={(e) => setForm((s) => ({ ...s, control_type: e.target.value }))}>
                {["preventive", "detective", "automated", "manual", "IT-dependent"].map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <Label className="text-[10px] font-mono uppercase text-[#737373]">Process</Label>
              <Input className="mt-1 h-9" value={form.process} onChange={(e) => setForm((s) => ({ ...s, process: e.target.value }))} />
            </div>
            <div>
              <Label className="text-[10px] font-mono uppercase text-[#737373]">Description</Label>
              <Input className="mt-1 h-9" value={form.description} onChange={(e) => setForm((s) => ({ ...s, description: e.target.value }))} />
            </div>
            <Button type="submit" className="font-mono text-[10px] uppercase w-full">Save to library</Button>
          </form>
        </SectionCard>
        <SectionCard kicker="INVENTORY" title="All controls" bodyClassName="p-0 lg:col-span-2">
          <DataTable className="rounded-none border-0 max-h-[70vh] overflow-auto">
            <DataTableHead>
              <tr>
                <DataTableTh>Code</DataTableTh>
                <DataTableTh>Name</DataTableTh>
                <DataTableTh>Type</DataTableTh>
                <DataTableTh>Process</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {rows.map((r) => (
                <DataTableRow key={r.id}>
                  <DataTableTd className="font-mono text-xs text-white">{r.code}</DataTableTd>
                  <DataTableTd className="text-xs">{r.name}</DataTableTd>
                  <DataTableTd className="text-[10px] uppercase">{r.control_type}</DataTableTd>
                  <DataTableTd className="text-xs text-[#A3A3A3]">{r.process}</DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>
      </div>
    </PageShell>
  );
}
