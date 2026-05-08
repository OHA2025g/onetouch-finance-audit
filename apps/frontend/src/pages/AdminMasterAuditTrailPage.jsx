import React, { useEffect, useMemo, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";

export default function AdminMasterAuditTrailPage() {
  const [loading, setLoading] = useState(true);
  const [rows, setRows] = useState([]);

  useEffect(() => {
    setLoading(true);
    const req = http.get("/masters/audit-trail", { params: { limit: 200, offset: 0 } });
    // Defensive: avoid crashing the page if the HTTP client is mocked/misconfigured.
    if (!req || typeof req.then !== "function") {
      setLoading(false);
      return;
    }
    req
      .then((r) => setRows(r?.data?.items || []))
      .catch((e) => toast.error(e?.response?.data?.detail || "Failed to load master audit trail"))
      .finally(() => setLoading(false));
  }, []);

  const hasData = rows && rows.length > 0;
  const ordered = useMemo(() => {
    const copy = [...(rows || [])];
    copy.sort((a, b) => String(b.at || "").localeCompare(String(a.at || "")));
    return copy;
  }, [rows]);

  return (
    <PageShell maxWidth="max-w-[1400px]">
      <div data-testid="admin-master-audit-trail-page">
        <PageHeader
          kicker="ADMIN"
          title="Master data audit trail"
          subtitle="Append-only history of master changes (L4 hardening for Phase 2)."
        />

        <SectionCard kicker="AUDIT" title="Recent events" className="mt-4" bodyClassName="p-0">
          {loading && !hasData ? (
            <div className="crt-overline p-8 text-muted-foreground">Loading audit trail…</div>
          ) : !hasData ? (
            <div className="p-8 text-sm text-muted-foreground">
              No master audit events yet. Create/update a master record as Super Admin to generate audit entries.
            </div>
          ) : (
            <DataTable>
              <DataTableHead>
                <DataTableRow>
                  <DataTableTh>At</DataTableTh>
                  <DataTableTh>Actor</DataTableTh>
                  <DataTableTh>Action</DataTableTh>
                  <DataTableTh>Type</DataTableTh>
                  <DataTableTh>ID</DataTableTh>
                  <DataTableTh>Entity</DataTableTh>
                </DataTableRow>
              </DataTableHead>
              <DataTableBody>
                {ordered.map((r) => (
                  <DataTableRow key={r.id || `${r.resource_type}:${r.resource_id}:${r.at}`}>
                    <DataTableTd className="font-mono text-xs">{r.at || "—"}</DataTableTd>
                    <DataTableTd className="font-mono text-xs">{r.actor_email || "—"}</DataTableTd>
                    <DataTableTd className="text-sm">{r.action || "—"}</DataTableTd>
                    <DataTableTd className="text-sm">{r.resource_type || "—"}</DataTableTd>
                    <DataTableTd className="font-mono text-xs">{r.resource_id || "—"}</DataTableTd>
                    <DataTableTd className="font-mono text-xs">{r.entity_code || "—"}</DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          )}
        </SectionCard>
      </div>
    </PageShell>
  );
}

