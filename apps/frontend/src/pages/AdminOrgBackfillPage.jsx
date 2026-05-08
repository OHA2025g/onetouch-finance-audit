import React, { useCallback, useEffect, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";

export default function AdminOrgBackfillPage() {
  const [status, setStatus] = useState(null);
  const [running, setRunning] = useState(false);

  const load = useCallback(() => {
    http
      .get("/system/org-backfill/status")
      .then((r) => setStatus(r.data))
      .catch(() => toast.error("Failed to load org backfill status"));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const run = async (targets) => {
    setRunning(true);
    try {
      const { data } = await http.post("/system/org-backfill/run", { targets, limit: 10000 });
      setStatus(data);
      toast.success("Org backfill run completed");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Org backfill failed");
    }
    setRunning(false);
  };

  return (
    <PageShell maxWidth="max-w-[1200px]">
      <div data-testid="admin-org-backfill-page">
        <PageHeader
          kicker="SUPER ADMIN"
          title="Org backfill"
          subtitle="Repair department + cost center fields on transactions, exceptions, and cases (Slice 10)."
        />

        <SectionCard
          kicker="STATUS"
          title="Latest run"
          subtitle={status?.last_run_at ? `Last run by ${status.last_run_by} at ${status.last_run_at}` : "No runs recorded yet."}
          right={
            <button
              type="button"
              className="crt-num rounded-sm border border-zinc-300 bg-white px-3 py-2 text-xs uppercase tracking-wider text-muted-foreground hover:bg-zinc-50 hover:text-foreground dark:border-zinc-600 dark:bg-zinc-900 dark:hover:bg-zinc-800 disabled:opacity-50"
              onClick={load}
              disabled={running}
            >
              Refresh
            </button>
          }
        >
          <pre className="mt-3 max-h-[420px] overflow-auto rounded-sm border border-zinc-200 bg-zinc-50 p-3 text-xs text-muted-foreground dark:border-zinc-800 dark:bg-zinc-950/40">
            {JSON.stringify(status?.last_result || status || {}, null, 2)}
          </pre>
        </SectionCard>

        <SectionCard kicker="ACTIONS" title="Run backfill" subtitle="Runs are audited. Safe to re-run (idempotent).">
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => run(["transactions", "exceptions", "cases"])}
              disabled={running}
              className="crt-num rounded-sm border border-primary bg-primary px-4 py-2 text-xs uppercase tracking-wider text-white disabled:opacity-50"
              data-testid="org-backfill-run-all"
            >
              {running ? "Running…" : "Run all"}
            </button>
            <button
              type="button"
              onClick={() => run(["transactions"])}
              disabled={running}
              className="crt-num rounded-sm border border-zinc-300 bg-white px-4 py-2 text-xs uppercase tracking-wider text-muted-foreground hover:bg-zinc-50 hover:text-foreground dark:border-zinc-600 dark:bg-zinc-900 dark:hover:bg-zinc-800 disabled:opacity-50"
            >
              Transactions only
            </button>
            <button
              type="button"
              onClick={() => run(["exceptions"])}
              disabled={running}
              className="crt-num rounded-sm border border-zinc-300 bg-white px-4 py-2 text-xs uppercase tracking-wider text-muted-foreground hover:bg-zinc-50 hover:text-foreground dark:border-zinc-600 dark:bg-zinc-900 dark:hover:bg-zinc-800 disabled:opacity-50"
            >
              Exceptions only
            </button>
            <button
              type="button"
              onClick={() => run(["cases"])}
              disabled={running}
              className="crt-num rounded-sm border border-zinc-300 bg-white px-4 py-2 text-xs uppercase tracking-wider text-muted-foreground hover:bg-zinc-50 hover:text-foreground dark:border-zinc-600 dark:bg-zinc-900 dark:hover:bg-zinc-800 disabled:opacity-50"
            >
              Cases only
            </button>
          </div>
        </SectionCard>
      </div>
    </PageShell>
  );
}

