import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { useDashboardFilterParams } from "../lib/useDashboardFilterParams";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { StatCard } from "../components/StatCard";
import { useAuth } from "../lib/auth";
import { fmtDateTime } from "../lib/format";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "../components/ui/sheet";

const PENDING = new Set(["draft", "reopened", "submitted"]);

function categoryDrillHref(category, hrefWithMasterParams) {
  if (!category) return null;
  const n = String(category).trim().toLowerCase();
  if (n.includes("treasury")) return hrefWithMasterParams("/app/treasury");
  if (n.includes("working capital")) return hrefWithMasterParams("/app/working-capital");
  if (n.includes("revenue")) return hrefWithMasterParams("/app/continuous-audit/o2c-audit-dashboard");
  if (n === "r2r" || n.includes("r2r")) return hrefWithMasterParams("/app/controller");
  if (n.includes("tax")) return hrefWithMasterParams("/app/compliance");
  return null;
}

function ownerKey(task) {
  const o = task?.owner_email;
  return o && String(o).trim() ? String(o).trim() : "unassigned";
}

function formatEventDetail(ev) {
  const d = ev?.detail;
  if (!d || typeof d !== "object") return "—";
  const tid = d.task_id;
  if (ev.type?.startsWith("task_") && tid) return `Task ${tid}`;
  if (ev.type === "evidence_added" && tid) return `Evidence on task ${tid}`;
  if (ev.type === "cycle_signed_off") return d.override ? "CFO override sign-off" : "Cycle signed off";
  if (ev.type === "cycle_created" && d.backfilled) return "Cycle opened (historical)";
  try {
    return JSON.stringify(d);
  } catch {
    return "—";
  }
}

