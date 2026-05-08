import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { buildDashboardFilterParams } from "../lib/mastersDashboardParams";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { StatCard } from "../components/StatCard";
import { useAuth } from "../lib/auth";

export default function MonthEndClosePage() {
  const { cycleId } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const { hrefWithMasterParams, entityCode, periodYm, periodExplicit, departmentId, costCenterId } = useMastersFilters();
  const [cycles, setCycles] = useState([]);
  const [cycle, setCycle] = useState(null);
  const [creating, setCreating] = useState(false);
  const [signingOff, setSigningOff] = useState(false);
  const [closeMetrics, setCloseMetrics] = useState(null);
  const [overrideReason, setOverrideReason] = useState("");
  const [showOverride, setShowOverride] = useState(false);

  const canSignOff = ["CFO", "Super Admin"].includes(user?.role);

  const scopeParams = useMemo(
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

  const loadCycles = () =>
    http
      .get("/close/cycles")
      .then((r) => setCycles(r.data || []))
      .catch(() => toast.error("Failed to load close cycles"));

  const loadCycle = (id) =>
    http
      .get(`/close/cycles/${id}`)
      .then((r) => setCycle(r.data))
      .catch(() => toast.error("Failed to load close cycle"));

  useEffect(() => {
    loadCycles();
  }, []);

  useEffect(() => {
    if (!cycleId) {
      setCycle(null);
      setCloseMetrics(null);
      setShowOverride(false);
      return;
    }
    loadCycle(cycleId);
  }, [cycleId]);

  useEffect(() => {
    if (!cycleId) return;
    http
      .get("/close/bottlenecks", { params: { cycle_id: cycleId } })
      .then((r) =>
        setCloseMetrics((m) => ({ ...(m || {}), bottlenecks: r.data })),
      )
      .catch(() => {});
    http
      .get("/close/quality-score", { params: { cycle_id: cycleId } })
      .then((r) =>
        setCloseMetrics((m) => ({ ...(m || {}), quality: r.data })),
      )
      .catch(() => {});
  }, [cycleId, cycle?.updated_at]);

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
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Approve failed");
    }
  };

  const submitTask = async (taskId) => {
    try {
      await http.post(`/close/tasks/${taskId}/submit`);
      toast.success("Task submitted");
      await loadCycle(cycleId);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Submit failed");
    }
  };

  const reopenTask = async (taskId) => {
    try {
      await http.post(`/close/tasks/${taskId}/reopen`, { note: "Reopened from UI" });
      toast.success("Task reopened");
      await loadCycle(cycleId);
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

  const criticalIncomplete = (cycle?.tasks || []).filter((t) => t.critical && t.status !== "approved").length;

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="month-end-close-page">
        <PageHeader
          kicker="FINANCE OPERATIONS"
          title="Month-end close"
          subtitle="Cycles, tasks, evidence, approvals, close quality metrics, and CFO sign-off (Phase 6)."
          right={
            <div className="flex flex-wrap items-center gap-2">
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

        {cycleId && closeMetrics?.quality ? (
          <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2" data-testid="close-metrics-row">
            <StatCard
              label="Close quality score"
              value={closeMetrics.quality.score}
              testId="close-quality-score"
            />
            <StatCard
              label="Pending tasks (bottleneck)"
              value={closeMetrics.bottlenecks?.pending ?? "—"}
              testId="close-bottlenecks-pending"
            />
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
                ? criticalIncomplete
                  ? `${criticalIncomplete} critical tasks pending approval (sign-off blocked).`
                  : "All critical tasks approved — ready for sign-off."
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
                    <DataTableTh>Critical</DataTableTh>
                    <DataTableTh>Status</DataTableTh>
                    <DataTableTh align="right" className="w-56">
                      Actions
                    </DataTableTh>
                  </tr>
                </DataTableHead>
                <DataTableBody>
                  {(cycle.tasks || []).map((t) => (
                    <DataTableRow key={t.id} testId={`close-task-${t.id}`}>
                      <DataTableTd>
                        <div className="text-sm text-foreground">{t.title}</div>
                        <div className="crt-num mt-0.5 text-[10px] uppercase tracking-wider text-muted-foreground">
                          due {String(t.due_date || "").slice(0, 10)}
                        </div>
                      </DataTableTd>
                      <DataTableTd className="text-sm text-muted-foreground">{t.category || "—"}</DataTableTd>
                      <DataTableTd className="crt-num text-xs uppercase">{t.critical ? "yes" : "no"}</DataTableTd>
                      <DataTableTd className="crt-num text-xs uppercase">{t.status}</DataTableTd>
                      <DataTableTd align="right">
                        <div className="flex flex-wrap justify-end gap-2">
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
                  ))}
                </DataTableBody>
              </DataTable>
            ) : (
              <div className="p-4 text-sm text-muted-foreground">Select a close cycle to view tasks.</div>
            )}
          </SectionCard>
        </div>
      </div>
    </PageShell>
  );
}

