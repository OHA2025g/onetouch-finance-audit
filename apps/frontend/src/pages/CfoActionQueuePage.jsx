import React, { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowsClockwise, ArrowRight, Download } from "@phosphor-icons/react";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { useActionQueue } from "../lib/useActionQueue";
import {
  ActionQueueCharts,
  ActionQueueKpiStrip,
  ActionQueueOpsScorecard,
} from "../components/ActionQueueAnalytics";
import { ActionQueueVirtualList } from "../components/ActionQueueVirtualList";
import { ActionQueueTypeIcon } from "../lib/actionQueueTypeIcon";
import { SeverityBadge } from "../components/Badges";
import { fmtUSD } from "../lib/format";

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "open", label: "Open" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "escalated", label: "Escalated" },
];

const PRIORITY_OPTIONS = [
  { value: "", label: "All priorities" },
  { value: "P0", label: "P0" },
  { value: "P1", label: "P1" },
  { value: "P2", label: "P2" },
];

const TYPE_OPTIONS = [
  { value: "", label: "All types" },
  { value: "case_overdue", label: "Case overdue" },
  { value: "exception_highrisk", label: "High-risk exception" },
  { value: "approval_pending", label: "Approval pending" },
  { value: "connector_failed", label: "Connector failed" },
  { value: "close_critical_task", label: "Close critical" },
  { value: "reconciliation_overdue", label: "Recon overdue" },
  { value: "bank_signoff_pending", label: "Bank sign-off" },
  { value: "journal_approval_backlog", label: "Journal backlog" },
  { value: "three_way_match_failure", label: "3-way match" },
  { value: "sod_violation", label: "SoD violation" },
  { value: "policy_exception", label: "Policy breach" },
  { value: "treasury_alert", label: "Treasury alert" },
];

const PROCESS_OPTIONS = [
  { value: "", label: "All processes" },
  { value: "Procure-to-Pay", label: "Procure-to-Pay" },
  { value: "Record-to-Report", label: "Record-to-Report" },
  { value: "Access/SoD", label: "Access/SoD" },
  { value: "Treasury", label: "Treasury" },
  { value: "Policy compliance", label: "Policy compliance" },
];

const SORT_OPTIONS = [
  { value: "score", label: "Sort: priority score" },
  { value: "materiality", label: "Sort: materiality" },
  { value: "exposure", label: "Sort: exposure" },
  { value: "age", label: "Sort: age (oldest)" },
];

const REJECT_REASONS = [
  { value: "duplicate", label: "Duplicate" },
  { value: "not_material", label: "Not material" },
  { value: "deferred", label: "Deferred" },
  { value: "other", label: "Other" },
];

function detailExposure(detail) {
  const v = detail?.exposure ?? detail?.financial_exposure;
  return v != null && v !== "" ? fmtUSD(v) : "—";
}

