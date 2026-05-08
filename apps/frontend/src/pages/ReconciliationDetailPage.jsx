import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { http } from "../lib/api";
import { fmtUSD, fmtDate } from "../lib/format";
import { CaretLeft } from "@phosphor-icons/react";
import DrillContextBar from "../components/DrillContextBar";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";

export default function ReconciliationDetailPage() {
  const { reconciliationId } = useParams();
  const nav = useNavigate();
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (!reconciliationId) return;
    setErr(null);
    http
      .get(`/reconciliations/${encodeURIComponent(reconciliationId)}`)
      .then((r) => setData(r.data))
      .catch((e) => setErr(e?.response?.data?.detail || "Failed to load"));
  }, [reconciliationId]);

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
          { label: "Controller", to: "/app/controller" },
          { label: r.id },
        ]}
      />
      <div data-testid="reconciliation-detail">
        <PageHeader
          kicker="RECONCILIATION"
          title={`${r.reconciliation_type} · ${r.entity}`}
          subtitle={`Period ${r.period} · status ${r.status}`}
        />

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
          <SectionCard kicker="POSITION" title="Balances" bodyClassName="p-4 space-y-2 font-mono text-xs text-[#A3A3A3]">
            <div className="flex justify-between text-foreground">
              <span>Variance</span>
              <span className="tabular-nums">{fmtUSD(r.variance_amount)}</span>
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
              >
                <div className="font-mono text-[10px] uppercase text-muted-foreground">Sample journal (same entity)</div>
                <div className="mt-1 text-sm text-foreground">{j.journal_number || j.id}</div>
                <div className="mt-1 font-mono text-[10px] text-primary">Open journal drill →</div>
              </Link>
            ) : (
              <div className="text-xs text-[#737373]">No linked journal sample for this entity.</div>
            )}
            <Link to="/app/rollups" className="inline-block text-xs font-mono uppercase text-[#0A84FF] hover:underline">
              Entity rollups →
            </Link>
          </SectionCard>
        </div>
      </div>
    </PageShell>
  );
}
