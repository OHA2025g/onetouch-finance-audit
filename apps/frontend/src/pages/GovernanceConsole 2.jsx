import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { ShieldCheck, Gavel, Trash, Plus } from "@phosphor-icons/react";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";

export default function GovernanceConsole() {
  const [tab, setTab] = useState("retention");
  const [policies, setPolicies] = useState([]);
  const [eligible, setEligible] = useState([]);
  const [holds, setHolds] = useState([]);
  const [name, setName] = useState("");
  const [scope, setScope] = useState("case");
  const [reason, setReason] = useState("");
  const [auditSince, setAuditSince] = useState("");
  const [auditUntil, setAuditUntil] = useState("");
  const [auditAction, setAuditAction] = useState("");
  const [auditObjectType, setAuditObjectType] = useState("");
  const [auditObjectId, setAuditObjectId] = useState("");
  const [auditActor, setAuditActor] = useState("");
  const [auditQ, setAuditQ] = useState("");
  const [auditPreviewTotal, setAuditPreviewTotal] = useState(null);
  const [auditPreviewLoading, setAuditPreviewLoading] = useState(false);
  const [auditExportGzip, setAuditExportGzip] = useState(false);
  const [auditExportOffset, setAuditExportOffset] = useState("");
  const [auditExportAfterTs, setAuditExportAfterTs] = useState("");
  const [auditExportAfterId, setAuditExportAfterId] = useState("");
  const [auditExportDigest, setAuditExportDigest] = useState(false);

  const load = async () => {
    const [p, e, h] = await Promise.all([
      http.get("/retention/policies"),
      http.get("/retention/eligible"),
      http.get("/legal-holds", { params: { status: "active" } }),
    ]);
    setPolicies(p.data);
    setEligible(e.data);
    setHolds(h.data);
  };

  useEffect(() => { load(); }, []);

  const applyAuditExportTransportParams = (params) => {
    const kt = auditExportAfterTs.trim();
    if (kt) {
      params.after_ts = kt;
      if (auditExportAfterId.trim()) params.after_id = auditExportAfterId.trim();
    } else {
      const o = Number.parseInt(auditExportOffset, 10);
      if (Number.isFinite(o) && o > 0) params.offset = o;
    }
    if (auditExportGzip) params.gzip = true;
    if (auditExportDigest) params.digest = true;
  };

  const runRetention = async (dry) => {
    try {
      const { data } = await http.post("/retention/run", { dry_run: dry, artifact_types: null });
      toast.success(dry ? `Dry run: ${JSON.stringify(data.deleted)}` : `Purge complete: ${JSON.stringify(data.deleted)}`);
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Retention run failed");
    }
  };

  const exportAuditLogsCsv = async () => {
    try {
      const params = {};
      if (auditQ.trim()) params.q = auditQ.trim();
      if (auditActor.trim()) params.actor = auditActor.trim();
      if (auditAction.trim()) params.action_type = auditAction.trim();
      if (auditObjectType.trim()) params.object_type = auditObjectType.trim();
      if (auditObjectId.trim()) params.object_id = auditObjectId.trim();
      if (auditSince.trim()) params.since_ts = auditSince.trim();
      if (auditUntil.trim()) params.until_ts = auditUntil.trim();
      applyAuditExportTransportParams(params);
      const resp = await http.get("/admin/audit-logs/export.csv", { params, responseType: "blob" });
      const blob = new Blob([resp.data], { type: auditExportGzip ? "application/gzip" : "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = auditExportGzip ? "audit-logs.csv.gz" : "audit-logs.csv";
      a.click();
      URL.revokeObjectURL(url);
      toast.success(auditExportGzip ? "Downloaded audit logs CSV (gzip)" : "Downloaded audit logs CSV");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Audit logs export failed");
    }
  };

  const exportAuditLogsJson = async () => {
    try {
      const params = {};
      if (auditQ.trim()) params.q = auditQ.trim();
      if (auditActor.trim()) params.actor = auditActor.trim();
      if (auditAction.trim()) params.action_type = auditAction.trim();
      if (auditObjectType.trim()) params.object_type = auditObjectType.trim();
      if (auditObjectId.trim()) params.object_id = auditObjectId.trim();
      if (auditSince.trim()) params.since_ts = auditSince.trim();
      if (auditUntil.trim()) params.until_ts = auditUntil.trim();
      applyAuditExportTransportParams(params);
      const resp = await http.get("/admin/audit-logs/export.json", { params, responseType: "blob" });
      const blob = new Blob([resp.data], { type: auditExportGzip ? "application/gzip" : "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = auditExportGzip ? "audit-logs.json.gz" : "audit-logs.json";
      a.click();
      URL.revokeObjectURL(url);
      toast.success(auditExportGzip ? "Downloaded audit logs JSON (gzip)" : "Downloaded audit logs JSON");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Audit logs JSON export failed");
    }
  };

  const exportAuditLogsNdjson = async () => {
    try {
      const params = {};
      if (auditQ.trim()) params.q = auditQ.trim();
      if (auditActor.trim()) params.actor = auditActor.trim();
      if (auditAction.trim()) params.action_type = auditAction.trim();
      if (auditObjectType.trim()) params.object_type = auditObjectType.trim();
      if (auditObjectId.trim()) params.object_id = auditObjectId.trim();
      if (auditSince.trim()) params.since_ts = auditSince.trim();
      if (auditUntil.trim()) params.until_ts = auditUntil.trim();
      applyAuditExportTransportParams(params);
      const resp = await http.get("/admin/audit-logs/export.ndjson", { params, responseType: "blob" });
      const blob = new Blob([resp.data], { type: auditExportGzip ? "application/gzip" : "application/x-ndjson" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = auditExportGzip ? "audit-logs.ndjson.gz" : "audit-logs.ndjson";
      a.click();
      URL.revokeObjectURL(url);
      toast.success(auditExportGzip ? "Downloaded audit logs NDJSON (gzip)" : "Downloaded audit logs NDJSON");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Audit logs NDJSON export failed");
    }
  };

  const previewAuditLogCount = async () => {
    setAuditPreviewLoading(true);
    try {
      const params = { limit: 1, offset: 0 };
      if (auditQ.trim()) params.q = auditQ.trim();
      if (auditActor.trim()) params.actor = auditActor.trim();
      if (auditAction.trim()) params.action_type = auditAction.trim();
      if (auditObjectType.trim()) params.object_type = auditObjectType.trim();
      if (auditObjectId.trim()) params.object_id = auditObjectId.trim();
      if (auditSince.trim()) params.since_ts = auditSince.trim();
      if (auditUntil.trim()) params.until_ts = auditUntil.trim();
      const { data } = await http.get("/admin/audit-logs/query", { params });
      setAuditPreviewTotal(typeof data?.total === "number" ? data.total : null);
      toast.message(typeof data?.total === "number" ? `Matching audit events: ${data.total}` : "Preview unavailable");
    } catch (e) {
      setAuditPreviewTotal(null);
      toast.error(e?.response?.data?.detail || "Preview failed");
    }
    setAuditPreviewLoading(false);
  };

  const auditExplorerHref = () => {
    const sp = new URLSearchParams();
    if (auditQ.trim()) sp.set("audit_q", auditQ.trim());
    if (auditActor.trim()) sp.set("audit_actor", auditActor.trim());
    if (auditAction.trim()) sp.set("audit_action", auditAction.trim());
    if (auditObjectType.trim()) sp.set("audit_object_type", auditObjectType.trim());
    if (auditObjectId.trim()) sp.set("audit_object_id", auditObjectId.trim());
    if (auditSince.trim()) sp.set("audit_since_ts", auditSince.trim());
    if (auditUntil.trim()) sp.set("audit_until_ts", auditUntil.trim());
    const qs = sp.toString();
    return qs ? `/app/admin?${qs}` : "/app/admin";
  };

  const applyPreset = (preset) => {
    // Phase 28 — safe presets for common governance tasks.
    if (preset === "exports") {
      setAuditAction("export_");
      setAuditObjectType("report");
      setAuditObjectId("audit-committee-pack");
      setAuditQ("");
      setAuditPreviewTotal(null);
    } else if (preset === "retention") {
      setAuditAction("retention_");
      setAuditObjectType("retention");
      setAuditObjectId("");
      setAuditQ("");
      setAuditPreviewTotal(null);
    } else if (preset === "access") {
      setAuditAction("login");
      setAuditObjectType("auth");
      setAuditObjectId("");
      setAuditQ("");
      setAuditPreviewTotal(null);
    }
  };

  const createHold = async () => {
    if (!name.trim() || !reason.trim()) return;
    try {
      await http.post("/legal-holds/", { name, scope, reason, entity_code: scope === "entity" ? "US-HQ" : null });
      toast.success("Legal hold created");
      setName(""); setReason("");
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Create failed");
    }
  };

  const releaseHold = async (id) => {
    if (!window.confirm("Release this hold?")) return;
    try {
      await http.post(`/legal-holds/${id}/release`, null, { params: { reason: "Released from console" } });
      toast.success("Hold released");
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Release failed");
    }
  };

  return (
    <PageShell maxWidth="max-w-[1200px]">
      <div data-testid="governance-console">
        <PageHeader
          kicker="GOVERNANCE"
          title="Retention & legal hold"
          icon={<ShieldCheck size={18} />}
          subtitle="Run retention (dry-run or limited live purge), and manage legal holds that block retention and protect evidence."
        />

        <div className="flex gap-2 mt-6">
          <button
            type="button"
            onClick={() => setTab("retention")}
            className={`px-4 h-10 text-xs font-mono uppercase rounded-full transition-colors ${
              tab === "retention" ? "bg-white text-black" : "bg-[#141414]/70 text-[#A3A3A3] hover:bg-[#1F1F1F]/70 border border-[#262626]"
            }`}
          >
            Retention
          </button>
          <button
            type="button"
            onClick={() => setTab("holds")}
            className={`px-4 h-10 text-xs font-mono uppercase rounded-full transition-colors flex items-center gap-2 ${
              tab === "holds" ? "bg-white text-black" : "bg-[#141414]/70 text-[#A3A3A3] hover:bg-[#1F1F1F]/70 border border-[#262626]"
            }`}
          >
            <Gavel size={14} /> Legal holds
          </button>
        </div>

      {tab === "retention" && (
        <div className="mt-6 space-y-6">
          <SectionCard
            kicker="RETENTION"
            title="Run retention"
            right={
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => runRetention(true)}
                  className="px-4 h-10 rounded-full border border-[#262626] bg-[#141414]/70 hover:bg-[#1F1F1F]/70 text-xs font-mono uppercase text-white"
                >
                  Dry run
                </button>
                <button
                  type="button"
                  onClick={() => runRetention(false)}
                  className="px-4 h-10 rounded-full border border-[#FF3B30] bg-[#FF3B30]/10 hover:bg-[#FF3B30]/15 text-xs font-mono uppercase text-[#FF3B30] flex items-center gap-2"
                >
                  <Trash size={14} /> Live purge (ingestion / copilot only)
                </button>
              </div>
            }
          >
            <div className="grid grid-cols-1 gap-4">
              <div>
                <div className="font-mono text-[10px] text-[#737373] uppercase mb-2">Policies</div>
                <div className="border border-[#262626] divide-y divide-[#262626]/60 text-xs font-mono rounded-xl overflow-hidden bg-[#0A0A0A]/40">
                  {policies.map((p) => (
                    <div key={p.id} className="p-3 flex justify-between gap-4">
                      <span className="text-white">{p.name}</span>
                      <span className="text-[#737373]">{p.artifact_type} · {p.retention_days}d · {p.action}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <div className="font-mono text-[10px] text-[#737373] uppercase mb-2">Eligible (estimate)</div>
                <pre className="p-3 bg-[#0A0A0A]/55 backdrop-blur border border-[#262626] text-[10px] text-[#A3A3A3] overflow-x-auto rounded-xl">{JSON.stringify(eligible, null, 2)}</pre>
              </div>
            </div>
          </SectionCard>

          <SectionCard
            kicker="AUDIT LOGS"
            title="Audit log governance"
            subtitle="Audit logs are governance data. Purge is blocked by default; prefer exporting to your archive/SIEM."
            right={
              <div className="flex flex-wrap gap-2">
                <Link
                  to={auditExplorerHref()}
                  className="px-4 h-10 rounded-full border border-[#262626] bg-[#141414]/70 hover:bg-[#1F1F1F]/70 text-xs font-mono uppercase text-white flex items-center"
                >
                  Open log explorer
                </Link>
                <label className="flex items-center gap-2 px-3 h-10 rounded-full border border-[#262626] bg-[#141414]/70 text-[10px] font-mono uppercase text-[#A3A3A3] cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={auditExportGzip}
                    onChange={(e) => setAuditExportGzip(e.target.checked)}
                    className="rounded border-[#404040] bg-[#0A0A0A]/70"
                  />
                  Gzip
                </label>
                <div className="flex items-center gap-2 px-3 h-10 rounded-full border border-[#262626] bg-[#141414]/70" title="Export row offset (ignored when cursor set)">
                  <span className="text-[10px] font-mono uppercase text-[#737373]">Off</span>
                  <input
                    type="number"
                    min={0}
                    value={auditExportOffset}
                    onChange={(e) => setAuditExportOffset(e.target.value)}
                    placeholder="0"
                    className="w-14 h-8 rounded-md border border-[#404040] bg-[#0A0A0A]/70 px-2 font-mono text-xs text-white outline-none"
                  />
                </div>
                <div className="flex flex-wrap items-center gap-1 px-2 min-h-10 rounded-full border border-[#262626] bg-[#141414]/70 py-1" title="Paste next_cursor from JSON export">
                  <input
                    type="text"
                    value={auditExportAfterTs}
                    onChange={(e) => setAuditExportAfterTs(e.target.value)}
                    placeholder="after_ts"
                    className="w-[118px] h-8 rounded-md border border-[#404040] bg-[#0A0A0A]/70 px-2 font-mono text-[10px] text-white outline-none"
                  />
                  <input
                    type="text"
                    value={auditExportAfterId}
                    onChange={(e) => setAuditExportAfterId(e.target.value)}
                    placeholder="after_id"
                    className="w-[100px] h-8 rounded-md border border-[#404040] bg-[#0A0A0A]/70 px-2 font-mono text-[10px] text-white outline-none"
                  />
                </div>
                <label className="flex items-center gap-2 px-3 h-10 rounded-full border border-[#262626] bg-[#141414]/70 text-[10px] font-mono uppercase text-[#A3A3A3] cursor-pointer select-none" title="X-Audit-Export-Sha256 on response bytes">
                  <input
                    type="checkbox"
                    checked={auditExportDigest}
                    onChange={(e) => setAuditExportDigest(e.target.checked)}
                    className="rounded border-[#404040] bg-[#0A0A0A]/70"
                  />
                  Digest
                </label>
                <button
                  type="button"
                  onClick={exportAuditLogsCsv}
                  className="px-4 h-10 rounded-full border border-[#262626] bg-[#141414]/70 hover:bg-[#1F1F1F]/70 text-xs font-mono uppercase text-white"
                >
                  Export CSV
                </button>
                <button
                  type="button"
                  onClick={exportAuditLogsJson}
                  className="px-4 h-10 rounded-full border border-[#262626] bg-[#141414]/70 hover:bg-[#1F1F1F]/70 text-xs font-mono uppercase text-white"
                >
                  Export JSON
                </button>
                <button
                  type="button"
                  onClick={exportAuditLogsNdjson}
                  className="px-4 h-10 rounded-full border border-[#262626] bg-[#141414]/70 hover:bg-[#1F1F1F]/70 text-xs font-mono uppercase text-white"
                >
                  Export NDJSON
                </button>
                <button
                  type="button"
                  onClick={previewAuditLogCount}
                  disabled={auditPreviewLoading}
                  className="px-4 h-10 rounded-full border border-[#262626] bg-[#0A0A0A]/55 hover:bg-[#1F1F1F]/70 text-xs font-mono uppercase text-white disabled:opacity-50"
                >
                  {auditPreviewLoading ? "Preview…" : "Preview count"}
                </button>
              </div>
            }
          >
            <div className="grid grid-cols-1 gap-4">
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => applyPreset("exports")}
                  className="px-3 h-9 rounded-full border border-[#262626] bg-[#0A0A0A]/55 hover:bg-[#1F1F1F]/70 text-[10px] font-mono uppercase tracking-wider text-white"
                >
                  Preset: exports
                </button>
                <button
                  type="button"
                  onClick={() => applyPreset("retention")}
                  className="px-3 h-9 rounded-full border border-[#262626] bg-[#0A0A0A]/55 hover:bg-[#1F1F1F]/70 text-[10px] font-mono uppercase tracking-wider text-white"
                >
                  Preset: retention
                </button>
                <button
                  type="button"
                  onClick={() => applyPreset("access")}
                  className="px-3 h-9 rounded-full border border-[#262626] bg-[#0A0A0A]/55 hover:bg-[#1F1F1F]/70 text-[10px] font-mono uppercase tracking-wider text-white"
                >
                  Preset: access
                </button>
                <button
                  type="button"
                  onClick={() => { setAuditSince(""); setAuditUntil(""); setAuditAction(""); setAuditObjectType(""); setAuditObjectId(""); setAuditActor(""); setAuditQ(""); }}
                  className="px-3 h-9 rounded-full border border-[#262626] bg-[#0A0A0A]/55 hover:bg-[#1F1F1F]/70 text-[10px] font-mono uppercase tracking-wider text-[#A3A3A3]"
                >
                  Clear
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <div className="font-mono text-[10px] text-[#737373] uppercase mb-1">Since (ISO)</div>
                  <input value={auditSince} onChange={(e) => setAuditSince(e.target.value)} placeholder="2026-05-01" className="w-full bg-[#141414]/70 backdrop-blur border border-[#404040] px-3 h-10 text-xs text-white rounded-xl" />
                </div>
                <div>
                  <div className="font-mono text-[10px] text-[#737373] uppercase mb-1">Until (ISO)</div>
                  <input value={auditUntil} onChange={(e) => setAuditUntil(e.target.value)} placeholder="2026-05-31" className="w-full bg-[#141414]/70 backdrop-blur border border-[#404040] px-3 h-10 text-xs text-white rounded-xl" />
                </div>
                <div>
                  <div className="font-mono text-[10px] text-[#737373] uppercase mb-1">Actor</div>
                  <input value={auditActor} onChange={(e) => setAuditActor(e.target.value)} placeholder="cfo@onetouch.ai" className="w-full bg-[#141414]/70 backdrop-blur border border-[#404040] px-3 h-10 text-xs text-white rounded-xl" />
                </div>
                <div>
                  <div className="font-mono text-[10px] text-[#737373] uppercase mb-1">Search</div>
                  <input value={auditQ} onChange={(e) => setAuditQ(e.target.value)} placeholder="actor/action/object…" className="w-full bg-[#141414]/70 backdrop-blur border border-[#404040] px-3 h-10 text-xs text-white rounded-xl" />
                </div>
                <div>
                  <div className="font-mono text-[10px] text-[#737373] uppercase mb-1">Action (prefix ok)</div>
                  <input value={auditAction} onChange={(e) => setAuditAction(e.target.value)} placeholder="export_" className="w-full bg-[#141414]/70 backdrop-blur border border-[#404040] px-3 h-10 text-xs text-white rounded-xl" />
                </div>
                <div>
                  <div className="font-mono text-[10px] text-[#737373] uppercase mb-1">Object type</div>
                  <input value={auditObjectType} onChange={(e) => setAuditObjectType(e.target.value)} placeholder="report" className="w-full bg-[#141414]/70 backdrop-blur border border-[#404040] px-3 h-10 text-xs text-white rounded-xl" />
                </div>
                <div className="md:col-span-2">
                  <div className="font-mono text-[10px] text-[#737373] uppercase mb-1">Object id</div>
                  <input value={auditObjectId} onChange={(e) => setAuditObjectId(e.target.value)} placeholder="audit-committee-pack" className="w-full bg-[#141414]/70 backdrop-blur border border-[#404040] px-3 h-10 text-xs text-white rounded-xl" />
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 text-[10px] font-mono uppercase text-[#737373]">
                <span>Tip: use presets + date range, then open the explorer for drill-down. Exports use the same filter scope.</span>
                {typeof auditPreviewTotal === "number" ? <span>preview: {auditPreviewTotal} events</span> : null}
              </div>
            </div>
          </SectionCard>
        </div>
      )}

      {tab === "holds" && (
        <div className="mt-6 space-y-6">
          <SectionCard kicker="LEGAL HOLD" title="Create new hold">
            <div className="space-y-2">
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" className="w-full bg-[#141414]/70 backdrop-blur border border-[#404040] px-3 h-10 text-xs text-white rounded-xl" />
              <select value={scope} onChange={(e) => setScope(e.target.value)} className="w-full bg-[#141414]/70 backdrop-blur border border-[#404040] px-3 h-10 text-xs text-white rounded-xl">
              <option value="case">case</option>
              <option value="evidence">evidence</option>
              <option value="entity">entity</option>
              <option value="global">global</option>
            </select>
              <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason" className="w-full bg-[#141414]/70 backdrop-blur border border-[#404040] px-3 h-10 text-xs text-white rounded-xl" />
              <button type="button" onClick={createHold} className="flex items-center gap-2 px-4 h-10 bg-white text-black text-xs font-mono uppercase rounded-full shadow-[0_18px_55px_rgba(255,255,255,0.08)]">
                <Plus size={14} /> Create
              </button>
            </div>
          </SectionCard>

          <SectionCard kicker="ACTIVE" title={`Active holds (${holds.length})`} bodyClassName="p-0">
            <div className="divide-y divide-[#262626]/60 text-xs font-mono">
              {holds.map((h) => (
                <div key={h.id} className="p-4 flex justify-between items-center gap-4">
                  <div>
                    <div className="text-white">{h.name}</div>
                    <div className="text-[#737373]">{h.scope} · {h.id}</div>
                    <div className="mt-2 font-mono text-[10px] uppercase">
                      <Link to="/app/evidence" className="text-[#0A84FF] hover:underline">Evidence explorer</Link>
                      {" · "}
                      <Link to="/app/cases" className="text-[#0A84FF] hover:underline">Cases</Link>
                    </div>
                  </div>
                  <button type="button" onClick={() => releaseHold(h.id)} className="px-4 h-10 rounded-full border border-[#FF9F0A] text-[#FF9F0A] uppercase text-[10px] hover:bg-[#FF9F0A]/10 transition-colors">
                    Release
                  </button>
                </div>
              ))}
              {!holds.length && <div className="p-4 text-[#737373]">No active holds.</div>}
            </div>
          </SectionCard>
        </div>
      )}
      </div>
    </PageShell>
  );
}
