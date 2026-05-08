import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { ArrowLeft } from "@phosphor-icons/react";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";

const AUDIT_TYPES = ["statutory", "internal", "GST", "tax", "IFC", "special audit"];

export default function AuditEngagementNew() {
  const nav = useNavigate();
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    engagement_id: "",
    entity_name: "",
    financial_year: "2024-25",
    audit_type: "statutory",
    audit_scope: "",
    audit_objectives: "",
    scope_lines: "",
    start_date: "",
    end_date: "",
    audit_partner: "",
    audit_manager: "",
    assigned_team: "",
    status: "draft",
    risk_level: "medium",
    tl_planning: "",
    tl_field_start: "",
    tl_field_end: "",
    tl_reporting: "",
  });

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const objectives = form.audit_objectives.split("\n").map((s) => s.trim()).filter(Boolean);
      const team = form.assigned_team.split(",").map((s) => s.trim()).filter(Boolean);
      const scopeLines = form.scope_lines.split("\n").map((s) => s.trim()).filter(Boolean);
      const scopes = scopeLines.map((description) => ({ description }));
      const structuredObjectives = objectives.map((title) => ({ title, description: "" }));
      await http.post("/audit-engagements", {
        engagement_id: form.engagement_id.trim(),
        entity_name: form.entity_name.trim(),
        financial_year: form.financial_year.trim(),
        audit_type: form.audit_type,
        audit_scope: form.audit_scope.trim(),
        audit_objectives: objectives,
        start_date: form.start_date,
        end_date: form.end_date,
        audit_partner: form.audit_partner.trim(),
        audit_manager: form.audit_manager.trim(),
        assigned_team: team,
        status: form.status,
        risk_level: form.risk_level,
        scopes,
        objectives: structuredObjectives,
        timeline: {
          planning_start: form.tl_planning || null,
          fieldwork_start: form.tl_field_start || null,
          fieldwork_end: form.tl_field_end || null,
          reporting_date: form.tl_reporting || null,
        },
      });
      toast.success("Engagement created");
      nav(`/app/audit-planning/engagements/${encodeURIComponent(form.engagement_id.trim())}`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Create failed");
    }
    setSaving(false);
  };

  return (
    <PageShell maxWidth="max-w-[900px]">
      <Link to="/app/audit-planning" className="inline-flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-[#737373] hover:text-white mb-4">
        <ArrowLeft size={14} /> Back to list
      </Link>
      <PageHeader kicker="AUDIT PLANNING" title="Create audit engagement" subtitle="Define scope, team, and timeline. This engagement becomes the parent for materiality, RACM, FS audit, and reporting." />
      <SectionCard kicker="FORM" title="Engagement details" bodyClassName="p-6">
        <form className="space-y-4" onSubmit={submit}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <label className="block text-xs font-mono uppercase text-[#737373]">Engagement ID
              <input required className="mt-1 w-full bg-[#141414] border border-[#262626] px-3 h-10 text-sm text-white" value={form.engagement_id} onChange={(ev) => setForm((f) => ({ ...f, engagement_id: ev.target.value }))} placeholder="ENG-2025-IN-001" />
            </label>
            <label className="block text-xs font-mono uppercase text-[#737373]">Entity name
              <input required className="mt-1 w-full bg-[#141414] border border-[#262626] px-3 h-10 text-sm text-white" value={form.entity_name} onChange={(ev) => setForm((f) => ({ ...f, entity_name: ev.target.value }))} />
            </label>
            <label className="block text-xs font-mono uppercase text-[#737373]">Financial year
              <input required className="mt-1 w-full bg-[#141414] border border-[#262626] px-3 h-10 text-sm text-white" value={form.financial_year} onChange={(ev) => setForm((f) => ({ ...f, financial_year: ev.target.value }))} />
            </label>
            <label className="block text-xs font-mono uppercase text-[#737373]">Audit type
              <select className="mt-1 w-full bg-[#141414] border border-[#262626] px-3 h-10 text-sm text-white" value={form.audit_type} onChange={(ev) => setForm((f) => ({ ...f, audit_type: ev.target.value }))}>
                {AUDIT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </label>
            <label className="block text-xs font-mono uppercase text-[#737373]">Start (ISO)
              <input required className="mt-1 w-full bg-[#141414] border border-[#262626] px-3 h-10 text-sm text-white" value={form.start_date} onChange={(ev) => setForm((f) => ({ ...f, start_date: ev.target.value }))} placeholder="2025-01-15T00:00:00Z" />
            </label>
            <label className="block text-xs font-mono uppercase text-[#737373]">End (ISO)
              <input required className="mt-1 w-full bg-[#141414] border border-[#262626] px-3 h-10 text-sm text-white" value={form.end_date} onChange={(ev) => setForm((f) => ({ ...f, end_date: ev.target.value }))} placeholder="2025-05-30T00:00:00Z" />
            </label>
            <label className="block text-xs font-mono uppercase text-[#737373]">Audit partner
              <input required className="mt-1 w-full bg-[#141414] border border-[#262626] px-3 h-10 text-sm text-white" value={form.audit_partner} onChange={(ev) => setForm((f) => ({ ...f, audit_partner: ev.target.value }))} />
            </label>
            <label className="block text-xs font-mono uppercase text-[#737373]">Audit manager
              <input required className="mt-1 w-full bg-[#141414] border border-[#262626] px-3 h-10 text-sm text-white" value={form.audit_manager} onChange={(ev) => setForm((f) => ({ ...f, audit_manager: ev.target.value }))} />
            </label>
            <label className="block text-xs font-mono uppercase text-[#737373]">Status
              <select className="mt-1 w-full bg-[#141414] border border-[#262626] px-3 h-10 text-sm text-white" value={form.status} onChange={(ev) => setForm((f) => ({ ...f, status: ev.target.value }))}>
                {["draft", "planned", "in-progress", "completed", "archived"].map((s) => <option key={s} value={s}>{s === "in-progress" ? "In progress" : s}</option>)}
              </select>
            </label>
            <label className="block text-xs font-mono uppercase text-[#737373]">Risk level
              <select className="mt-1 w-full bg-[#141414] border border-[#262626] px-3 h-10 text-sm text-white" value={form.risk_level} onChange={(ev) => setForm((f) => ({ ...f, risk_level: ev.target.value }))}>
                {["low", "medium", "high", "critical"].map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
          </div>
          <label className="block text-xs font-mono uppercase text-[#737373]">Assigned team (emails, comma-separated)
            <input className="mt-1 w-full bg-[#141414] border border-[#262626] px-3 h-10 text-sm text-white" value={form.assigned_team} onChange={(ev) => setForm((f) => ({ ...f, assigned_team: ev.target.value }))} placeholder="auditor@onetouch.ai, controller@onetouch.ai" />
          </label>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            <label className="block text-xs font-mono uppercase text-[#737373] md:col-span-2">Planning start
              <input className="mt-1 w-full bg-[#141414] border border-[#262626] px-3 h-10 text-sm text-white" value={form.tl_planning} onChange={(ev) => setForm((f) => ({ ...f, tl_planning: ev.target.value }))} placeholder="YYYY-MM-DD" />
            </label>
            <label className="block text-xs font-mono uppercase text-[#737373]">Fieldwork start
              <input className="mt-1 w-full bg-[#141414] border border-[#262626] px-3 h-10 text-sm text-white" value={form.tl_field_start} onChange={(ev) => setForm((f) => ({ ...f, tl_field_start: ev.target.value }))} placeholder="YYYY-MM-DD" />
            </label>
            <label className="block text-xs font-mono uppercase text-[#737373]">Fieldwork end
              <input className="mt-1 w-full bg-[#141414] border border-[#262626] px-3 h-10 text-sm text-white" value={form.tl_field_end} onChange={(ev) => setForm((f) => ({ ...f, tl_field_end: ev.target.value }))} placeholder="YYYY-MM-DD" />
            </label>
            <label className="block text-xs font-mono uppercase text-[#737373] md:col-span-2 lg:col-span-4">Reporting date
              <input className="mt-1 w-full bg-[#141414] border border-[#262626] px-3 h-10 text-sm text-white" value={form.tl_reporting} onChange={(ev) => setForm((f) => ({ ...f, tl_reporting: ev.target.value }))} placeholder="YYYY-MM-DD" />
            </label>
          </div>
          <label className="block text-xs font-mono uppercase text-[#737373]">Audit scope (summary)
            <textarea required className="mt-1 w-full bg-[#141414] border border-[#262626] px-3 py-2 text-sm text-white min-h-[80px]" value={form.audit_scope} onChange={(ev) => setForm((f) => ({ ...f, audit_scope: ev.target.value }))} />
          </label>
          <label className="block text-xs font-mono uppercase text-[#737373]">Scope areas (one line each → structured scopes)
            <textarea className="mt-1 w-full bg-[#141414] border border-[#262626] px-3 py-2 text-sm text-white min-h-[64px]" value={form.scope_lines} onChange={(ev) => setForm((f) => ({ ...f, scope_lines: ev.target.value }))} placeholder={"Revenue / O2C\nPayroll\n…"} />
          </label>
          <label className="block text-xs font-mono uppercase text-[#737373]">Audit objectives (one per line)
            <textarea className="mt-1 w-full bg-[#141414] border border-[#262626] px-3 py-2 text-sm text-white min-h-[80px]" value={form.audit_objectives} onChange={(ev) => setForm((f) => ({ ...f, audit_objectives: ev.target.value }))} />
          </label>
          <button type="submit" disabled={saving} className="px-4 h-11 bg-white text-black font-mono text-xs uppercase tracking-wider disabled:opacity-50">
            {saving ? "Saving…" : "Create engagement"}
          </button>
        </form>
      </SectionCard>
    </PageShell>
  );
}
