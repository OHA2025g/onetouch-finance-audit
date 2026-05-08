import React, { useEffect, useState } from "react";
import { http } from "../../lib/api";
import { toast } from "sonner";
import { SectionCard } from "../PageShell";

const STATUSES = ["draft", "planned", "in-progress", "completed", "archived"];
const AUDIT_TYPES = ["statutory", "internal", "GST", "tax", "IFC", "special audit"];
const RISKS = ["low", "medium", "high", "critical"];

/**
 * Edit core planning fields, add milestones / planning notes (parent engagement for all CA modules).
 */
export default function AuditPlanningPanel({ engagementId, engagement, onSaved }) {
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState(null);
  const [msTitle, setMsTitle] = useState("");
  const [msDue, setMsDue] = useState("");
  const [note, setNote] = useState("");

  useEffect(() => {
    if (!engagement) return;
    const tl = engagement.timeline || {};
    setForm({
      entity_name: engagement.entity_name || "",
      financial_year: engagement.financial_year || "",
      audit_type: engagement.audit_type || "statutory",
      audit_scope: engagement.audit_scope || "",
      audit_objectives: (engagement.audit_objectives || []).join("\n"),
      start_date: engagement.start_date || "",
      end_date: engagement.end_date || "",
      audit_partner: engagement.audit_partner || "",
      audit_manager: engagement.audit_manager || "",
      status: engagement.status === "in_progress" ? "in-progress" : (engagement.status || "draft"),
      risk_level: engagement.risk_level || "medium",
      tl_planning: tl.planning_start || "",
      tl_field_start: tl.fieldwork_start || "",
      tl_field_end: tl.fieldwork_end || "",
      tl_reporting: tl.reporting_date || "",
    });
  }, [engagement]);

  if (!form) return null;

  const savePlanning = async (ev) => {
    ev.preventDefault();
    setSaving(true);
    try {
      const objectives = form.audit_objectives.split("\n").map((s) => s.trim()).filter(Boolean);
      await http.put(`/audit-engagements/${encodeURIComponent(engagementId)}`, {
        entity_name: form.entity_name,
        financial_year: form.financial_year,
        audit_type: form.audit_type,
        audit_scope: form.audit_scope,
        audit_objectives: objectives,
        start_date: form.start_date,
        end_date: form.end_date,
        audit_partner: form.audit_partner,
        audit_manager: form.audit_manager,
        status: form.status,
        risk_level: form.risk_level,
        timeline: {
          planning_start: form.tl_planning || null,
          fieldwork_start: form.tl_field_start || null,
          fieldwork_end: form.tl_field_end || null,
          reporting_date: form.tl_reporting || null,
        },
      });
      toast.success("Planning saved");
      onSaved?.();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Save failed");
    }
    setSaving(false);
  };

  const addMilestone = async (ev) => {
    ev.preventDefault();
    if (!msTitle.trim() || !msDue.trim()) {
      toast.error("Milestone title and due date required");
      return;
    }
    try {
      await http.post(`/audit-engagements/${encodeURIComponent(engagementId)}/milestones`, {
        title: msTitle.trim(),
        due_date: msDue.trim(),
        status: "pending",
      });
      setMsTitle("");
      setMsDue("");
      toast.success("Milestone added");
      onSaved?.();
    } catch {
      toast.error("Could not add milestone");
    }
  };

  const addNote = async (ev) => {
    ev.preventDefault();
    if (!note.trim()) return;
    try {
      await http.post(`/audit-engagements/${encodeURIComponent(engagementId)}/planning-notes`, {
        note: note.trim(),
        visibility: "team",
      });
      setNote("");
      toast.success("Note added");
      onSaved?.();
    } catch {
      toast.error("Could not add note");
    }
  };

  return (
    <div className="space-y-4">
      <SectionCard kicker="PLANNING" title="Engagement profile & timeline" bodyClassName="p-4 md:p-6">
        <form className="space-y-4" onSubmit={savePlanning}>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <label className="text-xs font-mono text-[#737373]">Client / entity
              <input className="mt-1 w-full bg-[#141414] border border-[#262626] px-2 h-9 text-sm text-white" value={form.entity_name} onChange={(e) => setForm((f) => ({ ...f, entity_name: e.target.value }))} required />
            </label>
            <label className="text-xs font-mono text-[#737373]">Financial year
              <input className="mt-1 w-full bg-[#141414] border border-[#262626] px-2 h-9 text-sm text-white" value={form.financial_year} onChange={(e) => setForm((f) => ({ ...f, financial_year: e.target.value }))} required />
            </label>
            <label className="text-xs font-mono text-[#737373]">Audit type
              <select className="mt-1 w-full bg-[#141414] border border-[#262626] px-2 h-9 text-sm text-white" value={form.audit_type} onChange={(e) => setForm((f) => ({ ...f, audit_type: e.target.value }))}>
                {AUDIT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </label>
            <label className="text-xs font-mono text-[#737373]">Status
              <select className="mt-1 w-full bg-[#141414] border border-[#262626] px-2 h-9 text-sm text-white" value={form.status} onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))}>
                {STATUSES.map((s) => <option key={s} value={s}>{s === "in-progress" ? "In progress" : s}</option>)}
              </select>
            </label>
            <label className="text-xs font-mono text-[#737373]">Risk level
              <select className="mt-1 w-full bg-[#141414] border border-[#262626] px-2 h-9 text-sm text-white" value={form.risk_level} onChange={(e) => setForm((f) => ({ ...f, risk_level: e.target.value }))}>
                {RISKS.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </label>
            <label className="text-xs font-mono text-[#737373]">Start (ISO)
              <input className="mt-1 w-full bg-[#141414] border border-[#262626] px-2 h-9 text-sm text-white" value={form.start_date} onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))} required />
            </label>
            <label className="text-xs font-mono text-[#737373]">End (ISO)
              <input className="mt-1 w-full bg-[#141414] border border-[#262626] px-2 h-9 text-sm text-white" value={form.end_date} onChange={(e) => setForm((f) => ({ ...f, end_date: e.target.value }))} required />
            </label>
            <label className="text-xs font-mono text-[#737373]">Assigned partner
              <input className="mt-1 w-full bg-[#141414] border border-[#262626] px-2 h-9 text-sm text-white" value={form.audit_partner} onChange={(e) => setForm((f) => ({ ...f, audit_partner: e.target.value }))} required />
            </label>
            <label className="text-xs font-mono text-[#737373]">Assigned manager
              <input className="mt-1 w-full bg-[#141414] border border-[#262626] px-2 h-9 text-sm text-white" value={form.audit_manager} onChange={(e) => setForm((f) => ({ ...f, audit_manager: e.target.value }))} required />
            </label>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <label className="text-xs font-mono text-[#737373]">Planning start
              <input className="mt-1 w-full bg-[#141414] border border-[#262626] px-2 h-9 text-sm text-white" value={form.tl_planning} onChange={(e) => setForm((f) => ({ ...f, tl_planning: e.target.value }))} placeholder="YYYY-MM-DD" />
            </label>
            <label className="text-xs font-mono text-[#737373]">Fieldwork start
              <input className="mt-1 w-full bg-[#141414] border border-[#262626] px-2 h-9 text-sm text-white" value={form.tl_field_start} onChange={(e) => setForm((f) => ({ ...f, tl_field_start: e.target.value }))} placeholder="YYYY-MM-DD" />
            </label>
            <label className="text-xs font-mono text-[#737373]">Fieldwork end
              <input className="mt-1 w-full bg-[#141414] border border-[#262626] px-2 h-9 text-sm text-white" value={form.tl_field_end} onChange={(e) => setForm((f) => ({ ...f, tl_field_end: e.target.value }))} placeholder="YYYY-MM-DD" />
            </label>
            <label className="text-xs font-mono text-[#737373]">Reporting date
              <input className="mt-1 w-full bg-[#141414] border border-[#262626] px-2 h-9 text-sm text-white" value={form.tl_reporting} onChange={(e) => setForm((f) => ({ ...f, tl_reporting: e.target.value }))} placeholder="YYYY-MM-DD" />
            </label>
          </div>
          <label className="text-xs font-mono text-[#737373] block">Scope (summary)
            <textarea className="mt-1 w-full bg-[#141414] border border-[#262626] px-2 py-2 text-sm text-white min-h-[72px]" value={form.audit_scope} onChange={(e) => setForm((f) => ({ ...f, audit_scope: e.target.value }))} required />
          </label>
          <label className="text-xs font-mono text-[#737373] block">Objectives (one per line)
            <textarea className="mt-1 w-full bg-[#141414] border border-[#262626] px-2 py-2 text-sm text-white min-h-[72px]" value={form.audit_objectives} onChange={(e) => setForm((f) => ({ ...f, audit_objectives: e.target.value }))} />
          </label>
          <button type="submit" disabled={saving} className="px-4 h-10 bg-white text-black font-mono text-xs uppercase tracking-wider disabled:opacity-50">
            {saving ? "Saving…" : "Save planning"}
          </button>
        </form>
      </SectionCard>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <SectionCard kicker="MILESTONE" title="Add milestone" bodyClassName="p-4">
          <form className="space-y-2" onSubmit={addMilestone}>
            <input className="w-full bg-[#141414] border border-[#262626] px-2 h-9 text-sm" placeholder="Title" value={msTitle} onChange={(e) => setMsTitle(e.target.value)} />
            <input className="w-full bg-[#141414] border border-[#262626] px-2 h-9 text-sm font-mono text-xs" placeholder="Due (ISO datetime)" value={msDue} onChange={(e) => setMsDue(e.target.value)} />
            <button type="submit" className="px-3 h-9 border border-[#262626] text-xs font-mono uppercase text-white hover:border-white">Add milestone</button>
          </form>
        </SectionCard>
        <SectionCard kicker="NOTE" title="Planning note" bodyClassName="p-4">
          <form className="space-y-2" onSubmit={addNote}>
            <textarea className="w-full bg-[#141414] border border-[#262626] px-2 py-2 text-sm min-h-[72px]" placeholder="Planning observation…" value={note} onChange={(e) => setNote(e.target.value)} />
            <button type="submit" className="px-3 h-9 border border-[#262626] text-xs font-mono uppercase text-white hover:border-white">Add note</button>
          </form>
        </SectionCard>
      </div>
    </div>
  );
}
