import React, { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import clsx from "clsx";
import { http } from "../lib/api";
import { toast } from "sonner";
import { fmtUSD, fmtDate } from "../lib/format";
import { CaretLeft } from "@phosphor-icons/react";
import DrillContextBar from "../components/DrillContextBar";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { SeverityBadge } from "../components/Badges";
import { errorMessageFromAxios } from "../lib/apiErrorMessage";

function workflowSeverity(status) {
  const s = (status || "open").toLowerCase();
  if (s === "approved") return "low";
  if (s === "submitted") return "medium";
  return "warning";
}

export default function ReconciliationDetailPage() {
  const { reconciliationId } = useParams();
  const nav = useNavigate();
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const [evUrl, setEvUrl] = useState("");
  const [evNotes, setEvNotes] = useState("");
  const [reopenReason, setReopenReason] = useState("");

  const load = useCallback(() => {
    if (!reconciliationId) return Promise.resolve();
    setErr(null);
    return http
      .get(`/reconciliations/${encodeURIComponent(reconciliationId)}`)
      .then((r) => setData(r.data))
      .catch((e) => setErr(errorMessageFromAxios(e, "Failed to load")));
  }, [reconciliationId]);

  useEffect(() => {
    load();
  }, [load]);

  const runAction = async (label, fn) => {
    try {
      setBusy(true);
      await fn();
      toast.success(label);
      await load();
    } catch (e) {
      toast.error(errorMessageFromAxios(e, `${label} failed`));
    } finally {
      setBusy(false);
    }
  };

  if (err) {
    return (
      <PageShell maxWidth="max-w-[960px]">
        <div className="p-8 font-mono text-xs text-[#FF9F0A]">{err}</div>
      </PageShell>
    );
  }
  if (!data?.reconciliation) {
    return <div className="p-8 font-mono text-xs uppercase tracking-wider text-[#737373]">Loading reconciliation…</div>;
  }

  const r = data.reconciliation;
  const j = data.related_journal;
  const linkedCase = data.linked_case;
  const wf = r.workflow_status || r.status || "open";
  const isBankType = String(r.reconciliation_type || "")
    .toLowerCase()
    .includes("bank");
  const logs = [...(r.logs || [])].reverse();
  const evidence = r.evidence || [];

  return (
    <PageShell maxWidth="max-w-[960px]">
      <button
        type="button"
        onClick={() => nav(-1)}
        className="mb-2 flex items-center gap-1 text-xs font-mono uppercase tracking-wider text-muted-foreground transition-colors hover:text-foreground"
      >
        <CaretLeft size={12} /> Back
      </button>
      <DrillContextBar
        crumbs={[
          { label: "App", to: "/app" },
          { label: "Reconciliations", to: "/app/financial-audit/reconciliations-dashboard" },
          { label: r.id },
        ]}
      />
      <div data-testid="reconciliation-detail">
        <PageHeader
          kicker="RECONCILIATION"
          title={`${r.reconciliation_type} · ${r.entity}`}
          subtitle={`Period ${r.period} · workflow ${wf}`}
          right={
            <div className="flex flex-wrap gap-2" data-testid="recon-detail-actions">
              {wf === "open" ? (
                <Button
                  type="button"
                  size="sm"
                  disabled={busy}
                  data-testid="recon-action-submit"
                  onClick={() =>
                    runAction("Submitted for approval", () =>
                      http.post(`/reconciliations/${encodeURIComponent(reconciliationId)}/submit`),
                    )
                  }
                >
                  Submit
                </Button>
              ) : null}
              {wf === "submitted" ? (
                <Button
                  type="button"
                  size="sm"
                  disabled={busy}
                  data-testid="recon-action-approve"
                  onClick={() =>
                    runAction("Approved", () =>
                      http.post(`/reconciliations/${encodeURIComponent(reconciliationId)}/approve`),
                    )
                  }
                >
                  Approve
                </Button>
              ) : null}
              {wf !== "open" ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={busy}
                  data-testid="recon-action-reopen"
                  onClick={() =>
                    runAction("Reopened", () =>
                      http.post(`/reconciliations/${encodeURIComponent(reconciliationId)}/reopen`, {
                        reason: reopenReason || "Reopened from workbench",
                      }),
                    )
                  }
                >
                  Reopen
                </Button>
              ) : null}
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={busy}
                data-testid="recon-action-create-case"
                onClick={() =>
                  runAction("Case created", () =>
                    http.post(`/reconciliations/${encodeURIComponent(reconciliationId)}/create-case`, {
                      title: `Reconciliation variance — ${r.id}`,
                    }),
                  )
                }
              >
                Create case
              </Button>
            </div>
          }
        />

        <div className="mb-4 flex flex-wrap gap-2" data-testid="recon-detail-flags">
          <SeverityBadge severity={workflowSeverity(wf)} />
          <span className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">{wf}</span>
          {r.is_overdue ? (
            <span className="crt-num rounded border border-rose-400/60 px-2 py-0.5 text-[10px] uppercase text-rose-700 dark:text-rose-300">
              Overdue
            </span>
          ) : null}
          {r.outside_tolerance ? (
            <span className="crt-num rounded border border-amber-400/60 px-2 py-0.5 text-[10px] uppercase text-amber-800 dark:text-amber-200">
              Outside tolerance
            </span>
          ) : null}
          <span className="crt-num text-[10px] uppercase text-muted-foreground">
            Evidence {r.evidence_count ?? evidence.length}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
          <SectionCard kicker="POSITION" title="Balances" bodyClassName="p-4 space-y-2 font-mono text-xs text-[#A3A3A3]">
            <div className="flex justify-between text-foreground">
              <span>Variance</span>
              <span className={clsx("tabular-nums", r.outside_tolerance && "text-rose-600 dark:text-rose-400")}>
                {fmtUSD(r.variance_amount)}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Tolerance</span>
              <span className="tabular-nums">{fmtUSD(r.tolerance)}</span>
            </div>
            <div className="flex justify-between">
              <span>Due</span>
              <span>{r.due_date ? fmtDate(r.due_date) : "—"}</span>
            </div>
          </SectionCard>

          <SectionCard kicker="DRILL" title="Related activity" bodyClassName="p-4 space-y-3">
            {j ? (
              <Link
                to={`/app/drill/journal/${encodeURIComponent(j.id)}`}
                className="block rounded-xl border border-zinc-200 bg-zinc-50/80 p-3 transition-colors hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900/40 dark:hover:bg-zinc-900/70"
                data-testid="recon-related-journal"
              >
                <div className="font-mono text-[10px] uppercase text-muted-foreground">Sample journal (same entity)</div>
                <div className="mt-1 text-sm text-foreground">{j.journal_number || j.id}</div>
                <div className="mt-1 font-mono text-[10px] text-primary">Open journal drill →</div>
              </Link>
            ) : (
              <div className="text-xs text-[#737373]">No linked journal sample for this entity.</div>
            )}
            {linkedCase ? (
              <Link
                to={`/app/cases/${encodeURIComponent(linkedCase.id)}`}
                className="block rounded-xl border border-amber-200 bg-amber-50/80 p-3 transition-colors hover:bg-amber-100 dark:border-amber-900/50 dark:bg-amber-950/40 dark:hover:bg-amber-950/70"
                data-testid="recon-linked-case"
              >
                <div className="font-mono text-[10px] uppercase text-muted-foreground">Linked case</div>
                <div className="mt-1 text-sm text-foreground">{linkedCase.title || linkedCase.id}</div>
                <div className="crt-num mt-1 text-[10px] uppercase text-muted-foreground">
                  {linkedCase.status} · {fmtUSD(linkedCase.financial_exposure)}
                </div>
                <div className="mt-1 font-mono text-[10px] text-primary">Open case →</div>
              </Link>
            ) : null}
            {isBankType ? (
              <Link
                to="/app/financial-audit/bank-reconciliation-dashboard"
                className="inline-block text-xs font-mono uppercase text-[#0A84FF] hover:underline"
                data-testid="recon-bank-recon-link"
              >
                Bank reconciliation workbench (Phase 18) →
              </Link>
            ) : null}
            <Link to="/app/rollups" className="inline-block text-xs font-mono uppercase text-[#0A84FF] hover:underline">
              Entity rollups →
            </Link>
          </SectionCard>
        </div>

        <SectionCard kicker="EVIDENCE" title="Supporting evidence" className="mt-6">
          <div className="space-y-3 p-4" data-testid="recon-evidence-panel">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
              <div className="flex-1 space-y-1">
                <label className="crt-num text-[10px] uppercase text-muted-foreground" htmlFor="recon-ev-url">
                  URL
                </label>
                <Input
                  id="recon-ev-url"
                  value={evUrl}
                  onChange={(e) => setEvUrl(e.target.value)}
                  placeholder="https://…"
                  data-testid="recon-evidence-url"
                />
              </div>
              <div className="flex-1 space-y-1">
                <label className="crt-num text-[10px] uppercase text-muted-foreground" htmlFor="recon-ev-notes">
                  Notes
                </label>
                <Input
                  id="recon-ev-notes"
                  value={evNotes}
                  onChange={(e) => setEvNotes(e.target.value)}
                  placeholder="Workpaper reference"
                  data-testid="recon-evidence-notes"
                />
              </div>
              <Button
                type="button"
                size="sm"
                disabled={busy || !evUrl.trim()}
                data-testid="recon-action-add-evidence"
                onClick={() =>
                  runAction("Evidence added", () =>
                    http.post(`/reconciliations/${encodeURIComponent(reconciliationId)}/evidence`, {
                      type: "link",
                      url: evUrl.trim(),
                      notes: evNotes.trim() || undefined,
                    }),
                  ).then(() => {
                    setEvUrl("");
                    setEvNotes("");
                  })
                }
              >
                Add evidence
              </Button>
            </div>
            {evidence.length === 0 ? (
              <p className="text-xs text-muted-foreground">No evidence attached yet.</p>
            ) : (
              <ul className="space-y-2">
                {evidence.map((ev) => (
                  <li
                    key={ev.id}
                    className="rounded-lg border border-zinc-200 px-3 py-2 text-xs dark:border-zinc-700"
                    data-testid={`recon-evidence-${ev.id}`}
                  >
                    <div className="font-mono text-[10px] uppercase text-muted-foreground">{ev.type || "link"}</div>
                    {ev.url ? (
                      <a href={ev.url} target="_blank" rel="noreferrer" className="mt-1 block text-primary hover:underline">
                        {ev.url}
                      </a>
                    ) : null}
                    {ev.notes ? <p className="mt-1 text-muted-foreground">{ev.notes}</p> : null}
                    <p className="crt-num mt-1 text-[10px] text-muted-foreground">
                      {ev.by || "—"} · {ev.at ? fmtDate(ev.at) : "—"}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </SectionCard>

        {wf !== "open" ? (
          <SectionCard kicker="REOPEN" title="Reopen reason" className="mt-4">
            <div className="p-4">
              <Input
                value={reopenReason}
                onChange={(e) => setReopenReason(e.target.value)}
                placeholder="Optional reason for reopen"
                data-testid="recon-reopen-reason"
              />
            </div>
          </SectionCard>
        ) : null}

        <SectionCard kicker="ACTIVITY" title="Workflow log" className="mt-6">
          <div className="p-4" data-testid="recon-activity-log">
            {logs.length === 0 ? (
              <p className="text-xs text-muted-foreground">No workflow events yet — submit to start the trail.</p>
            ) : (
              <ul className="space-y-2 font-mono text-xs">
                {logs.map((log, i) => (
                  <li key={`${log.at}-${log.action}-${i}`} className="flex justify-between gap-4 border-b border-zinc-100 py-2 dark:border-zinc-800">
                    <span className="uppercase text-foreground">{log.action}</span>
                    <span className="crt-num shrink-0 text-muted-foreground">
                      {log.by || "—"} · {log.at ? fmtDate(log.at) : "—"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </SectionCard>
      </div>
    </PageShell>
  );
}
