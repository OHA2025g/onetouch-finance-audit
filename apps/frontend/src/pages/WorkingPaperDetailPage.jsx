import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { SectionCard } from "../components/PageShell";
import { ArrowLeft } from "@phosphor-icons/react";
import { useAuth } from "../lib/auth";

const TICKS = [
  "agreed to invoice",
  "agreed to bank",
  "recalculated",
  "verified",
  "exception noted",
  "pending clarification",
];

export default function WorkingPaperDetailPage() {
  const { engagementId, paperId } = useParams();
  const eid = decodeURIComponent(engagementId || "");
  const pid = decodeURIComponent(paperId || "");
  const base = `/app/audit-planning/engagements/${encodeURIComponent(eid)}/working-papers`;

  const [wp, setWp] = useState(null);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [refsText, setRefsText] = useState("");
  const [evLabel, setEvLabel] = useState("");
  const [evRef, setEvRef] = useState("");
  const [evType, setEvType] = useState("file");
  const [note, setNote] = useState("");
  const [noteType, setNoteType] = useState("review");
  const { user } = useAuth();

  useEffect(() => {
    if (!pid) return;
    (async () => {
      try {
        const { data } = await http.get(`/working-papers/${encodeURIComponent(pid)}`);
        setWp(data);
        setTitle(data.title || "");
        setBody(data.body || "");
        const r = (data.references || []).map((x) => (x.description ? `${x.ref_code} — ${x.description}` : x.ref_code));
        setRefsText(r.join("\n"));
      } catch {
        toast.error("Working paper not found");
      }
    })();
  }, [pid]);

  const saveWp = async () => {
    const refLines = refsText.split("\n").map((s) => s.trim()).filter(Boolean);
    const references = refLines.map((line) => {
      const [code, ...rest] = line.split(/\s+—\s+|\s+-\s+/);
      return { ref_code: code?.trim() || line, description: rest.join(" — ").trim() || null };
    });
    try {
      const { data } = await http.put(`/working-papers/${encodeURIComponent(pid)}`, {
        title: title.trim(),
        body: body.trim() || null,
        references,
      });
      setWp((prev) => (prev ? { ...prev, ...data } : data));
      toast.success("Saved");
    } catch {
      toast.error("Save failed");
    }
  };

  const attachEvidence = async (e) => {
    e.preventDefault();
    if (!evLabel.trim() || !evRef.trim()) {
      toast.error("Label and reference required");
      return;
    }
    try {
      await http.post(`/working-papers/${encodeURIComponent(pid)}/evidence`, {
        label: evLabel.trim(),
        reference: evRef.trim(),
        ref_type: evType,
      });
      setEvLabel("");
      setEvRef("");
      const { data } = await http.get(`/working-papers/${encodeURIComponent(pid)}`);
      setWp(data);
      toast.success("Evidence attached");
    } catch {
      toast.error("Attach failed");
    }
  };

  const addReviewNote = async (e) => {
    e.preventDefault();
    if (!note.trim() || !user?.email) {
      toast.error("Note and login required");
      return;
    }
    try {
      await http.post(`/working-papers/${encodeURIComponent(pid)}/review-notes`, {
        note: note.trim(),
        author_email: user.email,
        note_type: noteType,
      });
      setNote("");
      const { data } = await http.get(`/working-papers/${encodeURIComponent(pid)}`);
      setWp(data);
      toast.success("Review note added");
    } catch {
      toast.error("Could not add note");
    }
  };

  const signOff = async (role) => {
    if (!user?.email) {
      toast.error("Sign in to sign off");
      return;
    }
    try {
      const { data } = await http.post(`/working-papers/${encodeURIComponent(pid)}/sign-off`, {
        role,
        signer_email: user.email,
      });
      setWp((prev) => (prev ? { ...prev, ...data } : data));
      const { data: full } = await http.get(`/working-papers/${encodeURIComponent(pid)}`);
      setWp(full);
      toast.success("Sign-off recorded");
    } catch {
      toast.error("Sign-off failed");
    }
  };

  if (!wp) {
    return <div className="font-mono text-xs text-[#737373] uppercase tracking-wider py-8">Loading…</div>;
  }

  return (
    <div className="space-y-6">
      <Link to={base} className="inline-flex items-center gap-2 text-xs font-mono uppercase text-[#737373] hover:text-white">
        <ArrowLeft size={14} /> Back to repository
      </Link>

      <div className="flex flex-wrap gap-2 items-center justify-between">
        <div>
          <div className="font-mono text-[10px] uppercase text-[#737373]">Reference</div>
          <div className="text-xl text-white font-mono tracking-tight">{wp.reference}</div>
        </div>
        <div className="flex flex-wrap gap-2 text-xs font-mono">
          <div className="border border-[#262626] px-3 py-2 text-[#A3A3A3]">
            Prepared: <span className="text-white">{wp.prepared_by || "—"}</span>
          </div>
          <div className="border border-[#262626] px-3 py-2 text-[#A3A3A3]">
            Reviewed: <span className="text-white">{wp.reviewed_by || "—"}</span>
          </div>
          <div className="border border-[#262626] px-3 py-2 text-[#A3A3A3]">
            Approved: <span className="text-white">{wp.approved_by || "—"}</span>
          </div>
        </div>
      </div>

      <SectionCard kicker="WORKING PAPER" title="Documentation" bodyClassName="p-4 space-y-3">
        <input
          value={title}
          onChange={(ev) => setTitle(ev.target.value)}
          className="w-full bg-black border border-[#262626] px-3 py-2 text-white text-sm"
        />
        <textarea
          value={body}
          onChange={(ev) => setBody(ev.target.value)}
          rows={12}
          className="w-full bg-black border border-[#262626] px-3 py-2 text-sm text-white font-mono"
        />
        <div>
          <div className="font-mono text-[10px] uppercase text-[#737373] mb-1">Cross-references (one per line)</div>
          <textarea
            value={refsText}
            onChange={(ev) => setRefsText(ev.target.value)}
            rows={4}
            className="w-full bg-black border border-[#262626] px-3 py-2 text-sm text-white font-mono"
          />
        </div>
        <button type="button" onClick={saveWp} className="px-4 h-10 bg-white text-black font-mono text-xs uppercase">
          Save working paper
        </button>
      </SectionCard>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <SectionCard kicker="EVIDENCE" title="Attachments" bodyClassName="p-4 space-y-3">
          <form onSubmit={attachEvidence} className="space-y-2">
            <input
              placeholder="Label"
              value={evLabel}
              onChange={(ev) => setEvLabel(ev.target.value)}
              className="w-full bg-black border border-[#262626] px-3 py-2 text-sm text-white"
            />
            <input
              placeholder="Reference (file / URL / id)"
              value={evRef}
              onChange={(ev) => setEvRef(ev.target.value)}
              className="w-full bg-black border border-[#262626] px-3 py-2 text-sm text-white"
            />
            <select value={evType} onChange={(ev) => setEvType(ev.target.value)} className="w-full bg-black border border-[#262626] px-3 py-2 text-sm text-white">
              <option value="file">file</option>
              <option value="url">url</option>
              <option value="scan">scan</option>
            </select>
            <button type="submit" className="px-4 h-9 border border-white text-white font-mono text-[10px] uppercase">
              Attach evidence
            </button>
          </form>
          <ul className="mt-4 space-y-2 text-sm border-t border-[#262626] pt-4">
            {(wp.audit_evidence || []).map((ev) => (
              <li key={ev.id} className="text-[#A3A3A3]">
                <span className="text-white">{ev.label}</span>
                <span className="font-mono text-[10px] ml-2 text-[#0A84FF]">{ev.ref_type}</span>
                <div className="font-mono text-[10px] text-[#737373] break-all">{ev.reference}</div>
              </li>
            ))}
          </ul>
        </SectionCard>

        <SectionCard kicker="REVIEW" title="Notes &amp; tick context" bodyClassName="p-4 space-y-3">
          <form onSubmit={addReviewNote} className="space-y-2">
            <select value={noteType} onChange={(ev) => setNoteType(ev.target.value)} className="w-full bg-black border border-[#262626] px-3 py-2 text-sm text-white">
              <option value="review">review</option>
              <option value="clearing">clearing</option>
              <option value="query">query</option>
            </select>
            <textarea
              value={note}
              onChange={(ev) => setNote(ev.target.value)}
              rows={3}
              placeholder="Review note…"
              className="w-full bg-black border border-[#262626] px-3 py-2 text-sm text-white"
            />
            <button type="submit" className="px-4 h-9 border border-[#262626] text-white font-mono text-[10px] uppercase">
              Add note
            </button>
          </form>
          <ul className="mt-4 space-y-2 text-sm max-h-48 overflow-y-auto">
            {(wp.review_notes || []).map((n) => (
              <li key={n.id} className="border-b border-[#262626] pb-2">
                <span className="font-mono text-[10px] text-[#0A84FF]">{n.note_type}</span>
                <div className="text-white mt-1">{n.note}</div>
                <div className="font-mono text-[10px] text-[#737373]">{n.author_email}</div>
              </li>
            ))}
          </ul>
          <div className="pt-4 border-t border-[#262626] space-y-2">
            <div className="font-mono text-[10px] uppercase text-[#737373]">Sign-off workflow</div>
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={() => signOff("preparer")} className="px-3 h-9 border border-[#262626] text-xs font-mono uppercase text-white">
                Prepared by (me)
              </button>
              <button type="button" onClick={() => signOff("reviewer")} className="px-3 h-9 border border-[#262626] text-xs font-mono uppercase text-white">
                Reviewed by (me)
              </button>
              <button type="button" onClick={() => signOff("partner")} className="px-3 h-9 border border-[#262626] text-xs font-mono uppercase text-white">
                Approved by (me)
              </button>
            </div>
            <p className="text-[10px] text-[#737373] font-mono">Tick marks for vouching are applied in the Vouching workbench ({TICKS.slice(0, 3).join(", ")}…).</p>
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