export default function MonthEndClosePage() {
  const { cycleId } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const { hrefWithMasterParams, periodYm } = useMastersFilters();
  const [cycles, setCycles] = useState([]);
  const [cycle, setCycle] = useState(null);
  const [creating, setCreating] = useState(false);
  const [signingOff, setSigningOff] = useState(false);
  const [closeMetrics, setCloseMetrics] = useState(null);
  const [overrideReason, setOverrideReason] = useState("");
  const [showOverride, setShowOverride] = useState(false);
  const [tableFilter, setTableFilter] = useState({ kind: "all", owner: null });
  const [selectedTaskId, setSelectedTaskId] = useState(null);
  const [closeEvents, setCloseEvents] = useState([]);
  const [eventsLoading, setEventsLoading] = useState(false);
  const [eventsError, setEventsError] = useState(null);
  const [draftOwner, setDraftOwner] = useState("");
  const [draftDue, setDraftDue] = useState("");
  const [savingTask, setSavingTask] = useState(false);

  const canSignOff = ["CFO", "Super Admin"].includes(user?.role);

  const scopeParams = useDashboardFilterParams();

  const loadCycles = useCallback(
    () =>
      http
        .get("/close/cycles")
        .then((r) => setCycles(r.data || []))
        .catch(() => toast.error("Failed to load close cycles")),
    [],
  );

  const loadCycle = useCallback((id) => {
    if (!id) return Promise.resolve();
    return http
      .get(`/close/cycles/${id}`)
      .then((r) => setCycle(r.data))
      .catch(() => toast.error("Failed to load close cycle"));
  }, []);

  const loadEvents = useCallback((id) => {
    if (!id) {
      setCloseEvents([]);
      setEventsLoading(false);
      setEventsError(null);
      return Promise.resolve();
    }
    setEventsLoading(true);
    setEventsError(null);
    return http
      .get(`/close/cycles/${id}/events`)
      .then((r) => {
        const rows = Array.isArray(r.data) ? r.data : [];
        setCloseEvents(rows);
        setEventsError(null);
      })
      .catch((e) => {
        setCloseEvents([]);
        setEventsError(e?.response?.data?.detail || "Failed to load close activity");
        toast.error("Failed to load close activity timeline");
      })
      .finally(() => setEventsLoading(false));
  }, []);

  useEffect(() => {
    loadCycles();
  }, [loadCycles]);

  useEffect(() => {
    if (!cycleId) {
      setCycle(null);
      setCloseMetrics(null);
      setShowOverride(false);
      setTableFilter({ kind: "all", owner: null });
      setSelectedTaskId(null);
      setCloseEvents([]);
      setEventsLoading(false);
      setEventsError(null);
      return;
    }
    setTableFilter({ kind: "all", owner: null });
    setSelectedTaskId(null);
    loadCycle(cycleId);
    loadEvents(cycleId);
  }, [cycleId, loadCycle, loadEvents]);

  useEffect(() => {
    if (!cycleId) return;
    http
      .get("/close/bottlenecks", { params: { cycle_id: cycleId } })
      .then((r) => setCloseMetrics((m) => ({ ...(m || {}), bottlenecks: r.data })))
      .catch(() => {});
    http
      .get("/close/quality-score", { params: { cycle_id: cycleId } })
      .then((r) => setCloseMetrics((m) => ({ ...(m || {}), quality: r.data })))
      .catch(() => {});
  }, [cycleId, cycle?.updated_at]);

  const tasks = useMemo(() => cycle?.tasks ?? [], [cycle]);

  const criticalOpenCount = useMemo(
    () => tasks.filter((t) => t.critical && t.status !== "approved").length,
    [tasks],
  );

  const filteredTasks = useMemo(() => {
    if (tableFilter.kind === "pending") return tasks.filter((t) => PENDING.has(t.status));
    if (tableFilter.kind === "critical_open") return tasks.filter((t) => t.critical && t.status !== "approved");
    if (tableFilter.kind === "owner" && tableFilter.owner != null)
      return tasks.filter((t) => ownerKey(t) === tableFilter.owner);
    return tasks;
  }, [tasks, tableFilter]);

  const selectedTask = useMemo(() => tasks.find((t) => t.id === selectedTaskId) || null, [tasks, selectedTaskId]);

  useEffect(() => {
    if (!selectedTask) return;
    setDraftOwner(selectedTask.owner_email || "");
    setDraftDue(String(selectedTask.due_date || "").slice(0, 10));
  }, [selectedTask, cycle?.updated_at]);

  const saveTaskMeta = async () => {
    if (!selectedTaskId) return;
    setSavingTask(true);
    try {
      const body = {
        owner_email: draftOwner.trim() || null,
        due_date: draftDue.trim() || null,
      };
      await http.patch(`/close/tasks/${selectedTaskId}`, body);
      toast.success("Task updated");
      await loadCycle(cycleId);
      loadEvents(cycleId);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Update failed");
    }
    setSavingTask(false);
  };

  const createCycle = async () => {
    setCreating(true);
    try {
      const target = periodYm;
      const { data } = await http.post("/close/cycles", { period_ym: target, name: `Month-end close ${target}` });
      toast.success("Close cycle created");
      await loadCycles();
      nav(hrefWithMasterParams(`/app/finance-operations/month-end-close/${data.id}`));
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Create cycle failed");
    }
    setCreating(false);
  };

  const approveTask = async (taskId) => {
    try {
      await http.post(`/close/tasks/${taskId}/approve`);
      toast.success("Task approved");
      await loadCycle(cycleId);
      loadEvents(cycleId);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Approve failed");
    }
  };

  const submitTask = async (taskId) => {
    try {
      await http.post(`/close/tasks/${taskId}/submit`);
      toast.success("Task submitted");
      await loadCycle(cycleId);
      loadEvents(cycleId);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Submit failed");
    }
  };

  const reopenTask = async (taskId) => {
    try {
      await http.post(`/close/tasks/${taskId}/reopen`, { note: "Reopened from UI" });
      toast.success("Task reopened");
      await loadCycle(cycleId);
      loadEvents(cycleId);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Reopen failed");
    }
  };

  const addEvidenceLink = async (taskId) => {
    try {
      await http.post(`/close/tasks/${taskId}/evidence`, {
        type: "link",
        uri: `s3://onetouch-evidence/close/${taskId}.pdf`,
        label: "Close evidence link",
      });
      toast.success("Evidence added");
      await loadCycle(cycleId);
      loadEvents(cycleId);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Evidence add failed");
    }
  };

  const signoff = async (override = false) => {
    if (!cycleId) return;
    setSigningOff(true);
    try {
      await http.post("/close/signoff", {
        cycle_id: cycleId,
        ...(override
          ? {
              override: true,
              override_reason: overrideReason.trim() || "Management override",
            }
          : {}),
      });
      toast.success("Cycle signed off");
      setShowOverride(false);
      setOverrideReason("");
      await loadCycle(cycleId);
      loadEvents(cycleId);
    } catch (e) {
      const st = e?.response?.status;
      const detail = e?.response?.data?.detail;
      if (st === 409 && canSignOff && !override) {
        setShowOverride(true);
        toast.error(typeof detail === "string" ? detail : "Sign-off blocked — CFO override available");
      } else {
        toast.error(detail || "Signoff failed");
      }
    }
    setSigningOff(false);
  };

  const reconHealth = cycle?.reconciliation_health;
  const criticalIncomplete = tasks.filter((t) => t.critical && t.status !== "approved").length;

  const quality = closeMetrics?.quality;
  const bn = closeMetrics?.bottlenecks;

  const filterChip = (active, onClick, label, testId) => (
    <button
      type="button"
      data-testid={testId}
      onClick={onClick}
      className={`crt-num rounded-sm border px-3 py-1.5 text-[10px] uppercase tracking-wider transition-colors ${
        active
          ? "border-primary bg-primary text-white"
          : "border-zinc-300 bg-white text-muted-foreground hover:bg-zinc-50 hover:text-foreground dark:border-zinc-600 dark:bg-zinc-900 dark:hover:bg-zinc-800"
      }`}
    >
      {label}
    </button>
  );

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="month-end-close-page">
        <PageHeader
          kicker="FINANCE OPERATIONS"
          title="Month-end close"
          subtitle="Cycles, task drilldown, owner bottlenecks, activity timeline, and CFO sign-off. Use metrics and chips to filter the task grid."
          right={
            <div className="flex flex-wrap items-center gap-2">
              <Link
                to={hrefWithMasterParams("/app/finance-operations/team-performance")}
                className="crt-num rounded-sm border border-zinc-300 bg-white px-3 py-2 text-xs uppercase tracking-wider text-muted-foreground hover:bg-zinc-50 hover:text-foreground dark:border-zinc-600 dark:bg-zinc-900 dark:hover:bg-zinc-800"
              >
                Finance team
              </Link>
              <Link
                to={hrefWithMasterParams("/app/finance-operations")}
                className="crt-num rounded-sm border border-zinc-300 bg-white px-3 py-2 text-xs uppercase tracking-wider text-muted-foreground hover:bg-zinc-50 hover:text-foreground dark:border-zinc-600 dark:bg-zinc-900 dark:hover:bg-zinc-800"
              >
                Finance ops hub
              </Link>
              <button
                type="button"
                onClick={createCycle}
                disabled={creating}
                className="crt-num rounded-sm border border-primary bg-primary px-4 py-2 text-xs uppercase tracking-wider text-white disabled:opacity-50"
                data-testid="close-create-cycle"
              >
                {creating ? "Creating…" : "Create cycle"}
              </button>
            </div>
          }
        />

        <MastersFilterStrip className="mb-4" />
        {Object.keys(scopeParams).length ? (
          <p className="crt-num mb-6 text-[10px] uppercase tracking-wider text-muted-foreground">
            Reporting context: {Object.entries(scopeParams).map(([k, v]) => `${k}=${v}`).join(" · ")}
          </p>
        ) : null}

        {cycleId && quality ? (
          <div className="mb-4 space-y-3" data-testid="close-metrics-row">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
              <button
                type="button"
                className="text-left"
                onClick={() => setTableFilter({ kind: "all", owner: null })}
                data-testid="close-metric-quality"
              >
                <StatCard
                  label="Close quality score"
                  value={quality.score}
                  subtle={`${quality.approved_pct ?? "—"}% approved · ${quality.critical_approved_pct ?? "—"}% critical · ${quality.total_tasks ?? tasks.length} tasks`}
                  testId="close-quality-score"
                />
              </button>
              <button
                type="button"
                className="text-left"
                onClick={() => setTableFilter({ kind: "pending", owner: null })}
                data-testid="close-metric-pending"
              >
                <StatCard
                  label="Pending tasks"
                  value={bn?.pending ?? "—"}
                  subtle="Draft, submitted, or reopened"
                  testId="close-bottlenecks-pending"
                />
              </button>
              <button
                type="button"
                className="text-left"
                onClick={() => setTableFilter({ kind: "critical_open", owner: null })}
                data-testid="close-metric-critical"
              >
                <StatCard
                  label="Critical not approved"
                  value={criticalOpenCount}
                  subtle="Blocks sign-off until cleared or CFO override"
                  testId="close-critical-open"
                />
              </button>
              <StatCard
                label="Cycle"
                value={cycle?.period_ym || cycleId || "—"}
                subtle={cycle?.status || "—"}
                testId="close-cycle-summary"
              />
              {reconHealth ? (
                <Link
                  to={hrefWithMasterParams("/app/financial-audit/reconciliations-dashboard")}
                  className="text-left"
                  data-testid="close-recon-overdue-link"
                >
                  <StatCard
                    label="Reconciliations overdue"
                    value={reconHealth.reconciliations_overdue}
                    unit={`/${reconHealth.reconciliations_total}`}
                    severity="warning"
                    testId="close-recon-overdue"
                  />
                </Link>
              ) : null}
            </div>

            {bn?.top?.length ? (
              <SectionCard kicker="BOTTLENECK" title="Pending work by owner" bodyClassName="p-4">
                <p className="mb-2 text-xs text-muted-foreground">Click a row to filter tasks for that owner (includes unassigned).</p>
                <div className="flex flex-wrap gap-2">
                  {bn.top.map((pair) => {
                    const email = Array.isArray(pair) ? pair[0] : pair;
                    const cnt = Array.isArray(pair) ? pair[1] : "";
                    const active = tableFilter.kind === "owner" && tableFilter.owner === email;
                    const safeTestId = String(email).replace(/[^a-zA-Z0-9_-]/g, "-");
                    return (
                      <button
                        key={email}
                        type="button"
                        data-testid={`close-bottleneck-owner-${safeTestId}`}
                        onClick={() => setTableFilter({ kind: "owner", owner: email })}
                        className={`crt-num rounded-sm border px-3 py-1.5 text-left text-[11px] transition-colors ${
                          active
                            ? "border-primary bg-primary/10 text-foreground"
                            : "border-zinc-200 bg-zinc-50 hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900/50"
                        }`}
                      >
                        <span className="font-mono uppercase text-muted-foreground">{email}</span>
                        <span className="ml-2 font-display text-sm">{cnt}</span>
                      </button>
                    );
                  })}
                </div>
              </SectionCard>
            ) : null}

            <div className="flex flex-wrap items-center gap-2">
              <span className="crt-overline text-muted-foreground">Task filters:</span>
              {filterChip(
                tableFilter.kind === "all",
                () => setTableFilter({ kind: "all", owner: null }),
                "All",
                "close-filter-all",
              )}
              {filterChip(
                tableFilter.kind === "pending",
                () => setTableFilter({ kind: "pending", owner: null }),
                "Pending",
                "close-filter-pending",
              )}
              {filterChip(
                tableFilter.kind === "critical_open",
                () => setTableFilter({ kind: "critical_open", owner: null }),
                "Critical open",
                "close-filter-critical",
              )}
            </div>
          </div>
        ) : null}

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <SectionCard kicker="CYCLES" title="Close cycles" className="lg:col-span-1" bodyClassName="p-0">
            <div className="divide-y divide-zinc-200 dark:divide-zinc-800">
              {cycles.length ? (
                cycles.map((c) => (
                  <Link
                    key={c.id}
                    to={hrefWithMasterParams(`/app/finance-operations/month-end-close/${c.id}`)}
                    className="block px-4 py-3 hover:bg-zinc-50 dark:hover:bg-zinc-900/40"
                    data-testid={`close-cycle-${c.id}`}
                  >
                    <div className="text-sm font-medium text-foreground">{c.name}</div>
                    <div className="crt-num mt-0.5 text-[10px] uppercase tracking-wider text-muted-foreground">
                      {c.period_ym} · {c.status}
                    </div>
                  </Link>
                ))
              ) : (
                <div className="p-4 text-sm text-muted-foreground">No cycles yet. Create one to start.</div>
              )}
            </div>
          </SectionCard>

          <SectionCard
            kicker="TASKS"
            title={cycle ? cycle.name : "Select a cycle"}
            className="lg:col-span-2"
            right={
              cycle && canSignOff ? (
                <div className="flex flex-col items-end gap-2">
                  <button
                    type="button"
                    onClick={() => signoff(false)}
                    disabled={signingOff || cycle.status === "signed_off"}
                    className="crt-num rounded-sm border border-primary bg-primary px-4 py-2 text-xs uppercase tracking-wider text-white disabled:opacity-50"
                    data-testid="close-signoff"
                    title={criticalIncomplete ? "May return 409 until critical tasks approved or override" : "Sign off"}
                  >
                    {cycle.status === "signed_off" ? "Signed off" : signingOff ? "Signing off…" : "Sign off"}
                  </button>
                  {showOverride && cycle.status !== "signed_off" ? (
                    <div className="flex max-w-xs flex-col gap-2 rounded border border-amber-500/40 bg-amber-500/5 p-2">
                      <label className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">
                        Override reason (CFO)
                        <input
                          value={overrideReason}
                          onChange={(ev) => setOverrideReason(ev.target.value)}
                          className="mt-1 w-full rounded border border-zinc-300 bg-white px-2 py-1 text-xs text-foreground dark:border-zinc-600 dark:bg-zinc-900"
                          placeholder="Document why sign-off proceeds early"
                          data-testid="close-signoff-override-reason"
                        />
                      </label>
                      <button
                        type="button"
                        onClick={() => signoff(true)}
                        disabled={signingOff}
                        className="crt-num rounded-sm border border-amber-600 bg-amber-600 px-3 py-1.5 text-[10px] uppercase tracking-wider text-white disabled:opacity-50"
                        data-testid="close-signoff-override"
                      >
                        Override & sign off
                      </button>
                    </div>
                  ) : null}
                </div>
              ) : null
            }
            subtitle={
              cycle
                ? `${filteredTasks.length} shown · ${criticalIncomplete ? `${criticalIncomplete} critical tasks pending approval (sign-off may be blocked).` : "All critical tasks approved — ready for sign-off."}`
                : "Pick a cycle from the left."
            }
            bodyClassName="p-0"
          >
            {cycle ? (
              <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[70vh]" testId="close-tasks-table">
                <DataTableHead>
                  <tr>
                    <DataTableTh>Task</DataTableTh>
                    <DataTableTh>Category</DataTableTh>
                    <DataTableTh>Owner</DataTableTh>
                    <DataTableTh>Critical</DataTableTh>
                    <DataTableTh>Status</DataTableTh>
                    <DataTableTh align="right" className="min-w-[14rem]">
                      Actions
                    </DataTableTh>
                  </tr>
                </DataTableHead>
                <DataTableBody>
                  {filteredTasks.map((t) => {
                    const drill = categoryDrillHref(t.category, hrefWithMasterParams);
                    return (
                      <DataTableRow key={t.id} testId={`close-task-${t.id}`}>
                        <DataTableTd>
                          <div className="text-sm text-foreground">{t.title}</div>
                          <div className="crt-num mt-0.5 text-[10px] uppercase tracking-wider text-muted-foreground">
                            due {String(t.due_date || "").slice(0, 10)}
                          </div>
                        </DataTableTd>
                        <DataTableTd className="text-sm">
                          {drill ? (
                            <Link to={drill} className="text-primary underline-offset-2 hover:underline">
                              {t.category || "—"}
                            </Link>
                          ) : (
                            <span className="text-muted-foreground">{t.category || "—"}</span>
                          )}
                        </DataTableTd>
                        <DataTableTd className="crt-num text-xs text-muted-foreground">{ownerKey(t)}</DataTableTd>
                        <DataTableTd className="crt-num text-xs uppercase">{t.critical ? "yes" : "no"}</DataTableTd>
                        <DataTableTd className="crt-num text-xs uppercase">{t.status}</DataTableTd>
                        <DataTableTd align="right">
                          <div className="flex flex-wrap justify-end gap-2">
                            <button
                              type="button"
                              onClick={() => setSelectedTaskId(t.id)}
                              className="crt-num rounded-sm border border-zinc-300 bg-white px-2 py-1 text-[9px] uppercase tracking-wider text-muted-foreground hover:bg-zinc-50 hover:text-foreground dark:border-zinc-600 dark:bg-zinc-900 dark:hover:bg-zinc-800"
                              data-testid={`close-task-details-${t.id}`}
                            >
                              Details
                            </button>
                            <button
                              type="button"
                              onClick={() => addEvidenceLink(t.id)}
                              className="crt-num rounded-sm border border-zinc-300 bg-white px-2 py-1 text-[9px] uppercase tracking-wider text-muted-foreground hover:bg-zinc-50 hover:text-foreground dark:border-zinc-600 dark:bg-zinc-900 dark:hover:bg-zinc-800"
                              data-testid={`close-add-evidence-${t.id}`}
                            >
                              Evidence
                            </button>
                            <button
                              type="button"
                              onClick={() => submitTask(t.id)}
                              className="crt-num rounded-sm border border-zinc-300 bg-white px-2 py-1 text-[9px] uppercase tracking-wider text-muted-foreground hover:bg-zinc-50 hover:text-foreground dark:border-zinc-600 dark:bg-zinc-900 dark:hover:bg-zinc-800"
                            >
                              Submit
                            </button>
                            <button
                              type="button"
                              onClick={() => approveTask(t.id)}
                              className="crt-num rounded-sm border border-primary bg-primary px-2 py-1 text-[9px] uppercase tracking-wider text-white hover:opacity-90"
                            >
                              Approve
                            </button>
                            <button
                              type="button"
                              onClick={() => reopenTask(t.id)}
                              className="crt-num rounded-sm border border-zinc-300 bg-white px-2 py-1 text-[9px] uppercase tracking-wider text-muted-foreground hover:bg-zinc-50 hover:text-foreground dark:border-zinc-600 dark:bg-zinc-900 dark:hover:bg-zinc-800"
                            >
                              Reopen
                            </button>
                          </div>
                        </DataTableTd>
                      </DataTableRow>
                    );
                  })}
                </DataTableBody>
              </DataTable>
            ) : (
              <div className="p-4 text-sm text-muted-foreground">Select a close cycle to view tasks.</div>
            )}
          </SectionCard>
        </div>

        {cycleId ? (
          <SectionCard
            kicker="ACTIVITY"
            title="Close timeline"
            subtitle="Audit trail for this cycle — task actions, evidence, and sign-off appear here as they occur."
            className="mt-4"
            bodyClassName="p-0 overflow-x-auto"
            data-testid="close-activity-timeline"
          >
            {eventsLoading ? (
              <p className="crt-overline p-4 text-muted-foreground" data-testid="close-activity-loading">
                Loading activity…
              </p>
            ) : eventsError ? (
              <p className="p-4 text-sm text-destructive" data-testid="close-activity-error">
                {typeof eventsError === "string" ? eventsError : "Could not load activity."}
              </p>
            ) : closeEvents.length === 0 ? (
              <p className="p-4 text-sm text-muted-foreground" data-testid="close-activity-empty">
                No activity recorded yet. Submit, approve, or add evidence on tasks to populate the timeline.
              </p>
            ) : (
              <table className="w-full min-w-[640px] text-sm" data-testid="close-activity-table">
                <thead>
                  <tr className="border-b border-zinc-200 text-left font-mono text-[10px] uppercase text-muted-foreground dark:border-zinc-800">
                    <th className="p-3">When</th>
                    <th className="p-3">Type</th>
                    <th className="p-3">Actor</th>
                    <th className="p-3">Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {closeEvents.map((ev) => (
                    <tr key={ev.id} className="border-b border-zinc-100 dark:border-zinc-800/80">
                      <td className="whitespace-nowrap p-3 font-mono text-xs text-muted-foreground">{fmtDateTime(ev.at)}</td>
                      <td className="p-3 font-mono text-xs uppercase">{ev.type?.replace(/_/g, " ") || "—"}</td>
                      <td className="p-3 text-xs">{ev.actor || "—"}</td>
                      <td className="max-w-md p-3 text-xs text-muted-foreground">{formatEventDetail(ev)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </SectionCard>
        ) : (
          <SectionCard kicker="ACTIVITY" title="Close timeline" className="mt-4" data-testid="close-activity-timeline-hint">
            <p className="text-sm text-muted-foreground">Select a close cycle from the list to view its activity timeline.</p>
          </SectionCard>
        )}

        <Sheet open={Boolean(selectedTaskId)} onOpenChange={(o) => !o && setSelectedTaskId(null)}>
          <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-md">
            <SheetHeader>
              <SheetTitle className="text-left font-display text-lg">Close task</SheetTitle>
              <SheetDescription className="text-left">Evidence, notes, and ownership for this checklist line.</SheetDescription>
            </SheetHeader>
            {selectedTask ? (
              <div className="mt-4 space-y-4 text-sm">
                <div>
                  <div className="crt-overline text-muted-foreground">Title</div>
                  <p className="mt-1 text-foreground">{selectedTask.title}</p>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <div className="crt-overline text-muted-foreground">Status</div>
                    <p className="crt-num mt-1 text-xs uppercase">{selectedTask.status}</p>
                  </div>
                  <div>
                    <div className="crt-overline text-muted-foreground">Critical</div>
                    <p className="crt-num mt-1 text-xs uppercase">{selectedTask.critical ? "yes" : "no"}</p>
                  </div>
                </div>
                <div>
                  <label className="crt-overline text-muted-foreground" htmlFor="close-owner">
                    Owner email
                  </label>
                  <input
                    id="close-owner"
                    value={draftOwner}
                    onChange={(e) => setDraftOwner(e.target.value)}
                    className="mt-1 w-full rounded-sm border border-zinc-300 bg-white px-2 py-2 text-sm text-foreground dark:border-zinc-600 dark:bg-zinc-950"
                    placeholder="controller@company.com"
                  />
                </div>
                <div>
                  <label className="crt-overline text-muted-foreground" htmlFor="close-due">
                    Due date
                  </label>
                  <input
                    id="close-due"
                    type="date"
                    value={draftDue}
                    onChange={(e) => setDraftDue(e.target.value)}
                    className="mt-1 w-full rounded-sm border border-zinc-300 bg-white px-2 py-2 text-sm text-foreground dark:border-zinc-600 dark:bg-zinc-950"
                  />
                </div>
                <button
                  type="button"
                  disabled={savingTask}
                  onClick={saveTaskMeta}
                  className="crt-num rounded-sm border border-primary bg-primary px-4 py-2 text-xs uppercase tracking-wider text-primary-foreground disabled:opacity-50"
                  data-testid="close-task-save-meta"
                >
                  {savingTask ? "Saving…" : "Save owner & due date"}
                </button>
                <div>
                  <div className="crt-overline text-muted-foreground">Evidence</div>
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-foreground">
                    {(selectedTask.evidence || []).length === 0 ? <li className="text-muted-foreground">None yet</li> : null}
                    {(selectedTask.evidence || []).map((ev) => (
                      <li key={ev.id || ev.uri}>
                        <span className="font-medium">{ev.label || ev.type}</span>{" "}
                        <span className="text-muted-foreground">{ev.uri}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <div className="crt-overline text-muted-foreground">Notes</div>
                  <ul className="mt-2 space-y-2 text-xs">
                    {(selectedTask.notes || []).length === 0 ? <li className="text-muted-foreground">None</li> : null}
                    {(selectedTask.notes || []).map((n, i) => (
                      <li key={i} className="rounded border border-zinc-200 bg-zinc-50/80 p-2 dark:border-zinc-800">
                        <div className="font-mono text-[10px] text-muted-foreground">{n.at} · {n.by}</div>
                        <div className="mt-1 text-foreground">{n.text}</div>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            ) : null}
          </SheetContent>
        </Sheet>
      </div>
    </PageShell>
  );
}
