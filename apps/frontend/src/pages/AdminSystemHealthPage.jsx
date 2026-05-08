import React, { useEffect, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";

export default function AdminSystemHealthPage() {
  const [d, setD] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    http
      .get("/system/health")
      .then((r) => setD(r.data))
      .catch((e) => toast.error(e?.response?.data?.detail || "Failed to load system health"))
      .finally(() => setLoading(false));
  }, []);

  if (loading && !d) {
    return <div className="crt-overline p-8 text-muted-foreground">Loading system health…</div>;
  }

  return (
    <PageShell maxWidth="max-w-[1200px]">
      <div data-testid="admin-system-health-page">
        <PageHeader
          kicker="ADMIN"
          title="System health"
          subtitle="Dependency and dataset sanity checks (Phase 40)."
        />

        <SectionCard kicker="STATUS" title="Overall">
          <div className="text-sm">
            <div className="crt-num text-xs uppercase tracking-wider text-muted-foreground">Status</div>
            <div className="mt-1 text-base text-foreground">{d?.status || "unknown"}</div>
            <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
              <div>
                <div className="crt-num text-xs uppercase tracking-wider text-muted-foreground">Service</div>
                <div className="mt-1 text-foreground">{d?.service || "—"}</div>
              </div>
              <div>
                <div className="crt-num text-xs uppercase tracking-wider text-muted-foreground">Now</div>
                <div className="mt-1 font-mono text-xs text-foreground">{d?.now || "—"}</div>
              </div>
            </div>
          </div>
        </SectionCard>

        <SectionCard kicker="DATASET" title="Collection counts" className="mt-4" bodyClassName="p-0">
          <div className="divide-y divide-zinc-200 dark:divide-zinc-800">
            {Object.entries(d?.counts || {}).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between px-4 py-3">
                <span className="crt-num text-xs uppercase tracking-wider text-muted-foreground">{k}</span>
                <span className="font-mono text-sm text-foreground">{String(v)}</span>
              </div>
            ))}
          </div>
        </SectionCard>
      </div>
    </PageShell>
  );
}

