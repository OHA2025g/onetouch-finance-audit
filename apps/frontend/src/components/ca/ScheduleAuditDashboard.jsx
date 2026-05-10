import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { http } from "../../lib/api";
import { toast } from "sonner";
import { ArrowSquareOut, Flag, Paperclip } from "@phosphor-icons/react";
import { PageHeader, SectionCard } from "../PageShell";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../DataTable";
import { Button } from "../ui/button";
import { Textarea } from "../ui/textarea";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { useAuth } from "../../lib/auth";
import { useDashboardFilterParams } from "../../lib/useDashboardFilterParams";

const TABS = [
  { id: "assets", label: "Fixed assets" },
  { id: "revenue", label: "Revenue" },
  { id: "expenses", label: "Expenses" },
  { id: "inventory", label: "Inventory" },
  { id: "liabilities", label: "Liabilities" },
];

function flagLabel(key) {
  return key.replace(/_/g, " ");
}

export default function ScheduleAuditDashboard({ engagementId, compact = false }) {
  const eid = engagementId;
  const { user } = useAuth();
  const dashboardParams = useDashboardFilterParams();
  const [tab, setTab] = useState("assets");
  const [doc, setDoc] = useState(null);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [exTitle, setExTitle] = useState("");
  const [exDesc, setExDesc] = useState("");
  const [exFlag, setExFlag] = useState("");
  const [exAmt, setExAmt] = useState("");
  const [evLabel, setEvLabel] = useState("");
  const [evRef, setEvRef] = useState("");
  const [conclusion, setConclusion] = useState("");
  const [reviewerEmail, setReviewerEmail] = useState("");
  const [signedOff, setSignedOff] = useState(false);

  const loadSummary = useCallback(async () => {
    if (!eid) return;
    try {
      const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/schedules`, { params: dashboardParams });
      setSummary(data);
    } catch {
      setSummary(null);
    }
  }, [eid, dashboardParams]);

  const loadDoc = useCallback(async () => {
    if (!eid) return;
    setLoading(true);
    try {
      const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/schedules/${tab}`, { params: dashboardParams });
      setDoc(data);
      const c = data?.conclusion || {};
      setConclusion(c.conclusion || "");
      setReviewerEmail(c.reviewer_email || user?.email || "");
      setSignedOff(!!c.signed_off);
    } catch {
      toast.error("Failed to load schedule");
      setDoc(null);
    } finally {
      setLoading(false);
    }
  }, [eid, tab, user?.email, dashboardParams]);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  useEffect(() => {
    loadDoc();
  }, [loadDoc]);

  const saveConclusion = async () => {
    try {
      await http.post(
        `/audit-engagements/${encodeURIComponent(eid)}/schedules/${tab}/conclusion`,
        {
          conclusion: conclusion || "—",
          preparer_email: user?.email,
          reviewer_email: reviewerEmail || user?.email,
          signed_off: signedOff,
        },
        { params: dashboardParams },
      );
      toast.success("Conclusion saved");
      await loadDoc();
      await loadSummary();
    } catch {
      toast.error("Could not save conclusion");
    }
  };

  const addException = async () => {
    if (!exTitle.trim() || !exDesc.trim()) {
      toast.error("Title and description required");
      return;
    }
    try {
      await http.post(
        `/audit-engagements/${encodeURIComponent(eid)}/schedules/${tab}/exception`,
        {
          title: exTitle.trim(),
          description: exDesc.trim(),
          amount: exAmt ? parseFloat(exAmt, 10) : null,
          severity: "medium",
          create_case: false,
          exception_flag: exFlag.trim() || null,
        },
        { params: dashboardParams },
      );
      toast.success("Exception logged");
      setExTitle("");
      setExDesc("");
      setExFlag("");
      setExAmt("");
      await loadDoc();
      await loadSummary();
    } catch {
      toast.error("Failed to add exception");
    }
  };

  const addEvidence = async () => {
    if (!evLabel.trim() || !evRef.trim()) {
      toast.error("Label and reference required");
      return;
    }
    try {
      await http.post(
        `/audit-engagements/${encodeURIComponent(eid)}/schedules/${tab}/evidence`,
        {
          label: evLabel.trim(),
          reference: evRef.trim(),
          ref_type: "file",
        },
        { params: dashboardParams },
      );
      toast.success("Evidence attached");
      setEvLabel("");
      setEvRef("");
      await loadDoc();
      await loadSummary();
    } catch {
      toast.error("Evidence attach failed");
    }
  };

  const setProcedureStatus = async (procId, status) => {
    try {
      await http.put(`/audit-engagements/${encodeURIComponent(eid)}/schedules/${tab}/procedures/${encodeURIComponent(procId)}`, { status }, { params: dashboardParams });
      toast.success("Procedure updated");
      await loadDoc();
      await loadSummary();
    } catch {
      toast.error("Update failed");
    }
  };

  const flags = doc?.exception_flags || {};
  const activeFlags = Object.entries(flags).filter(([, v]) => v);

  const header = compact ? null : (
    <PageHeader
      kicker="SCHEDULE AUDIT"
      title="Statutory schedule workbooks"
      subtitle={`Engagement ${eid}`}
      right={null}
    />
  );

  return (
    <div className="space-y-4">
      {header}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap gap-1 items-center">
          {compact ? (
            <Link
              to={`/app/audit-planning/engagements/${encodeURIComponent(eid)}/schedules-audit`}
              className="text-[10px] font-mono uppercase text-[#0A84FF] inline-flex items-center gap-1 mr-2"
            >
              Full dashboard <ArrowSquareOut size={12} />
            </Link>
          ) : null}
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={`px-2.5 h-8 font-mono text-[10px] uppercase border ${tab === t.id ? "bg-white text-black border-white" : "border-[#262626] text-[#A3A3A3] hover:text-white"}`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <button type="button" onClick={() => { loadDoc(); loadSummary(); }} className="px-2 h-8 border border-[#262626] text-[10px] font-mono uppercase text-[#737373] hover:text-white">
          Refresh
        </button>
      </div>

      {summary?.schedules?.length ? (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-[10px] font-mono">
          {summary.schedules.map((s) => (
            <button
              key={s.schedule_type}
              type="button"
              onClick={() => setTab(s.schedule_type)}
              className={`border p-2 text-left ${tab === s.schedule_type ? "border-white bg-[#1A1A1A]" : "border-[#262626] hover:border-[#404040]"}`}
            >
              <div className="text-white uppercase">{s.schedule_type}</div>
              <div className="text-[#737373] mt-1">
                Exc {s.exception_count} · Ev {s.evidence_count} · Proc {s.procedure_completed}/{s.procedure_total ?? 0}
              </div>
              {s.conclusion_signed ? <div className="text-[#30D158] mt-1">Signed</div> : <div className="text-[#525252] mt-1">Open</div>}
            </button>
          ))}
        </div>
      ) : null}

      {activeFlags.length ? (
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-[10px] font-mono uppercase text-[#737373] flex items-center gap-1">
            <Flag size={14} className="text-[#FF9F0A]" /> Exception flags
          </span>
          {activeFlags.map(([k]) => (
            <span key={k} className="px-2 py-0.5 text-[9px] font-mono uppercase bg-[#9A3412]/35 text-[#FDBA74] border border-[#C2410C]/50">
              {flagLabel(k)}
            </span>
          ))}
        </div>
      ) : (
        <div className="text-[10px] font-mono text-[#525252]">No derived exception flags for this schedule (or not yet initialized).</div>
      )}

      {loading ? <div className="text-xs font-mono text-[#525252]">Loading…</div> : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard kicker="PROCEDURES" title="Audit programme" bodyClassName="p-0">
          <DataTable className="rounded-none border-0">
            <DataTableHead>
              <tr>
                <DataTableTh>Procedure</DataTableTh>
                <DataTableTh>Status</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {(doc?.audit_procedures || []).map((p) => (
                <DataTableRow key={p.id}>
                  <DataTableTd className="text-xs text-[#E5E5E5]">{p.title}</DataTableTd>
                  <DataTableTd>
                    <select
                      value={p.status || "pending"}
                      onChange={(ev) => setProcedureStatus(p.id, ev.target.value)}
                      className="bg-[#0A0A0A] border border-[#262626] text-[10px] font-mono uppercase h-8 px-2"
                    >
                      {["pending", "in_progress", "completed", "waived"].map((s) => (
                        <option key={s} value={s}>{s.replace("_", " ")}</option>
                      ))}
                    </select>
                  </DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>

        <SectionCard kicker="PAYLOAD" title="Schedule analytics (demo data)" bodyClassName="p-4">
          <pre className="text-[10px] font-mono text-[#A3A3A3] overflow-auto max-h-[280px] whitespace-pre-wrap">{JSON.stringify(doc?.payload || {}, null, 2)}</pre>
        </SectionCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard kicker="EXCEPTIONS" title="Logged findings" bodyClassName="p-0">
          <DataTable className="rounded-none border-0 max-h-52 overflow-auto">
            <DataTableHead>
              <tr>
                <DataTableTh>Title</DataTableTh>
                <DataTableTh>Flag</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {(doc?.exceptions || []).map((x) => (
                <DataTableRow key={x.id}>
                  <DataTableTd className="text-xs">
                    <div className="text-white">{x.title}</div>
                    <div className="text-[10px] text-[#737373]">{x.description?.slice(0, 120)}</div>
                  </DataTableTd>
                  <DataTableTd className="font-mono text-[10px] text-[#FF9F0A]">{x.exception_flag || "—"}</DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
          <div className="p-4 border-t border-[#262626] space-y-2">
            <div className="text-[10px] font-mono uppercase text-[#737373]">Add exception</div>
            <Input value={exTitle} onChange={(e) => setExTitle(e.target.value)} placeholder="Title" className="h-9 text-xs" />
            <Textarea value={exDesc} onChange={(e) => setExDesc(e.target.value)} placeholder="Description" rows={2} className="text-xs" />
            <div className="grid grid-cols-2 gap-2">
              <Input value={exFlag} onChange={(e) => setExFlag(e.target.value)} placeholder="Flag code (optional)" className="h-9 text-xs font-mono" />
              <Input value={exAmt} onChange={(e) => setExAmt(e.target.value)} placeholder="Amount" className="h-9 text-xs font-mono" />
            </div>
            <Button type="button" variant="outline" size="sm" className="font-mono text-[10px] uppercase" onClick={addException}>
              Log exception
            </Button>
          </div>
        </SectionCard>

        <SectionCard kicker="EVIDENCE" title="Attachments" bodyClassName="p-4 space-y-3">
          <div className="flex items-center gap-2 text-[10px] font-mono uppercase text-[#737373]">
            <Paperclip size={16} /> Working paper / file reference
          </div>
          <ul className="space-y-1 max-h-32 overflow-auto text-xs font-mono text-[#A3A3A3]">
            {(doc?.evidence || []).map((ev) => (
              <li key={ev.id}>
                <span className="text-white">{ev.label}</span> · {ev.reference}{" "}
                <span className="text-[#525252]">({ev.uploaded_by})</span>
              </li>
            ))}
          </ul>
          <div className="space-y-2">
            <div>
              <Label className="text-[10px] font-mono uppercase text-[#737373]">Label</Label>
              <Input value={evLabel} onChange={(e) => setEvLabel(e.target.value)} className="mt-1 h-9 text-xs" />
            </div>
            <div>
              <Label className="text-[10px] font-mono uppercase text-[#737373]">Reference</Label>
              <Input value={evRef} onChange={(e) => setEvRef(e.target.value)} className="mt-1 h-9 text-xs font-mono" placeholder="e.g. WP-REV-03.pdf or https://..." />
            </div>
            <Button type="button" size="sm" variant="secondary" className="font-mono text-[10px] uppercase" onClick={addEvidence}>
              Attach evidence
            </Button>
          </div>
        </SectionCard>
      </div>

      <SectionCard kicker="CONCLUSION" title="Audit conclusion & reviewer sign-off" bodyClassName="p-6 space-y-4">
        <Textarea value={conclusion} onChange={(e) => setConclusion(e.target.value)} rows={4} className="text-sm" placeholder="Overall conclusion on this schedule area…" />
        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <Label className="text-[10px] font-mono uppercase text-[#737373]">Reviewer email</Label>
            <Input value={reviewerEmail} onChange={(e) => setReviewerEmail(e.target.value)} className="mt-1 h-9 text-xs" />
          </div>
          <label className="flex items-center gap-2 text-xs text-[#A3A3A3] mt-6 md:mt-8 cursor-pointer">
            <input type="checkbox" checked={signedOff} onChange={(e) => setSignedOff(e.target.checked)} className="accent-white" />
            Reviewer sign-off (locks expectation — store timestamp on save)
          </label>
        </div>
        <Button type="button" onClick={saveConclusion} className="font-mono text-xs uppercase">
          Save conclusion
        </Button>
        {doc?.conclusion?.reviewer_signed_at ? (
          <div className="text-[10px] font-mono text-[#30D158]">Signed at {doc.conclusion.reviewer_signed_at}</div>
        ) : null}
      </SectionCard>
    </div>
  );
}
