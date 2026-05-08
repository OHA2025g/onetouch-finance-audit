import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowsClockwise, ArrowRight } from "@phosphor-icons/react";
import { toast } from "sonner";
import { http } from "../lib/api";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { buildDashboardFilterParams } from "../lib/mastersDashboardParams";

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "open", label: "Open" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "escalated", label: "Escalated" },
];

export default function CfoActionQueuePage() {
  const nav = useNavigate();
  const { entityCode, periodYm, periodExplicit, departmentId, costCenterId, hrefWithMasterParams } = useMastersFilters();
  const [queue, setQueue] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [status, setStatus] = useState("");

  const dashboardParams = useMemo(
    () =>
      buildDashboardFilterParams({
        entityCode,
        periodYm,
        periodExplicit,
        departmentId,
        costCenterId,
      }),
    [entityCode, periodYm, periodExplicit, departmentId, costCenterId],
  );

  const loadList = useCallback(
    async (opts = { refresh: false }) => {
      const { refresh } = opts;
      if (refresh) setRefreshing(true);
      else setLoading(true);
      try {
        const params = {
          ...dashboardParams,
          refresh,
          limit: 100,
          offset: 0,
          ...(status ? { status } : {}),
        };
        const { data } = await http.get("/cfo/action-queue", { params });
        setQueue(data);
      } catch {
        toast.error("Failed to load action queue");
        setQueue(null);
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [dashboardParams, status],
  );

  useEffect(() => {
    setDetail(null);
  }, [status]);

  useEffect(() => {
    loadList({ refresh: true });
  }, [loadList]);

  const selectItem = async (id) => {
    try {
      const { data } = await http.get(`/cfo/action-queue/${encodeURIComponent(id)}`);
      setDetail(data);
    } catch {
      toast.error("Failed to load action detail");
      setDetail(null);
    }
  };

  const backHref = hrefWithMasterParams("/app/cfo");

  return (
    <PageShell maxWidth="max-w-[1100px]">
      <div data-testid="cfo-action-queue-page">
        <PageHeader
          kicker="CFO COMMAND CENTER"
          title="CFO action queue"
          subtitle={`Materialized items across cases and exceptions · context: ${entityCode || "all entities"}`}
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

        <div className="mb-4 flex flex-wrap items-center gap-3">
          <label htmlFor="aq-status-filter" className="sr-only">
            Status filter
          </label>
          <select
            id="aq-status-filter"
            data-testid="cfo-action-queue-status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="crt-num rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-xs text-foreground dark:border-zinc-600 dark:bg-zinc-950"
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value || "all"} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            data-testid="cfo-action-queue-refresh"
            disabled={refreshing || loading}
            onClick={() => loadList({ refresh: true })}
            className="crt-num inline-flex items-center gap-1 rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-[10px] uppercase tracking-wider text-muted-foreground hover:bg-zinc-50 hover:text-foreground disabled:opacity-50 dark:border-zinc-600 dark:bg-zinc-900 dark:hover:bg-zinc-800"
          >
            <ArrowsClockwise size={14} className={refreshing ? "animate-spin" : ""} aria-hidden />
            Refresh
          </button>
          {typeof queue?.total === "number" ? (
            <span className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">
              {queue.total} total
            </span>
          ) : null}
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
          <SectionCard
            className="lg:col-span-2"
            kicker="QUEUE"
            title="Items"
            bodyClassName="p-0"
          >
            {loading || refreshing ? (
              <div className="p-4 text-sm text-muted-foreground" data-testid="cfo-action-queue-list-loading">
                Loading…
              </div>
            ) : !queue?.items?.length ? (
              <div className="p-4 text-sm text-muted-foreground">No items for this filter.</div>
            ) : (
              <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">
                {queue.items.map((it) => (
                  <li key={it.id}>
                    <button
                      type="button"
                      data-testid={`cfo-aq-row-${it.id}`}
                      onClick={() => selectItem(it.id)}
                      className="flex w-full flex-col items-start gap-0.5 px-4 py-3 text-left hover:bg-zinc-50 dark:hover:bg-zinc-900/60"
                    >
                      <span className="text-sm font-medium text-foreground">{it.title}</span>
                      <span className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">
                        {it.status} · {it.priority} · {it.type?.replaceAll("_", " ")}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>

          <SectionCard className="lg:col-span-3" kicker="DETAIL" title="Selected action" bodyClassName="p-0">
            {!detail ? (
              <div className="p-4 text-sm text-muted-foreground">Select an item to view detail and act.</div>
            ) : (
              <div className="space-y-4 p-4">
                <div>
                  <div className="font-display text-base font-semibold text-foreground">{detail.title}</div>
                  <div className="crt-num mt-1 text-[10px] uppercase tracking-wider text-muted-foreground">
                    {detail.id} · {detail.status}
                  </div>
                </div>
                {detail.drill?.route ? (
                  <button
                    type="button"
                    data-testid="cfo-aq-detail-open-drill"
                    onClick={() => nav(hrefWithMasterParams(detail.drill.route))}
                    className="crt-num rounded-sm border border-zinc-300 bg-white px-2 py-1 text-[9px] uppercase tracking-wider text-muted-foreground hover:bg-zinc-50 hover:text-foreground dark:border-zinc-600 dark:bg-zinc-900 dark:hover:bg-zinc-800"
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
                        await http.post(`/cfo/action/${detail.id}/approve`, { note: "Approved from action queue page" });
                        toast.success("Approved");
                        await loadList({ refresh: true });
                        const { data } = await http.get(`/cfo/action-queue/${encodeURIComponent(detail.id)}`);
                        setDetail(data);
                      } catch (e) {
                        toast.error(e?.response?.data?.detail || "Approve failed");
                      }
                    }}
                    className="crt-num rounded-sm border border-primary bg-primary px-3 py-1 text-[9px] uppercase tracking-wider text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    Approve
                  </button>
                  <button
                    type="button"
                    data-testid="cfo-aq-escalate"
                    disabled={detail.status !== "open"}
                    onClick={async () => {
                      try {
                        await http.post(`/cfo/action/${detail.id}/escalate`, { note: "Escalated from action queue page" });
                        toast.success("Escalated");
                        await loadList({ refresh: true });
                        const { data } = await http.get(`/cfo/action-queue/${encodeURIComponent(detail.id)}`);
                        setDetail(data);
                      } catch (e) {
                        toast.error(e?.response?.data?.detail || "Escalate failed");
                      }
                    }}
                    className="crt-num rounded-sm border border-zinc-300 bg-white px-3 py-1 text-[9px] uppercase tracking-wider text-muted-foreground hover:bg-zinc-50 hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40 dark:border-zinc-600 dark:bg-zinc-900 dark:hover:bg-zinc-800"
                  >
                    Escalate
                  </button>
                </div>
                {Array.isArray(detail.comments) && detail.comments.length ? (
                  <div>
                    <div className="crt-num mb-2 text-[10px] uppercase tracking-wider text-muted-foreground">
                      Comments
                    </div>
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
      </div>
    </PageShell>
  );
}
