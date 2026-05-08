import React, { useEffect, useMemo, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { useMastersFilters } from "../lib/MastersFilterContext";
import { StatCard } from "../components/StatCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";

export default function Copilot2WorkbenchPage() {
  const { hrefWithMasterParams } = useMastersFilters();
  const [d, setD] = useState(null);

  const chatHref = useMemo(() => hrefWithMasterParams("/app/copilot"), [hrefWithMasterParams]);

  useEffect(() => {
    Promise.all([
      http.get("/copilot/sessions", { params: { limit: 50 } }),
      http.get("/copilot/index-status"),
      http.get("/copilot/retrieval-configs"),
    ])
      .then(([sess, idx, cfg]) => {
        const rows = Array.isArray(sess.data) ? sess.data : [];
        const configs = Array.isArray(cfg.data) ? cfg.data : [];
        setD({
          sessionCount: rows.length,
          indexedDocs: idx.data?.indexed_docs ?? idx.data?.semantic?.chunks ?? 0,
          retrievalConfigs: configs.length,
          sessions: rows.slice(0, 35),
        });
      })
      .catch(() => toast.error("Failed to load Copilot 2.0 workbench"));
  }, []);

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="copilot-2-workbench-loading">
        Loading Copilot 2.0 workbench…
      </div>
    );
  }

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="copilot-2-workbench-page" data-copilot-phase37-surface="true">
        <PageHeader
          kicker="AI COPILOT · PHASE 37"
          title="Sessions · RAG index · governed asks"
          subtitle="Read-only ladder from GET /copilot/sessions and /copilot/index-status; CFO summary, audit procedure, and board asks live on POST endpoints (use full Copilot chat)."
        />

        <MastersFilterStrip className="mb-6" />

        <div className="mb-6 flex flex-wrap items-center gap-3">
          <Link
            to={chatHref}
            className="crt-num inline-flex items-center rounded-sm border border-primary/40 bg-primary/10 px-3 py-2 text-xs font-mono uppercase text-primary hover:bg-primary/15"
            data-testid="cp37-open-full-copilot"
          >
            Open full Copilot chat
          </Link>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-8">
          <StatCard label="Recent sessions (you)" value={d.sessionCount} testId="cp37-kpi-sessions" />
          <StatCard label="Indexed chunks" value={d.indexedDocs} testId="cp37-kpi-indexed-docs" />
          <StatCard label="Retrieval configs" value={d.retrievalConfigs} testId="cp37-kpi-retrieval-configs" />
        </div>

        <SectionCard kicker="SESSIONS" title="Copilot conversation history (latest 35)">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[58vh]" testId="cp37-sessions-table">
            <DataTableHead>
              <tr>
                <DataTableTh>When</DataTableTh>
                <DataTableTh>Mode</DataTableTh>
                <DataTableTh>Question</DataTableTh>
                <DataTableTh>Review</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {d.sessions.length === 0 ? (
                <tr>
                  <td colSpan={4} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                    No sessions yet. Open the full Copilot to run POST /copilot/ask or the Phase 37 generate endpoints.
                  </td>
                </tr>
              ) : null}
              {d.sessions.map((row) => (
                <DataTableRow key={row.id} testId={`cp37-sess-${row.id}`}>
                  <DataTableTd className="crt-num text-xs text-muted-foreground whitespace-nowrap">{row.created_at || "—"}</DataTableTd>
                  <DataTableTd className="text-xs text-foreground">{row.mode || "—"}</DataTableTd>
                  <DataTableTd className="text-xs text-muted-foreground max-w-[360px] truncate" title={row.question}>
                    {row.question || "—"}
                  </DataTableTd>
                  <DataTableTd className="crt-num text-xs text-foreground">{row.needs_human_review ? "Yes" : "—"}</DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>
      </div>
    </PageShell>
  );
}
