import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { fmtDateTime } from "../lib/format";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import { MF_CC, MF_DEPT, MF_ENTITY, MF_PERIOD } from "../lib/mastersFilterKeys";

function masterHrefFromFiltersApplied(pathname, filtersApplied) {
  const fa = filtersApplied || {};
  const sp = new URLSearchParams();
  if (fa.entity_code) sp.set(MF_ENTITY, fa.entity_code);
  if (fa.period_ym) sp.set(MF_PERIOD, fa.period_ym);
  if (fa.department_id) sp.set(MF_DEPT, fa.department_id);
  if (fa.cost_center_id) sp.set(MF_CC, fa.cost_center_id);
  const qs = sp.toString();
  return qs ? `${pathname}?${qs}` : pathname;
}

export default function AuditLogEvent() {
  const { logId } = useParams();
  const nav = useNavigate();
  const [ev, setEv] = useState(null);

  useEffect(() => {
    http
      .get(`/admin/audit-logs/${encodeURIComponent(logId)}`)
      .then((r) => setEv(r.data))
      .catch(() => toast.error("Failed to load audit event"));
  }, [logId]);

  const filtersApplied = ev?.detail?.filters_applied || {};
  const canReplayPack =
    (ev?.action_type === "export_pdf" || ev?.action_type === "export_xlsx") &&
    ev?.object_type === "report" &&
    String(ev?.object_id || "").includes("audit-committee-pack");

  const replayFormat = ev?.action_type === "export_pdf" ? "pdf" : "xlsx";

  const subtitle = useMemo(() => {
    if (!ev) return "Loading…";
    const base = `${fmtDateTime(ev.event_ts)} · ${ev.actor_user_email || "—"} · ${ev.action_type}`;
    const ctx = Object.keys(filtersApplied).length
      ? ` · context: ${Object.entries(filtersApplied)
          .map(([k, v]) => `${k}=${v}`)
          .join(" · ")}`
      : "";
    return `${base}${ctx}`;
  }, [ev, filtersApplied]);

  const replay = async () => {
    try {
      const resp = await http.get(`/reports/audit-committee-pack.${replayFormat}`, {
        params: filtersApplied,
        responseType: "blob",
      });
      const blob = new Blob([resp.data]);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `audit-committee-pack.${replayFormat}`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(`Downloaded ${replayFormat.toUpperCase()} pack`);
    } catch {
      toast.error("Replay export failed");
    }
  };

  if (!ev) {
    return (
      <PageShell>
        <div className="crt-num p-8 text-xs text-muted-foreground">Loading audit event…</div>
      </PageShell>
    );
  }

  return (
    <PageShell maxWidth="max-w-[1200px]">
      <div data-testid="audit-log-event">
        <PageHeader
          kicker="AUDIT LOG"
          title={`Event ${String(ev.id || "").slice(0, 10)}…`}
          subtitle={subtitle}
          right={
            <div className="flex flex-wrap justify-end gap-2">
              <button
                type="button"
                onClick={() => nav(-1)}
                className="crt-num h-9 rounded-sm border border-zinc-300 bg-white px-3 text-[10px] uppercase tracking-wider text-muted-foreground hover:bg-zinc-50 dark:border-zinc-600 dark:bg-zinc-900"
              >
                Back
              </button>
              <Link
                to={masterHrefFromFiltersApplied("/app/cfo", filtersApplied)}
                className="crt-num h-9 rounded-sm border border-zinc-300 bg-white px-3 text-[10px] uppercase tracking-wider text-primary hover:bg-zinc-50 dark:border-zinc-600 dark:bg-zinc-900"
              >
                Open CFO
              </Link>
              <Link
                to={masterHrefFromFiltersApplied("/app/readiness", filtersApplied)}
                className="crt-num h-9 rounded-sm border border-zinc-300 bg-white px-3 text-[10px] uppercase tracking-wider text-primary hover:bg-zinc-50 dark:border-zinc-600 dark:bg-zinc-900"
              >
                Open readiness
              </Link>
              {canReplayPack ? (
                <button
                  type="button"
                  onClick={replay}
                  className="crt-num h-9 rounded-sm border border-primary bg-primary px-3 text-[10px] uppercase tracking-wider text-white hover:opacity-90"
                >
                  Replay export
                </button>
              ) : null}
            </div>
          }
        />

        <SectionCard kicker="DETAIL" title="Event payload">
          <pre className="max-h-[70vh] overflow-auto rounded-sm border border-zinc-200 bg-zinc-50 p-4 font-mono text-[12px] leading-relaxed text-foreground dark:border-zinc-800 dark:bg-zinc-950">
            {JSON.stringify(ev, null, 2)}
          </pre>
        </SectionCard>
      </div>
    </PageShell>
  );
}

