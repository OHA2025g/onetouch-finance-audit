import React, { useEffect, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterStrip from "../components/filters/MastersFilterStrip";
import { StatCard } from "../components/StatCard";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";

export default function BoardReportingWorkbenchPage() {
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState(false);

  const refresh = async () => {
    try {
      const [tplRes, verRes] = await Promise.all([
        http.get("/reports/templates"),
        http.get("/reports/versions", { params: { limit: 50 } }),
      ]);
      const items = tplRes.data?.items || [];
      const exportFormats = tplRes.data?.export_formats || [];
      const verItems = verRes.data?.items || [];
      setD({
        templateCount: items.length,
        versionCount: verRes.data?.count ?? verItems.length,
        exportFormatCount: exportFormats.length,
        exportFormats,
        templates: items.slice(0, 30),
        versions: verItems.slice(0, 30),
        note: tplRes.data?.note || "",
      });
    } catch {
      toast.error("Failed to load board reporting workbench");
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const generateDemo = async () => {
    setBusy(true);
    try {
      const g = await http.post("/reports/generate", {
        template_id: "tpl-audit-committee-pack",
        format: "pdf",
        filters: { entity_code: "US-HQ" },
      });
      const rid = g.data?.id;
      if (rid) {
        await http.get(`/reports/${rid}`);
      }
      await refresh();
      toast.success(rid ? `Generated report ${rid}` : "Generate completed");
    } catch {
      toast.error("Generate failed");
    } finally {
      setBusy(false);
    }
  };

  if (!d) {
    return (
      <div className="crt-overline p-8 text-muted-foreground" data-testid="board-reporting-workbench-loading">
        Loading board & committee report automation…
      </div>
    );
  }

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="board-reporting-workbench-page" data-board-reporting-phase39-surface="true">
        <PageHeader
          kicker="BOARD REPORTING · PHASE 39"
          title="Templates · generate · versions"
          subtitle="GET /reports/templates and /reports/versions; POST /reports/generate aligns with L4 audit-committee pack flow."
        />

        <MastersFilterStrip className="mb-6" />

        <div className="mb-4 flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="crt-pill text-xs px-3 py-1.5 border border-border rounded-md hover:bg-muted/50 disabled:opacity-50"
            data-testid="br39-generate-demo"
            disabled={busy}
            onClick={generateDemo}
          >
            {busy ? "Generating…" : "Generate audit committee pack (demo)"}
          </button>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-8">
          <StatCard label="Templates in library" value={d.templateCount} testId="br39-kpi-templates" />
          <StatCard label="Recent report rows" value={d.versionCount} testId="br39-kpi-versions" />
          <StatCard label="Export formats" value={d.exportFormatCount} testId="br39-kpi-export-formats" />
        </div>

        {d.note ? (
          <p className="crt-num text-xs text-muted-foreground mb-6 px-1" data-testid="br39-api-note">
            {d.note}
          </p>
        ) : null}

        <SectionCard kicker="LIBRARY" title="Report templates (top 30)">
          <DataTable className="rounded-none border-0 bg-transparent mb-10" maxHeightClassName="max-h-[38vh]" testId="br39-templates-table">
            <DataTableHead>
              <tr>
                <DataTableTh>ID</DataTableTh>
                <DataTableTh>Name</DataTableTh>
                <DataTableTh>Default</DataTableTh>
                <DataTableTh>Status</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {d.templates.map((row) => (
                <DataTableRow key={row.id} testId={`br39-tpl-${row.id}`}>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{row.id}</DataTableTd>
                  <DataTableTd className="text-xs text-foreground">{row.name || "—"}</DataTableTd>
                  <DataTableTd className="text-xs text-muted-foreground">{row.default_format || "—"}</DataTableTd>
                  <DataTableTd className="text-xs text-foreground">{row.status || "—"}</DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>

        <SectionCard kicker="VERSIONS" title="Recent generated reports">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[36vh]" testId="br39-versions-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Report ID</DataTableTh>
                <DataTableTh>Template</DataTableTh>
                <DataTableTh>Version</DataTableTh>
                <DataTableTh>Status</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {d.versions.length === 0 ? (
                <tr>
                  <td colSpan={4} className="crt-num px-4 py-8 text-center text-xs text-muted-foreground">
                    No runs yet — use Generate demo or POST /reports/generate.
                  </td>
                </tr>
              ) : null}
              {d.versions.map((row) => (
                <DataTableRow key={row.id} testId={`br39-ver-${row.id}`}>
                  <DataTableTd className="crt-num text-xs text-muted-foreground">{row.id}</DataTableTd>
                  <DataTableTd className="text-xs text-foreground">{row.template_id || "—"}</DataTableTd>
                  <DataTableTd className="text-xs text-muted-foreground">{row.version || "—"}</DataTableTd>
                  <DataTableTd className="text-xs text-foreground">{row.status || "—"}</DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>
      </div>
    </PageShell>
  );
}
