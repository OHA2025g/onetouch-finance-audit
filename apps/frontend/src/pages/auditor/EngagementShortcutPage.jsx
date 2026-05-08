import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { toast } from "sonner";
import { http } from "../../lib/api";
import { PageHeader, PageShell, SectionCard } from "../../components/PageShell";

const DEMO_EID = "ENG-DEMO-IN-2025";

export default function EngagementShortcutPage({
  kicker = "AUDIT · SHORTCUT",
  title,
  subtitle,
  buildPath,
  primaryCta = "Open module",
}) {
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const eid = params.get("engagement_id") || DEMO_EID;

  const [engagements, setEngagements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  const targetPath = useMemo(() => buildPath(eid), [buildPath, eid]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setErr(null);
      try {
        const { data } = await http.get("/audit-engagements");
        if (!cancelled) setEngagements(Array.isArray(data) ? data : []);
      } catch {
        if (!cancelled) setErr("Could not load engagements.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const setEngagement = (id) => {
    const n = new URLSearchParams(params);
    n.set("engagement_id", id);
    setParams(n, { replace: true });
  };

  return (
    <PageShell maxWidth="max-w-[1200px]">
      <PageHeader
        kicker={kicker}
        title={title}
        subtitle={subtitle}
        right={
          <div className="flex flex-wrap gap-2 justify-end">
            <Link to="/app/audit-planning" className="text-xs font-mono uppercase text-[#0A84FF]">
              Audit planning
            </Link>
            <button
              onClick={() => nav(targetPath)}
              className="rounded-sm border border-zinc-300 bg-zinc-100 px-2 py-1 text-xs font-mono uppercase text-zinc-800 transition-colors hover:bg-zinc-200 dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-700"
            >
              {primaryCta}
            </button>
          </div>
        }
      />

      <SectionCard kicker="ENGAGEMENT" title="Pick an engagement" bodyClassName="p-6 space-y-4">
        {loading ? <div className="font-mono text-xs text-[#737373]">Loading engagements…</div> : null}
        {err && !loading ? <div className="text-sm text-red-600 dark:text-red-300">{err}</div> : null}

        {!loading && !err && engagements.length === 0 ? (
          <div className="text-sm text-[#737373]">
            No engagements found. Create one in Audit planning, or use the demo engagement {DEMO_EID}.
          </div>
        ) : null}

        <div className="flex flex-wrap gap-3 items-center">
          <label className="text-xs font-mono uppercase text-muted-foreground">Engagement</label>
          <select
            value={eid}
            onChange={(ev) => setEngagement(ev.target.value)}
            className="min-w-[320px] rounded-sm border border-zinc-300 bg-white px-3 py-2 text-sm text-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100"
          >
            {engagements.every((x) => x.engagement_id !== eid) ? <option value={eid}>{eid}</option> : null}
            {engagements.map((en) => (
              <option key={en.engagement_id} value={en.engagement_id}>
                {en.engagement_id} — {en.entity_name}
              </option>
            ))}
          </select>

          <button
            onClick={() => {
              toast.success("Opening module…");
              nav(targetPath);
            }}
            className="text-xs font-mono uppercase text-[#0A84FF] hover:underline"
          >
            {primaryCta} →
          </button>
        </div>

        <div className="text-xs font-mono text-muted-foreground">
          Target: <span className="text-foreground">{targetPath}</span>
        </div>

        {!loading && !err && engagements.length > 0 ? (
          <div className="mt-4 max-h-[42vh] divide-y divide-zinc-200 overflow-y-auto rounded-sm border border-zinc-200 dark:divide-zinc-800 dark:border-zinc-800">
            {engagements.map((en) => (
              <div
                key={en.engagement_id}
                className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-900/60"
              >
                <div className="min-w-0">
                  <div className="truncate text-sm text-foreground">{en.entity_name}</div>
                  <div className="font-mono text-[10px] text-muted-foreground">{en.engagement_id}</div>
                </div>
                <div className="flex shrink-0 gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setEngagement(en.engagement_id);
                      nav(buildPath(en.engagement_id));
                    }}
                    className="rounded-sm border border-zinc-300 px-2 py-1 text-[10px] font-mono uppercase text-zinc-800 transition-colors hover:border-zinc-400 hover:bg-zinc-100 dark:border-zinc-600 dark:text-zinc-100 dark:hover:border-zinc-500 dark:hover:bg-zinc-800"
                  >
                    {primaryCta}
                  </button>
                  <Link
                    to={`/app/audit-planning/engagements/${encodeURIComponent(en.engagement_id)}`}
                    className="text-[10px] font-mono uppercase text-[#0A84FF] hover:underline px-2 py-1"
                  >
                    Hub
                  </Link>
                </div>
              </div>
            ))}
          </div>
        ) : null}
      </SectionCard>
    </PageShell>
  );
}