export default function CfoActionQueuePage() {
  const nav = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { entityCode, hrefWithMasterParams } = useMastersFilters();
  const dashboardParams = useDashboardFilterParams();
  const [status, setStatus] = useState("open");
  const [priority, setPriority] = useState(searchParams.get("priority") || "");
  const [actionType, setActionType] = useState(searchParams.get("action_type") || "");
  const [processFilter, setProcessFilter] = useState("");
  const [sort, setSort] = useState("score");
  const [myQueue, setMyQueue] = useState(false);
  const [selected, setSelected] = useState(new Set());
  const [rejectReason, setRejectReason] = useState("not_material");

  const {
    queue,
    dashboard,
    detail,
    setDetail,
    loading,
    refreshing,
    loadingMore,
    loadDashboard,
    loadList,
    loadDetail,
    actOnItem,
    bulkAct,
    exportCsv,
    exportXlsx,
  } = useActionQueue(dashboardParams);

  const listFilters = useCallback(() => {
    let assignee;
    if (myQueue) {
      try {
        const raw = localStorage.getItem("ota_user");
        const u = raw ? JSON.parse(raw) : null;
        assignee = u?.email;
      } catch {
        assignee = undefined;
      }
    }
    return {
      status: status || undefined,
      priority: priority || undefined,
      action_type: actionType || undefined,
      process: processFilter || undefined,
      sort,
      assignee_email: assignee,
    };
  }, [status, priority, actionType, processFilter, sort, myQueue]);

  const refreshAll = useCallback(async () => {
    try {
      await loadDashboard();
      await loadList({ refresh: true, ...listFilters() });
      toast.success("Action queue refreshed");
    } catch {
      toast.error("Refresh failed");
    }
  }, [loadDashboard, loadList, listFilters]);

  useEffect(() => {
    refreshAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dashboardParams]);

  useEffect(() => {
    setDetail(null);
    loadList({ refresh: false, ...listFilters() }).catch(() => toast.error("Failed to load list"));
  }, [status, priority, actionType, processFilter, sort, myQueue, loadList, listFilters, setDetail]);

  useEffect(() => {
    const next = new URLSearchParams();
    if (priority) next.set("priority", priority);
    if (actionType) next.set("action_type", actionType);
    const aid = searchParams.get("action_id");
    if (aid) next.set("action_id", aid);
    setSearchParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [priority, actionType]);

  const deepActionId = searchParams.get("action_id");
  useEffect(() => {
    if (!deepActionId) return;
    loadDetail(deepActionId).catch(() => {});
  }, [deepActionId, loadDetail]);

  const loadMore = useCallback(() => {
    if (!queue?.has_more || !queue?.next_cursor || loadingMore) return;
    loadList({ append: true, cursor: queue.next_cursor, ...listFilters() }).catch(() =>
      toast.error("Failed to load more"),
    );
  }, [queue?.has_more, queue?.next_cursor, loadingMore, loadList, listFilters]);

  const toggleSelect = (id) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const backHref = hrefWithMasterParams("/app/cfo");
  const items = queue?.items || [];
  const summary = dashboard?.summary;

  return (
    <PageShell maxWidth="w-full max-w-none">
      <div data-testid="cfo-action-queue-page">
        <PageHeader
          kicker="CFO COMMAND CENTER"
          title="CFO action queue"
          subtitle={`Prioritized decisions · ${entityCode || "all entities"}`}
          right={
            <Link
              to={backHref}
              className="crt-num inline-flex items-center gap-1 text-[10px] uppercase tracking-wider text-primary hover:underline"
              data-testid="cfo-action-queue-back-cfo"
            >
              <ArrowRight size={14} className="rotate-180" aria-hidden /> CFO cockpit
            </Link>
          }
        />

        <MastersFilterStrip className="mb-4" />

        <ActionQueueKpiStrip summary={summary} />
        <ActionQueueOpsScorecard linkage={dashboard?.ops_linkage} />

        <div className="mb-4 flex flex-wrap items-center gap-2">
          <select
            data-testid="cfo-action-queue-status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="crt-num rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-xs dark:border-zinc-600 dark:bg-zinc-950"
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value || "all"} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value)}
            className="crt-num rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-xs dark:border-zinc-600 dark:bg-zinc-950"
          >
            {PRIORITY_OPTIONS.map((o) => (
              <option key={o.value || "all"} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <select
            data-testid="cfo-action-queue-type"
            value={actionType}
            onChange={(e) => setActionType(e.target.value)}
            className="crt-num rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-xs dark:border-zinc-600 dark:bg-zinc-950"
          >
            {TYPE_OPTIONS.map((o) => (
              <option key={o.value || "all-types"} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <select
            data-testid="cfo-action-queue-process"
            value={processFilter}
            onChange={(e) => setProcessFilter(e.target.value)}
            className="crt-num rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-xs dark:border-zinc-600 dark:bg-zinc-950"
          >
            {PROCESS_OPTIONS.map((o) => (
              <option key={o.value || "all-proc"} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <select
            data-testid="cfo-action-queue-sort"
            value={sort}
            onChange={(e) => setSort(e.target.value)}
            className="crt-num rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-xs dark:border-zinc-600 dark:bg-zinc-950"
          >
            {SORT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <label className="crt-num flex items-center gap-1 text-[10px] uppercase tracking-wider text-muted-foreground">
            <input type="checkbox" checked={myQueue} onChange={(e) => setMyQueue(e.target.checked)} />
            My queue
          </label>
          <button
            type="button"
            data-testid="cfo-action-queue-refresh"
            disabled={refreshing || loading}
            onClick={refreshAll}
            className="crt-num inline-flex items-center gap-1 rounded-md border border-zinc-300 px-2 py-1.5 text-[10px] uppercase tracking-wider disabled:opacity-50"
          >
            <ArrowsClockwise size={14} className={refreshing ? "animate-spin" : ""} />
            Refresh
          </button>
          <button
            type="button"
            onClick={() => exportCsv().catch(() => toast.error("Export failed"))}
            className="crt-num inline-flex items-center gap-1 rounded-md border border-zinc-300 px-2 py-1.5 text-[10px] uppercase tracking-wider"
          >
            <Download size={14} /> CSV
          </button>
          <button
            type="button"
            data-testid="cfo-action-queue-export-xlsx"
            onClick={() => exportXlsx().catch(() => toast.error("XLSX export failed"))}
            className="crt-num inline-flex items-center gap-1 rounded-md border border-zinc-300 px-2 py-1.5 text-[10px] uppercase tracking-wider"
          >
            <Download size={14} /> XLSX
          </button>
          {selected.size > 0 ? (
            <>
              <button
                type="button"
                className="crt-num rounded-sm border border-primary bg-primary px-2 py-1 text-[9px] uppercase text-white"
                onClick={async () => {
                  await bulkAct([...selected], "approve", "Bulk approved");
                  toast.success("Bulk approve complete");
                  setSelected(new Set());
                  await refreshAll();
                }}
              >
                Bulk approve ({selected.size})
              </button>
              <button
                type="button"
                className="crt-num rounded-sm border px-2 py-1 text-[9px] uppercase"
                onClick={async () => {
                  await bulkAct([...selected], "escalate", "Bulk escalated");
                  toast.success("Bulk escalate complete");
                  setSelected(new Set());
                  await refreshAll();
                }}
              >
                Bulk escalate
              </button>
              <button
                type="button"
                data-testid="cfo-action-queue-bulk-reject"
                className="crt-num rounded-sm border border-red-500/40 px-2 py-1 text-[9px] uppercase text-red-700 dark:text-red-300"
                onClick={async () => {
                  await bulkAct([...selected], "reject", "Bulk rejected", rejectReason);
                  toast.success("Bulk reject complete");
                  setSelected(new Set());
                  await refreshAll();
                }}
              >
                Bulk reject ({selected.size})
              </button>
            </>
          ) : null}
          {typeof queue?.total === "number" ? (
            <span className="crt-num text-[10px] uppercase text-muted-foreground">{queue.total} listed</span>
          ) : null}
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
          <SectionCard className="lg:col-span-2" kicker="QUEUE" title="Items" bodyClassName="p-0">
            {loading || refreshing ? (
              <div className="p-4 text-sm text-muted-foreground" data-testid="cfo-action-queue-list-loading">
                Loading…
              </div>
            ) : !items.length ? (
              <div className="p-4 text-sm text-muted-foreground">No items for this filter.</div>
            ) : (
              <ActionQueueVirtualList
                items={items}
                hasMore={Boolean(queue?.has_more)}
                onEndReached={loadMore}
                renderRow={(it) => (
                  <div className="flex items-start gap-2 border-b border-zinc-200 dark:border-zinc-800">
                    <input
                      type="checkbox"
                      className="mt-3 ml-2"
                      checked={selected.has(it.id)}
                      onChange={() => toggleSelect(it.id)}
                    />
                    <button
                      type="button"
                      data-testid={`cfo-aq-row-${it.id}`}
                      onClick={() => loadDetail(it.id).catch(() => toast.error("Detail failed"))}
                      className="flex flex-1 items-start gap-2 px-2 py-3 text-left hover:bg-zinc-50 dark:hover:bg-zinc-900/60"
                    >
                      <ActionQueueTypeIcon type={it.type} className="mt-0.5 shrink-0 text-primary" />
                      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                        <span className="flex w-full items-center gap-2">
                          <span className="flex-1 truncate text-sm font-medium text-foreground">{it.title}</span>
                          {it.sla_breached ? (
                            <span
                              className="crt-num shrink-0 rounded border border-red-500/50 bg-red-500/10 px-1.5 py-0.5 text-[9px] uppercase tracking-wider text-red-700 dark:text-red-300"
                              data-testid={`cfo-aq-sla-${it.id}`}
                            >
                              SLA
                            </span>
                          ) : null}
                        </span>
                        <span className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">
                          {it.status} · {it.priority} · {it.type?.replaceAll("_", " ")}
                          {it.age_days != null ? ` · ${it.age_days}d` : ""}
                          {it.process ? ` · ${it.process}` : ""}
                        </span>
                      </span>
                    </button>
                  </div>
                )}
              />
            )}
            {loadingMore ? (
              <p className="crt-num border-t px-3 py-2 text-[10px] uppercase text-muted-foreground">Loading more…</p>
            ) : null}
          </SectionCard>

          <SectionCard className="lg:col-span-3" kicker="DETAIL" title="Selected action" bodyClassName="p-0">
            {!detail ? (
              <div className="p-4 text-sm text-muted-foreground">Select an item to view detail and act.</div>
            ) : (
              <div className="space-y-4 p-4">
                <div>
                  <div className="font-display text-base font-semibold text-foreground">{detail.title}</div>
                  <div className="crt-num mt-1 text-[10px] uppercase tracking-wider text-muted-foreground">
                    {detail.id} · {detail.status} · score {detail.materiality_score ?? "—"}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
                  <div>
                    <span className="text-muted-foreground">Entity</span>
                    <p className="font-medium">{detail.entity || detail.detail?.entity || "—"}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Process</span>
                    <p className="font-medium">{detail.process || detail.detail?.process || "—"}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Exposure</span>
                    <p className="font-medium">{detailExposure(detail.detail)}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Age</span>
                    <p className="font-medium">{detail.age_days != null ? `${detail.age_days}d` : "—"}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Severity</span>
                    <p className="mt-0.5">
                      {detail.detail?.severity ? <SeverityBadge severity={detail.detail.severity} /> : "—"}
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Due</span>
                    <p className="font-medium">{detail.detail?.due_date || "—"}</p>
                  </div>
                </div>

                {detail.drill?.route ? (
                  <button
                    type="button"
                    data-testid="cfo-aq-detail-open-drill"
                    onClick={() => nav(hrefWithMasterParams(detail.drill.route))}
                    className="crt-num rounded-sm border px-2 py-1 text-[9px] uppercase tracking-wider"
                  >
                    Open linked surface
                  </button>
                ) : null}

                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    data-testid="cfo-aq-approve"
                    disabled={detail.status === "approved" || detail.status === "rejected"}
                    onClick={async () => {
                      try {
                        await actOnItem(detail.id, "approve", "Approved from action queue");
                        toast.success("Approved");
                        await refreshAll();
                        await loadDetail(detail.id);
                      } catch (e) {
                        toast.error(e?.response?.data?.detail || "Approve failed");
                      }
                    }}
                    className="crt-num rounded-sm border border-primary bg-primary px-3 py-1 text-[9px] uppercase text-white disabled:opacity-40"
                  >
                    Approve
                  </button>
                  <button
                    type="button"
                    data-testid="cfo-aq-reject"
                    disabled={detail.status === "approved" || detail.status === "rejected"}
                    onClick={async () => {
                      try {
                        await actOnItem(detail.id, "reject", "Rejected from action queue", rejectReason);
                        toast.success("Rejected");
                        await refreshAll();
                        await loadDetail(detail.id);
                      } catch (e) {
                        toast.error(e?.response?.data?.detail || "Reject failed");
                      }
                    }}
                    className="crt-num rounded-sm border px-3 py-1 text-[9px] uppercase disabled:opacity-40"
                  >
                    Reject
                  </button>
                  <button
                    type="button"
                    data-testid="cfo-aq-escalate"
                    disabled={detail.status !== "open"}
                    onClick={async () => {
                      try {
                        await actOnItem(detail.id, "escalate", "Escalated from action queue");
                        toast.success("Escalated");
                        await refreshAll();
                        await loadDetail(detail.id);
                      } catch (e) {
                        toast.error(e?.response?.data?.detail || "Escalate failed");
                      }
                    }}
                    className="crt-num rounded-sm border px-3 py-1 text-[9px] uppercase disabled:opacity-40"
                  >
                    Escalate
                  </button>
                  <button
                    type="button"
                    data-testid="cfo-aq-reopen"
                    disabled={detail.status === "open"}
                    onClick={async () => {
                      try {
                        await actOnItem(detail.id, "reopen", "Reopened from action queue");
                        toast.success("Reopened");
                        await refreshAll();
                        await loadDetail(detail.id);
                      } catch (e) {
                        toast.error(e?.response?.data?.detail || "Reopen failed");
                      }
                    }}
                    className="crt-num rounded-sm border px-3 py-1 text-[9px] uppercase disabled:opacity-40"
                  >
                    Reopen
                  </button>
                  <select
                    value={rejectReason}
                    onChange={(e) => setRejectReason(e.target.value)}
                    className="crt-num rounded-sm border px-2 py-1 text-[9px] uppercase"
                    aria-label="Reject reason"
                  >
                    {REJECT_REASONS.map((r) => (
                      <option key={r.value} value={r.value}>
                        {r.label}
                      </option>
                    ))}
                  </select>
                </div>

                {Array.isArray(detail.comments) && detail.comments.length ? (
                  <div>
                    <div className="crt-num mb-2 text-[10px] uppercase text-muted-foreground">Comments</div>
                    <ul className="space-y-2 text-sm text-muted-foreground">
                      {detail.comments.map((c, i) => (
                        <li key={`${detail.id}-c-${i}`} className="border-l-2 border-primary/30 pl-2">
                          {typeof c === "string" ? c : c?.text || JSON.stringify(c)}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            )}
          </SectionCard>
        </div>

        <ActionQueueCharts dashboard={dashboard} />
      </div>
    </PageShell>
  );
}
