import React, { useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { http } from "../lib/api";
import DrillContextBar from "../components/DrillContextBar";
import { exceptionSourceDrillPath } from "../lib/drillPaths";
import { SeverityBadge, StatusBadge, PriorityTag } from "../components/Badges";
import { fmtUSD, fmtDate, fmtDateTime } from "../lib/format";
import { toast } from "sonner";
import { CaretLeft, Graph, PaperPlaneRight, CheckCircle, User } from "@phosphor-icons/react";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";

const STATUSES = ["open", "in_progress", "closed"];
const ROOT_CAUSES = ["Process gap", "System config", "Human error", "Policy not followed", "Data quality", "Approval override"];

export default function CaseDetail() {
  const { caseId } = useParams();
  const nav = useNavigate();
  const [d, setD] = useState(null);
  const [comment, setComment] = useState("");
  const [saving, setSaving] = useState(false);

  const load = async () => {
    const { data } = await http.get(`/cases/${caseId}`);
    setD(data);
  };
  useEffect(() => { load(); }, [caseId]); // eslint-disable-line

  const updateCase = async (patch) => {
    setSaving(true);
    try {
      await http.patch(`/cases/${caseId}`, patch);
      toast.success("Case updated");
      await load();
    } catch { toast.error("Update failed"); }
    setSaving(false);
  };

  const addComment = async () => {
    if (!comment.trim()) return;
    try {
      await http.post(`/cases/${caseId}/comments`, { comment });
      setComment("");
      await load();
    } catch { toast.error("Comment failed"); }
  };

  if (!d) return <div className="p-8 font-mono text-xs uppercase text-muted-foreground">Loading case…</div>;

  const c = d.case;
  const ex = d.exception;

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="case-detail">
        <button onClick={() => nav("/app/cases")} className="mb-2 flex items-center gap-1 text-xs font-mono uppercase tracking-wider text-muted-foreground transition-colors hover:text-foreground" data-testid="back-to-cases">
          <CaretLeft size={12} /> Back to cases
        </button>
        <DrillContextBar
          crumbs={[
            { label: "App", to: "/app" },
            { label: "Cases", to: "/app/cases" },
            { label: c.id.slice(0, 12) },
          ]}
        />

        <PageHeader
          kicker={`${c.control_code} · Case ${c.id.slice(0, 8)}`}
          title={c.title}
          subtitle={`${c.entity} · ${c.process}`}
          right={
            <Link
              to={`/app/evidence/${c.exception_id}`}
              className="wow-badge flex items-center gap-2 rounded-full border border-zinc-200 bg-zinc-100 px-4 py-2 text-xs font-mono uppercase tracking-wider text-foreground transition-colors hover:bg-zinc-200 dark:border-zinc-700 dark:bg-zinc-900 dark:hover:bg-zinc-800"
              data-testid="view-evidence-btn"
            >
              <Graph size={12} /> Evidence graph
            </Link>
          }
        />

        <div className="flex flex-wrap items-center gap-3 mt-3 mb-6">
          <SeverityBadge severity={c.severity} size="md" />
          <StatusBadge status={c.status} />
          <PriorityTag priority={c.priority} />
          {d.governance?.worm && (
            <span className="wow-badge px-3 py-2 font-mono text-[10px] uppercase text-amber-700 dark:text-amber-400">WORM locked</span>
          )}
          {d.governance?.legal_hold && (
            <span className="wow-badge px-3 py-2 font-mono text-[10px] uppercase text-primary">Legal hold</span>
          )}
        </div>
        {(d.governance?.worm || d.governance?.legal_hold) && (
          <p className="mb-6 max-w-3xl text-xs text-muted-foreground">
            {d.governance.worm && "Closed cases are immutable unless a permitted role uses API override (?force_override=true). "}
            {d.governance.legal_hold && "This record is under legal hold — retention purge is blocked."}
          </p>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Left: Main */}
          <SectionCard className="lg:col-span-2" kicker="CASE" title="Summary & activity">
            <h3 className="mb-3 font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">Summary</h3>
            <p className="mb-6 text-sm leading-relaxed text-foreground">{c.summary}</p>

          {ex && (() => {
            const drill = exceptionSourceDrillPath(ex);
            return (
              <div
                role={drill ? "button" : undefined}
                tabIndex={drill ? 0 : undefined}
                onClick={() => drill && nav(drill)}
                onKeyDown={(ev) => { if (drill && (ev.key === "Enter" || ev.key === " ")) { ev.preventDefault(); nav(drill); } }}
                className={`mb-6 rounded-xl border border-zinc-200 bg-zinc-50/90 p-4 dark:border-zinc-800 dark:bg-zinc-900/40 ${drill ? "cursor-pointer transition-colors hover:bg-zinc-100 dark:hover:bg-zinc-900/70" : ""}`}
                data-testid="source-record-drill"
              >
                <div className="mb-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Source record · click to drill</div>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-mono text-sm text-primary">{ex.source_record_type} · {ex.source_record_id}{drill ? " →" : ""}</span>
                  <span className="font-mono text-xs text-muted-foreground">anomaly={ex.anomaly_score} · materiality={ex.materiality_score}</span>
                </div>
                {(ex.control_code || c.control_code) ? (
                  <div className="mt-3 font-mono text-[10px] uppercase" onClick={(e) => e.stopPropagation()}>
                    <Link to={`/app/drill/control/${encodeURIComponent(ex.control_code || c.control_code)}`} className="text-primary hover:underline">Control {ex.control_code || c.control_code}</Link>
                    {" · "}
                    <Link to={`/app/evidence/${encodeURIComponent(c.exception_id)}`} className="text-primary hover:underline">Evidence graph</Link>
                  </div>
                ) : null}
              </div>
            );
          })()}

          <h3 className="mb-3 font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">Activity</h3>
          <div className="mb-6 space-y-3">
            {d.history.map(h => (
              <div key={h.id} className="flex items-start gap-3 text-xs">
                <div className="mt-1.5 h-1 w-1 bg-primary" />
                <div>
                  <span className="text-foreground">Status → <span className="font-mono">{h.new_status}</span></span>
                  <span className="ml-2 font-mono text-muted-foreground">{fmtDateTime(h.changed_at)} ·</span>
                  {h.changed_by_user_email ? (
                    <Link to={`/app/drill/user/${encodeURIComponent(h.changed_by_user_email)}`} className="ml-1 font-mono text-primary hover:underline">
                      {h.changed_by_user_email}
                    </Link>
                  ) : null}
                </div>
              </div>
            ))}
            {d.comments.map(cm => (
              <div key={cm.id} className="border-l border-zinc-200 py-1 pl-3 dark:border-zinc-700">
                <div className="flex items-center gap-2 text-xs">
                  <User size={10} className="text-muted-foreground" />
                  <span className="text-foreground">{cm.user_name}</span>
                  <span className="font-mono text-muted-foreground">{fmtDateTime(cm.created_at)}</span>
                </div>
                <div className="mt-1 text-sm text-foreground">{cm.comment}</div>
              </div>
            ))}
          </div>

          <div className="flex gap-2">
            <textarea
              data-testid="case-comment-input"
              value={comment}
              onChange={e => setComment(e.target.value)}
              placeholder="Add investigation note or closure evidence..."
              rows={2}
              className="flex-1 resize-none rounded-xl border border-zinc-200 bg-white px-3 py-2 text-sm text-foreground outline-none ring-offset-background placeholder:text-muted-foreground focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary/20 dark:border-zinc-700 dark:bg-zinc-950"
            />
            <button
              data-testid="submit-comment-btn"
              onClick={addComment}
              className="self-stretch rounded-xl bg-foreground px-4 font-mono text-xs uppercase tracking-wider text-background transition-colors hover:bg-foreground/90"
            >
              <PaperPlaneRight size={14} />
            </button>
          </div>
          </SectionCard>

          {/* Right: Actions */}
          <SectionCard kicker="ACTIONS" title="Case actions" data-testid="case-actions">

            <div className="space-y-4">
              <KVField label="Owner" value={c.owner_name || c.owner_email} />
              <KVField label="Exposure" value={fmtUSD(c.financial_exposure)} mono />
              <KVField label="Detected" value={fmtDate(c.detected_at)} mono />
              <KVField label="Due" value={fmtDate(c.due_date)} mono />
              <KVField label="Opened" value={fmtDate(c.opened_at)} mono />
              {c.closed_at && <KVField label="Closed" value={fmtDate(c.closed_at)} mono />}
            </div>

            <div className="mt-6 space-y-4 border-t border-zinc-200 pt-6 dark:border-zinc-800">
              <div>
                <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">Change status</div>
                <div className="flex flex-wrap gap-2">
                  {STATUSES.map(s => (
                    <button
                      key={s}
                      data-testid={`status-btn-${s}`}
                      disabled={saving || c.status === s}
                      onClick={() => updateCase({ status: s })}
                      className={`h-10 rounded-full px-4 text-xs font-mono uppercase tracking-wider transition-colors ${
                        c.status === s
                          ? "bg-foreground text-background"
                          : "border border-zinc-200 bg-zinc-50 text-muted-foreground hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900 dark:hover:bg-zinc-800"
                      }`}
                    >{s === "in_progress" ? "In progress" : s}</button>
                  ))}
                </div>
              </div>

            <div>
              <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">Root cause</div>
              <select
                data-testid="root-cause-select"
                value={c.root_cause_category || ""}
                onChange={(e) => updateCase({ root_cause_category: e.target.value })}
                className="h-10 w-full rounded-xl border border-zinc-200 bg-white px-3 text-sm text-foreground outline-none focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary/20 dark:border-zinc-700 dark:bg-zinc-950"
              >
                <option value="">— select —</option>
                {ROOT_CAUSES.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>

            {c.status !== "closed" && (
              <button
                data-testid="close-case-btn"
                onClick={() => updateCase({ status: "closed" })}
                className="w-full flex items-center justify-center gap-2 bg-[#30D158] text-black font-mono text-xs uppercase tracking-wider py-3 hover:bg-[#65E08C] transition-colors rounded-full shadow-[0_18px_45px_rgba(34,197,94,0.18)]"
              >
                <CheckCircle size={14} weight="fill" /> Close & retest
              </button>
            )}
          </div>
          </SectionCard>
        </div>
      </div>
    </PageShell>
  );
}

const KVField = ({ label, value, mono }) => (
  <div className="flex items-baseline justify-between">
    <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{label}</span>
    <span className={`text-sm text-foreground ${mono ? "font-mono tabular-nums" : ""}`}>{value}</span>
  </div>
);
