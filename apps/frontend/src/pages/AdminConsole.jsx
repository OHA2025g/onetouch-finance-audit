import React, { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { fmtDateTime } from "../lib/format";
import { Database, Cpu, ShieldCheck, ArrowsClockwise, Bell, Plus, Trash, Sparkle } from "@phosphor-icons/react";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import { DataTable, DataTableBody, DataTableHead, DataTableRow, DataTableTd, DataTableTh } from "../components/DataTable";
import { MF_CC, MF_DEPT, MF_ENTITY, MF_PERIOD } from "../lib/mastersFilterKeys";

const AUDIT_URL_PARAM_KEYS = [
  "audit_q",
  "audit_actor",
  "audit_action",
  "audit_object_type",
  "audit_object_id",
  "audit_since_ts",
  "audit_until_ts",
  "audit_offset",
];

function hasGovernanceAuditParams(searchParams) {
  return AUDIT_URL_PARAM_KEYS.some((k) => searchParams.get(k));
}

export default function AdminConsole() {
  const location = useLocation();
  const [sp, setSp] = useSearchParams();
  const [tab, setTab] = useState(() => {
    try {
      const p = new URLSearchParams(window.location.search);
      const forcedTab = (p.get("tab") || "").trim();
      if (forcedTab) return forcedTab;
      return hasGovernanceAuditParams(p) ? "logs" : "models";
    } catch {
      return "models";
    }
  });
  const [models, setModels] = useState([]);
  const [prompts, setPrompts] = useState([]);
  const [logs, setLogs] = useState([]);
  const [logsTotal, setLogsTotal] = useState(0);
  const [logQ, setLogQ] = useState(sp.get("audit_q") || "");
  const [logActor, setLogActor] = useState(sp.get("audit_actor") || "");
  const [logAction, setLogAction] = useState(sp.get("audit_action") || "");
  const [logObjectType, setLogObjectType] = useState(sp.get("audit_object_type") || "");
  const [logObjectId, setLogObjectId] = useState(sp.get("audit_object_id") || "");
  const [logSinceTs, setLogSinceTs] = useState(sp.get("audit_since_ts") || "");
  const [logUntilTs, setLogUntilTs] = useState(sp.get("audit_until_ts") || "");
  const [logOffset, setLogOffset] = useState(Number(sp.get("audit_offset") || "0") || 0);
  /** Phase 33 — append ?gzip=true to CSV/JSON/NDJSON downloads */
  const [auditExportGzip, setAuditExportGzip] = useState(false);
  /** Phase 34 — paged export ?offset=  and ?digest=true (SHA-256 header) */
  const [auditExportOffset, setAuditExportOffset] = useState("");
  const [auditExportAfterTs, setAuditExportAfterTs] = useState("");
  const [auditExportAfterId, setAuditExportAfterId] = useState("");
  const [auditExportDigest, setAuditExportDigest] = useState(false);
  const LOG_LIMIT = 60;
  const [expandedLogId, setExpandedLogId] = useState(null);
  const [summary, setSummary] = useState(null);
  const [runs, setRuns] = useState([]);
  const [resetting, setResetting] = useState(false);
  const [notifSettings, setNotifSettings] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [newWebhook, setNewWebhook] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [indexStatus, setIndexStatus] = useState(null);
  const [recalibrating, setRecalibrating] = useState(false);

  const [modelVersions, setModelVersions] = useState([]);
  const [training, setTraining] = useState(false);

  const load = async () => {
    const [m, p, s, r, ns, n, ix, mv] = await Promise.all([
      http.get("/admin/models"),
      http.get("/admin/prompts"),
      http.get("/admin/summary"),
      http.get("/admin/ingestion-runs"),
      http.get("/notifications/settings"),
      http.get("/notifications"),
      http.get("/copilot/index-status"),
      http.get("/admin/model-versions"),
    ]);
    setModels(m.data); setPrompts(p.data); setSummary(s.data); setRuns(r.data);
    setNotifSettings(ns.data); setNotifications(n.data); setIndexStatus(ix.data); setModelVersions(mv.data);
  };
  useEffect(() => { load(); }, []);

  const logQueryParams = useMemo(() => {
    const params = { limit: LOG_LIMIT, offset: logOffset };
    if (logQ.trim()) params.q = logQ.trim();
    if (logActor.trim()) params.actor = logActor.trim();
    if (logAction.trim()) params.action_type = logAction.trim();
    if (logObjectType.trim()) params.object_type = logObjectType.trim();
    if (logObjectId.trim()) params.object_id = logObjectId.trim();
    if (logSinceTs.trim()) params.since_ts = logSinceTs.trim();
    if (logUntilTs.trim()) params.until_ts = logUntilTs.trim();
    return params;
  }, [logQ, logActor, logAction, logObjectType, logObjectId, logSinceTs, logUntilTs, logOffset]);

  // Phase 20 — keep audit-log view shareable via URL params.
  useEffect(() => {
    if (tab !== "logs") return;
    setSp((prev) => {
      const n = new URLSearchParams(prev);
      const setOrDel = (k, v) => {
        if (v) n.set(k, v);
        else n.delete(k);
      };
      setOrDel("audit_q", logQ.trim());
      setOrDel("audit_actor", logActor.trim());
      setOrDel("audit_action", logAction.trim());
      setOrDel("audit_object_type", logObjectType.trim());
      setOrDel("audit_object_id", logObjectId.trim());
      setOrDel("audit_since_ts", logSinceTs.trim());
      setOrDel("audit_until_ts", logUntilTs.trim());
      if (logOffset) n.set("audit_offset", String(logOffset));
      else n.delete("audit_offset");
      return n;
    }, { replace: true });
  }, [tab, logQ, logActor, logAction, logObjectType, logObjectId, logSinceTs, logUntilTs, logOffset, setSp]);

  // Phase 31 — Governance / deep links: open Audit logs tab when URL carries audit_* query params.
  useEffect(() => {
    const p = new URLSearchParams(location.search);
    const forcedTab = (p.get("tab") || "").trim();
    if (forcedTab && forcedTab !== tab) {
      setTab(forcedTab);
    }
    if (!hasGovernanceAuditParams(p)) return;
    setTab("logs");
    setLogQ(p.get("audit_q") || "");
    setLogActor(p.get("audit_actor") || "");
    setLogAction(p.get("audit_action") || "");
    setLogObjectType(p.get("audit_object_type") || "");
    setLogObjectId(p.get("audit_object_id") || "");
    setLogSinceTs(p.get("audit_since_ts") || "");
    setLogUntilTs(p.get("audit_until_ts") || "");
    setLogOffset(Number(p.get("audit_offset") || "0") || 0);
  }, [location.search]);

  useEffect(() => {
    if (tab !== "logs") return;
    http
      .get("/admin/audit-logs/query", { params: logQueryParams })
      .then((r) => {
        setLogs(r.data.items || []);
        setLogsTotal(r.data.total || 0);
        setExpandedLogId(null);
      })
      .catch(() => toast.error("Failed to load audit logs"));
  }, [tab, logQueryParams]);

  const reseed = async () => {
    if (!window.confirm("Wipe all data and reseed?")) return;
    setResetting(true);
    try {
      await http.post("/admin/seed-reset");
      toast.success("Database reseeded + all controls re-run");
      await load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Reset failed"); }
    setResetting(false);
  };

  const saveNotifSettings = async (patch) => {
    const { data } = await http.patch("/notifications/settings", patch);
    setNotifSettings(data);
    toast.success("Notification settings saved");
  };

  const addWebhook = async () => {
    const url = newWebhook.trim();
    if (!url) return;
    const next = [...(notifSettings?.webhook_urls || []), url];
    await saveNotifSettings({ webhook_urls: next });
    setNewWebhook("");
  };
  const removeWebhook = async (url) => {
    await saveNotifSettings({ webhook_urls: notifSettings.webhook_urls.filter(u => u !== url) });
  };
  const addEmail = async () => {
    const email = newEmail.trim();
    if (!email) return;
    const next = [...(notifSettings?.email_recipients || []), email];
    await saveNotifSettings({ email_recipients: next });
    setNewEmail("");
  };
  const removeEmail = async (email) => {
    await saveNotifSettings({ email_recipients: notifSettings.email_recipients.filter(e => e !== email) });
  };
  const scanNow = async () => {
    const { data } = await http.post("/notifications/scan-sla");
    toast.message(`SLA scan: ${data.notified} notified / ${data.scanned} scanned`);
    await load();
  };
  const recalibrate = async () => {
    setRecalibrating(true);
    try {
      const { data } = await http.post("/anomaly/recalibrate");
      toast.success(`Recalibrated ${data.exceptions_recalibrated} exceptions`);
    } catch { toast.error("Recalibration failed"); }
    setRecalibrating(false);
  };
  const rebuildIndex = async () => {
    try {
      const { data } = await http.post("/copilot/rebuild-index");
      toast.success(`Vector index rebuilt · ${data.indexed_docs} docs`);
      await load();
    } catch { toast.error("Rebuild failed"); }
  };

  const trainModel = async () => {
    setTraining(true);
    try {
      const { data } = await http.post("/anomaly/train", { notes: "admin-ui trigger" });
      toast.success(`Trained ${data.version_label} · ${data.metrics.n_train} samples · anomaly rate ${(data.metrics.test_anomaly_rate * 100).toFixed(1)}%`);
      await load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Training failed"); }
    setTraining(false);
  };

  const approveVersion = async (id) => {
    try {
      await http.post(`/admin/model-versions/${id}/approve`);
      toast.success("Version approved and activated");
      await load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Approval failed"); }
  };

  const sendBriefNow = async () => {
    try {
      const { data } = await http.post("/notifications/daily-brief/send");
      if (data.skipped) toast.warning(`Skipped: ${data.skipped}`);
      else toast.success(`Daily brief dispatched · ${(data.dispatched_to || []).length} webhook(s)`);
      await load();
    } catch { toast.error("Brief dispatch failed"); }
  };

  const downloadScopedPack = async (format, filtersApplied) => {
    try {
      const resp = await http.get(`/reports/audit-committee-pack.${format}`, {
        params: filtersApplied || {},
        responseType: "blob",
      });
      const blob = new Blob([resp.data]);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `audit-committee-pack.${format}`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(`Downloaded ${format.toUpperCase()} pack`);
    } catch {
      toast.error(`Download ${format.toUpperCase()} failed`);
    }
  };

  const applyAuditExportTransportParams = (params) => {
    const o = Number.parseInt(auditExportOffset, 10);
    if (Number.isFinite(o) && o > 0) params.offset = o;
    if (auditExportGzip) params.gzip = true;
    if (auditExportDigest) params.digest = true;
  };

  const exportAuditLogsCsv = async () => {
    try {
      const params = {};
      if (logQ.trim()) params.q = logQ.trim();
      if (logActor.trim()) params.actor = logActor.trim();
      if (logAction.trim()) params.action_type = logAction.trim();
      if (logObjectType.trim()) params.object_type = logObjectType.trim();
      if (logObjectId.trim()) params.object_id = logObjectId.trim();
      if (logSinceTs.trim()) params.since_ts = logSinceTs.trim();
      if (logUntilTs.trim()) params.until_ts = logUntilTs.trim();
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
      toast.error(e?.response?.data?.detail || "CSV export failed");
    }
  };

  const exportAuditLogsJson = async () => {
    try {
      const params = {};
      if (logQ.trim()) params.q = logQ.trim();
      if (logActor.trim()) params.actor = logActor.trim();
      if (logAction.trim()) params.action_type = logAction.trim();
      if (logObjectType.trim()) params.object_type = logObjectType.trim();
      if (logObjectId.trim()) params.object_id = logObjectId.trim();
      if (logSinceTs.trim()) params.since_ts = logSinceTs.trim();
      if (logUntilTs.trim()) params.until_ts = logUntilTs.trim();
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
      toast.error(e?.response?.data?.detail || "JSON export failed");
    }
  };

  const exportAuditLogsNdjson = async () => {
    try {
      const params = {};
      if (logQ.trim()) params.q = logQ.trim();
      if (logActor.trim()) params.actor = logActor.trim();
      if (logAction.trim()) params.action_type = logAction.trim();
      if (logObjectType.trim()) params.object_type = logObjectType.trim();
      if (logObjectId.trim()) params.object_id = logObjectId.trim();
      if (logSinceTs.trim()) params.since_ts = logSinceTs.trim();
      if (logUntilTs.trim()) params.until_ts = logUntilTs.trim();
      applyAuditExportTransportParams(params);
      const resp = await http.get("/admin/audit-logs/export.ndjson", { params, responseType: "blob" });
      const blob = new Blob([resp.data], { type: auditExportGzip ? "application/gzip" : "application/x-ndjson" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = auditExportGzip ? "audit-logs.ndjson.gz" : "audit-logs.ndjson";
      a.click();
      URL.revokeObjectURL(url);
      toast.success(auditExportGzip ? "Downloaded audit logs NDJSON (gzip)" : "Downloaded audit logs NDJSON stream");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "NDJSON export failed");
    }
  };

  const masterHrefFromFiltersApplied = (pathname, filtersApplied) => {
    const fa = filtersApplied || {};
    const sp = new URLSearchParams();
    // Map server filter names → URL-synced master filter keys
    if (fa.entity_code) sp.set(MF_ENTITY, fa.entity_code);
    if (fa.period_ym) sp.set(MF_PERIOD, fa.period_ym);
    if (fa.department_id) sp.set(MF_DEPT, fa.department_id);
    if (fa.cost_center_id) sp.set(MF_CC, fa.cost_center_id);
    const qs = sp.toString();
    return qs ? `${pathname}?${qs}` : pathname;
  };

  return (
    <PageShell maxWidth="max-w-[1700px]">
      <div data-testid="admin-console">
        <PageHeader
          kicker="GOVERNANCE"
          title="Admin console"
          subtitle="Manage model registry, prompt governance, notifications, AI ops, audit logs, and ingestion runs."
          right={
            <button
              data-testid="reseed-btn"
              onClick={reseed}
              disabled={resetting}
              className="flex items-center gap-2 px-5 h-11 rounded-full bg-[#FF3B30]/10 border border-[#FF3B30]/40 text-xs font-mono uppercase tracking-wider text-[#FF3B30] hover:bg-[#FF3B30]/15 transition-colors disabled:opacity-50"
            >
              <ArrowsClockwise size={12} className={resetting ? "animate-spin" : ""} /> Reseed database
            </button>
          }
        />

      {summary && (
        <SectionCard kicker="SYSTEM" title="Collections" className="mb-6" bodyClassName="p-4">
          <div className="grid grid-cols-2 md:grid-cols-5 lg:grid-cols-11 gap-3" data-testid="collection-summary">
            {Object.entries(summary.collections).map(([k, v]) => (
              <div key={k} className="border border-[#262626] bg-[#0A0A0A]/55 backdrop-blur p-3 rounded-xl">
                <div className="font-mono text-[9px] uppercase tracking-wider text-[#737373] truncate">{k}</div>
                <div className="font-mono tabular-nums text-lg text-white mt-1">{v}</div>
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {/* Tabs */}
      <div className="flex flex-wrap gap-2 mb-6 w-fit">
        {[
          { k: "models", label: "Model registry", icon: Cpu },
          { k: "prompts", label: "Prompt governance", icon: ShieldCheck },
          { k: "notifications", label: "Notifications", icon: Bell },
          { k: "ai-ops", label: "AI Ops", icon: Sparkle },
          { k: "logs", label: "Audit logs", icon: Database },
          { k: "ingest", label: "Ingestion runs", icon: Database },
        ].map(t => (
          <button
            key={t.k}
            data-testid={`admin-tab-${t.k}`}
            onClick={() => setTab(t.k)}
            className={`flex items-center gap-2 px-5 h-11 text-xs font-mono uppercase tracking-wider transition-colors rounded-full ${
              tab === t.k ? "bg-white text-black" : "bg-[#141414]/70 text-[#A3A3A3] hover:bg-[#1F1F1F]/70 border border-[#262626]"
            }`}
          >
            <t.icon size={12} /> {t.label}
          </button>
        ))}
      </div>

      {/* Model registry */}
      {tab === "models" && (
        <SectionCard kicker="REGISTRY" title="Model registry" bodyClassName="p-0">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[70vh]" testId="admin-models-table">
            <DataTableHead>
              <tr>
                <DataTableTh>ID</DataTableTh>
                <DataTableTh>Model</DataTableTh>
                <DataTableTh>Use case</DataTableTh>
                <DataTableTh>Tier</DataTableTh>
                <DataTableTh>Approved by</DataTableTh>
                <DataTableTh>Status</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {models.map(m => (
                <DataTableRow key={m.id} testId={`model-row-${m.id}`}>
                  <DataTableTd className="font-mono text-xs text-[#A3A3A3]">{m.id}</DataTableTd>
                  <DataTableTd className="text-sm text-white font-mono">{m.provider}/{m.model_name}</DataTableTd>
                  <DataTableTd className="font-mono text-xs text-[#A3A3A3]">{m.use_case}</DataTableTd>
                  <DataTableTd className="font-mono text-xs uppercase">{m.governance_tier}</DataTableTd>
                  <DataTableTd className="text-xs text-[#A3A3A3]">{m.approved_by}</DataTableTd>
                  <DataTableTd><span className="font-mono text-[10px] uppercase tracking-wider text-[#30D158] bg-[#30D158]/10 px-2 py-0.5">{m.approval_status}</span></DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>
      )}

      {tab === "prompts" && (
        <SectionCard kicker="GOVERNANCE" title="Prompt governance" bodyClassName="p-0">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[70vh]" testId="admin-prompts-table">
            <DataTableHead>
              <tr>
                <DataTableTh>ID</DataTableTh>
                <DataTableTh>Name</DataTableTh>
                <DataTableTh>Version</DataTableTh>
                <DataTableTh>Template (excerpt)</DataTableTh>
                <DataTableTh>Approver</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {prompts.map(p => (
                <DataTableRow key={p.id} testId={`prompt-row-${p.id}`}>
                  <DataTableTd className="font-mono text-xs text-[#A3A3A3]">{p.id}</DataTableTd>
                  <DataTableTd className="text-sm text-white">{p.name}</DataTableTd>
                  <DataTableTd className="font-mono text-xs">v{p.version}</DataTableTd>
                  <DataTableTd className="text-xs text-[#A3A3A3] truncate max-w-md">{p.template}</DataTableTd>
                  <DataTableTd className="text-xs text-[#A3A3A3]">{p.approved_by}</DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>
      )}

      {tab === "logs" && (
        <SectionCard kicker="AUDIT" title="Audit logs" bodyClassName="p-0">
          <div className="border-b border-[#262626] p-4">
            <div className="flex flex-wrap items-end gap-3">
              <div>
                <div className="font-mono text-[10px] uppercase tracking-wider text-[#737373]">Search</div>
                <input
                  value={logQ}
                  onChange={(e) => { setLogOffset(0); setLogQ(e.target.value); }}
                  placeholder="actor/action/object…"
                  className="mt-1 h-9 w-[260px] rounded-sm border border-[#262626] bg-[#0A0A0A]/70 px-3 font-mono text-xs text-white outline-none focus:border-primary"
                />
              </div>
              <div>
                <div className="font-mono text-[10px] uppercase tracking-wider text-[#737373]">Actor</div>
                <input
                  value={logActor}
                  onChange={(e) => { setLogOffset(0); setLogActor(e.target.value); }}
                  placeholder="cfo@…"
                  className="mt-1 h-9 w-[220px] rounded-sm border border-[#262626] bg-[#0A0A0A]/70 px-3 font-mono text-xs text-white outline-none focus:border-primary"
                />
              </div>
              <div>
                <div className="font-mono text-[10px] uppercase tracking-wider text-[#737373]">Action</div>
                <input
                  value={logAction}
                  onChange={(e) => { setLogOffset(0); setLogAction(e.target.value); }}
                  placeholder="export_pdf"
                  className="mt-1 h-9 w-[180px] rounded-sm border border-[#262626] bg-[#0A0A0A]/70 px-3 font-mono text-xs text-white outline-none focus:border-primary"
                />
              </div>
              <div>
                <div className="font-mono text-[10px] uppercase tracking-wider text-[#737373]">Object type</div>
                <input
                  value={logObjectType}
                  onChange={(e) => { setLogOffset(0); setLogObjectType(e.target.value); }}
                  placeholder="report"
                  className="mt-1 h-9 w-[140px] rounded-sm border border-[#262626] bg-[#0A0A0A]/70 px-3 font-mono text-xs text-white outline-none focus:border-primary"
                />
              </div>
              <div>
                <div className="font-mono text-[10px] uppercase tracking-wider text-[#737373]">Object id</div>
                <input
                  value={logObjectId}
                  onChange={(e) => { setLogOffset(0); setLogObjectId(e.target.value); }}
                  placeholder="audit-committee-pack"
                  className="mt-1 h-9 w-[200px] rounded-sm border border-[#262626] bg-[#0A0A0A]/70 px-3 font-mono text-xs text-white outline-none focus:border-primary"
                />
              </div>
              <div>
                <div className="font-mono text-[10px] uppercase tracking-wider text-[#737373]">Since (ISO)</div>
                <input
                  value={logSinceTs}
                  onChange={(e) => { setLogOffset(0); setLogSinceTs(e.target.value); }}
                  placeholder="2026-05-01"
                  className="mt-1 h-9 w-[160px] rounded-sm border border-[#262626] bg-[#0A0A0A]/70 px-3 font-mono text-xs text-white outline-none focus:border-primary"
                />
              </div>
              <div>
                <div className="font-mono text-[10px] uppercase tracking-wider text-[#737373]">Until (ISO)</div>
                <input
                  value={logUntilTs}
                  onChange={(e) => { setLogOffset(0); setLogUntilTs(e.target.value); }}
                  placeholder="2026-05-31"
                  className="mt-1 h-9 w-[160px] rounded-sm border border-[#262626] bg-[#0A0A0A]/70 px-3 font-mono text-xs text-white outline-none focus:border-primary"
                />
              </div>
              <button
                type="button"
                onClick={() => { setLogOffset(0); setLogQ(""); setLogActor(""); setLogAction(""); setLogObjectType(""); setLogObjectId(""); setLogSinceTs(""); setLogUntilTs(""); }}
                className="h-9 rounded-sm border border-[#262626] bg-[#141414]/70 px-3 font-mono text-[10px] uppercase tracking-wider text-[#A3A3A3] hover:bg-[#1F1F1F]/70"
              >
                Clear
              </button>
              <label className="flex items-center gap-1.5 px-2 h-9 rounded-sm border border-[#262626] bg-[#141414]/70 font-mono text-[10px] uppercase tracking-wider text-[#A3A3A3] cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={auditExportGzip}
                  onChange={(e) => setAuditExportGzip(e.target.checked)}
                  className="rounded border-[#404040] bg-[#0A0A0A]/70"
                />
                Gzip
              </label>
              <div className="flex items-center gap-1" title="Skip N rows (ignored if cursor timestamps set)">
                <span className="font-mono text-[9px] uppercase text-[#737373]">Off</span>
                <input
                  type="number"
                  min={0}
                  value={auditExportOffset}
                  onChange={(e) => setAuditExportOffset(e.target.value)}
                  placeholder="0"
                  className="h-9 w-[72px] rounded-sm border border-[#262626] bg-[#0A0A0A]/70 px-2 font-mono text-xs text-white outline-none focus:border-primary"
                />
              </div>
              <div className="flex flex-wrap items-center gap-1" title="Phase 35 keyset cursor (paste from JSON export next_cursor)">
                <input
                  type="text"
                  value={auditExportAfterTs}
                  onChange={(e) => setAuditExportAfterTs(e.target.value)}
                  placeholder="after_ts"
                  className="h-9 w-[120px] rounded-sm border border-[#262626] bg-[#0A0A0A]/70 px-2 font-mono text-[10px] text-white outline-none focus:border-primary"
                />
                <input
                  type="text"
                  value={auditExportAfterId}
                  onChange={(e) => setAuditExportAfterId(e.target.value)}
                  placeholder="after_id"
                  className="h-9 w-[100px] rounded-sm border border-[#262626] bg-[#0A0A0A]/70 px-2 font-mono text-[10px] text-white outline-none focus:border-primary"
                />
              </div>
              <label
                className="flex items-center gap-1.5 px-2 h-9 rounded-sm border border-[#262626] bg-[#141414]/70 font-mono text-[10px] uppercase tracking-wider text-[#A3A3A3] cursor-pointer select-none"
                title="Response header X-Audit-Export-Sha256 over delivered bytes"
              >
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
                className="h-9 rounded-sm border border-[#262626] bg-[#141414]/70 px-3 font-mono text-[10px] uppercase tracking-wider text-[#A3A3A3] hover:bg-[#1F1F1F]/70"
                title="Phase 21 — export with auth"
              >
                Export CSV
              </button>
              <button
                type="button"
                onClick={exportAuditLogsJson}
                className="h-9 rounded-sm border border-[#262626] bg-[#141414]/70 px-3 font-mono text-[10px] uppercase tracking-wider text-[#A3A3A3] hover:bg-[#1F1F1F]/70"
                title="Phase 31 — JSON envelope + rows for archival / SIEM"
              >
                Export JSON
              </button>
              <button
                type="button"
                onClick={exportAuditLogsNdjson}
                className="h-9 rounded-sm border border-[#262626] bg-[#141414]/70 px-3 font-mono text-[10px] uppercase tracking-wider text-[#A3A3A3] hover:bg-[#1F1F1F]/70"
                title="Phase 32 — streamed NDJSON, one JSON object per line"
              >
                Export NDJSON
              </button>
              <button
                type="button"
                onClick={() => {
                  try {
                    navigator.clipboard.writeText(window.location.href);
                    toast.success("Copied permalink");
                  } catch {
                    toast.error("Copy failed");
                  }
                }}
                className="h-9 rounded-sm border border-[#262626] bg-[#141414]/70 px-3 font-mono text-[10px] uppercase tracking-wider text-[#A3A3A3] hover:bg-[#1F1F1F]/70"
                title="Phase 22 — share this audit-log view"
              >
                Copy link
              </button>
              <div className="ml-auto font-mono text-[10px] uppercase tracking-wider text-[#737373]">
                {logsTotal.toLocaleString()} total
              </div>
            </div>
          </div>
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[70vh]" testId="admin-audit-logs-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Timestamp</DataTableTh>
                <DataTableTh>Actor</DataTableTh>
                <DataTableTh>Action</DataTableTh>
                <DataTableTh>Object</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {logs.map((l) => (
                <React.Fragment key={l.id}>
                  <DataTableRow
                    testId={`log-${l.id}`}
                    onClick={() => setExpandedLogId((prev) => (prev === l.id ? null : l.id))}
                    className="cursor-pointer"
                  >
                    <DataTableTd className="font-mono text-xs text-[#A3A3A3]">{fmtDateTime(l.event_ts)}</DataTableTd>
                    <DataTableTd className="text-xs text-[#E5E5E5]">
                      {l.actor_user_email ? (
                        <Link
                          to={`/app/drill/user/${encodeURIComponent(l.actor_user_email)}`}
                          onClick={(e) => e.stopPropagation()}
                          className="font-mono text-[#0A84FF] hover:underline"
                        >
                          {l.actor_user_email}
                        </Link>
                      ) : (
                        "—"
                      )}
                    </DataTableTd>
                    <DataTableTd className="font-mono text-xs text-[#0A84FF]">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setLogOffset(0);
                          setLogAction(l.action_type || "");
                        }}
                        className="hover:underline"
                        title="Filter by this action"
                      >
                        {l.action_type}
                      </button>
                    </DataTableTd>
                    <DataTableTd className="font-mono text-xs text-[#A3A3A3]">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setLogOffset(0);
                          setLogObjectType(l.object_type || "");
                        }}
                        className="hover:underline"
                        title="Filter by this object type"
                      >
                        {l.object_type}
                      </button>
                      :{" "}
                      <span className="tabular-nums">{l.object_id?.slice(0, 20) || "—"}</span>
                      {l.object_type === "exception" && l.object_id ? (
                        <Link
                          to={`/app/evidence/${encodeURIComponent(l.object_id)}`}
                          onClick={(e) => e.stopPropagation()}
                          className="ml-2 text-[#0A84FF] hover:underline"
                        >
                          evidence
                        </Link>
                      ) : null}
                      <span className="ml-2 text-[#737373]">{expandedLogId === l.id ? "▾" : "▸"}</span>
                    </DataTableTd>
                  </DataTableRow>
                  {expandedLogId === l.id ? (
                    <DataTableRow testId={`log-detail-${l.id}`}>
                      <DataTableTd colSpan={4} className="bg-[#0A0A0A]/40 p-4">
                        <div className="flex flex-wrap items-center gap-2">
                          <div className="font-mono text-[10px] uppercase tracking-wider text-[#737373]">
                            Detail payload
                          </div>
                          {l?.detail?.filters_applied && Object.keys(l.detail.filters_applied).length > 0 ? (
                            <div className="flex flex-wrap items-center gap-2">
                              {Object.entries(l.detail.filters_applied).map(([k, v]) => (
                                <span
                                  key={`${l.id}-${k}`}
                                  className="inline-flex h-7 items-center rounded-sm border border-[#262626] bg-[#141414]/70 px-2 font-mono text-[10px] uppercase tracking-wider text-[#A3A3A3]"
                                  title="filters_applied"
                                >
                                  {k}={String(v)}
                                </span>
                              ))}
                              <Link
                                to={masterHrefFromFiltersApplied("/app/cfo", l.detail.filters_applied)}
                                onClick={(e) => e.stopPropagation()}
                                className="h-7 rounded-sm border border-[#262626] bg-[#141414]/70 px-2 font-mono text-[10px] uppercase tracking-wider text-[#0A84FF] hover:bg-[#1F1F1F]/70"
                                title="Open CFO cockpit with full reporting context"
                              >
                                Open CFO
                              </Link>
                              <Link
                                to={masterHrefFromFiltersApplied("/app/readiness", l.detail.filters_applied)}
                                onClick={(e) => e.stopPropagation()}
                                className="h-7 rounded-sm border border-[#262626] bg-[#141414]/70 px-2 font-mono text-[10px] uppercase tracking-wider text-[#0A84FF] hover:bg-[#1F1F1F]/70"
                                title="Open readiness matrix with full reporting context"
                              >
                                Open readiness
                              </Link>
                            </div>
                          ) : null}
                          {l.actor_user_email ? (
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setLogOffset(0);
                                setLogActor(l.actor_user_email);
                              }}
                              className="h-7 rounded-sm border border-[#262626] bg-[#141414]/70 px-2 font-mono text-[10px] uppercase tracking-wider text-[#A3A3A3] hover:bg-[#1F1F1F]/70"
                              title="Filter by this actor"
                            >
                              Actor
                            </button>
                          ) : null}
                          {(l.action_type === "export_pdf" || l.action_type === "export_xlsx") &&
                          l.object_type === "report" &&
                          String(l.object_id || "").includes("audit-committee-pack") ? (
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                const fa = l?.detail?.filters_applied || {};
                                const fmt = l.action_type === "export_pdf" ? "pdf" : "xlsx";
                                downloadScopedPack(fmt, fa);
                              }}
                              className="h-7 rounded-sm border border-[#262626] bg-[#141414]/70 px-2 font-mono text-[10px] uppercase tracking-wider text-[#A3A3A3] hover:bg-[#1F1F1F]/70"
                              title="Re-download using the same filters"
                            >
                              Replay export
                            </button>
                          ) : null}
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              try {
                                navigator.clipboard.writeText(JSON.stringify(l.detail || {}, null, 2));
                                toast.success("Copied detail JSON");
                              } catch {
                                toast.error("Copy failed");
                              }
                            }}
                            className="h-7 rounded-sm border border-[#262626] bg-[#141414]/70 px-2 font-mono text-[10px] uppercase tracking-wider text-[#A3A3A3] hover:bg-[#1F1F1F]/70"
                          >
                            Copy JSON
                          </button>
                          <Link
                            to={`/app/audit-log/${encodeURIComponent(l.id)}`}
                            onClick={(e) => e.stopPropagation()}
                            className="h-7 rounded-sm border border-[#262626] bg-[#141414]/70 px-2 font-mono text-[10px] uppercase tracking-wider text-[#0A84FF] hover:bg-[#1F1F1F]/70"
                            title="Phase 23 — open dedicated event page"
                          >
                            Open event
                          </Link>
                        </div>
                        <pre className="mt-3 max-h-[240px] overflow-auto rounded-sm border border-[#262626] bg-[#050505] p-3 font-mono text-[11px] leading-relaxed text-[#E5E5E5]">
                          {JSON.stringify(l.detail || {}, null, 2)}
                        </pre>
                      </DataTableTd>
                    </DataTableRow>
                  ) : null}
                </React.Fragment>
              ))}
            </DataTableBody>
          </DataTable>
          <div className="flex items-center justify-between border-t border-[#262626] p-3">
            <button
              type="button"
              onClick={() => setLogOffset((o) => Math.max(0, o - LOG_LIMIT))}
              disabled={logOffset === 0}
              className="h-9 rounded-sm border border-[#262626] bg-[#141414]/70 px-3 font-mono text-[10px] uppercase tracking-wider text-[#A3A3A3] hover:bg-[#1F1F1F]/70 disabled:opacity-50"
            >
              Prev
            </button>
            <div className="font-mono text-[10px] uppercase tracking-wider text-[#737373]">
              Showing {logOffset + 1}-{Math.min(logOffset + LOG_LIMIT, logsTotal)} of {logsTotal}
            </div>
            <button
              type="button"
              onClick={() => setLogOffset((o) => (o + LOG_LIMIT < logsTotal ? o + LOG_LIMIT : o))}
              disabled={logOffset + LOG_LIMIT >= logsTotal}
              className="h-9 rounded-sm border border-[#262626] bg-[#141414]/70 px-3 font-mono text-[10px] uppercase tracking-wider text-[#A3A3A3] hover:bg-[#1F1F1F]/70 disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </SectionCard>
      )}

      {tab === "ingest" && (
        <SectionCard kicker="INGESTION" title="Ingestion runs" bodyClassName="p-0">
          <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[70vh]" testId="admin-ingest-runs-table">
            <DataTableHead>
              <tr>
                <DataTableTh>Dataset</DataTableTh>
                <DataTableTh>Source</DataTableTh>
                <DataTableTh>User</DataTableTh>
                <DataTableTh align="right">Rows</DataTableTh>
                <DataTableTh>Status</DataTableTh>
                <DataTableTh>At</DataTableTh>
              </tr>
            </DataTableHead>
            <DataTableBody>
              {runs.length === 0 && (
                <DataTableRow>
                  <DataTableTd colSpan={6} className="p-6 text-center font-mono text-xs text-[#737373]">No ingestion runs yet. Upload a CSV from the Ingest page.</DataTableTd>
                </DataTableRow>
              )}
              {runs.map(r => (
                <DataTableRow key={r.id} testId={`run-${r.id}`}>
                  <DataTableTd className="font-mono text-xs text-white">{r.dataset}</DataTableTd>
                  <DataTableTd className="text-xs text-[#A3A3A3]">{r.source}</DataTableTd>
                  <DataTableTd className="text-xs text-[#A3A3A3]">
                    {r.user_email ? (
                      <Link to={`/app/drill/user/${encodeURIComponent(r.user_email)}`} className="text-[#0A84FF] hover:underline">
                        {r.user_email}
                      </Link>
                    ) : "—"}
                  </DataTableTd>
                  <DataTableTd align="right" className="font-mono tabular-nums">{r.rows_loaded}/{r.rows_read}</DataTableTd>
                  <DataTableTd className="font-mono text-[10px] uppercase tracking-wider" style={{ color: r.status === "success" ? "#30D158" : "#FF9F0A" }}>{r.status}</DataTableTd>
                  <DataTableTd className="font-mono text-xs text-[#737373]">{fmtDateTime(r.run_end)}</DataTableTd>
                </DataTableRow>
              ))}
            </DataTableBody>
          </DataTable>
        </SectionCard>
      )}

      {tab === "notifications" && notifSettings && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-px bg-[#262626] border border-[#262626]" data-testid="notifications-tab">
          <div className="bg-[#141414] p-5 lg:col-span-1">
            <h3 className="font-heading text-base text-white tracking-tight mb-4">SLA breach settings</h3>
            <div className="space-y-4">
              <label className="flex items-center justify-between gap-2">
                <span className="font-mono text-[10px] uppercase tracking-wider text-[#737373]">Enabled</span>
                <button
                  data-testid="toggle-notif-enabled"
                  onClick={() => saveNotifSettings({ enabled: !notifSettings.enabled })}
                  className={`relative w-10 h-5 transition-colors ${notifSettings.enabled ? "bg-[#30D158]" : "bg-[#262626]"}`}
                >
                  <span className={`absolute top-0.5 w-4 h-4 bg-white transition-all ${notifSettings.enabled ? "left-5" : "left-0.5"}`}></span>
                </button>
              </label>
              <div>
                <div className="font-mono text-[10px] uppercase tracking-wider text-[#737373] mb-2">Severity threshold</div>
                <select
                  data-testid="sla-threshold"
                  value={notifSettings.sla_breach_severity_threshold}
                  onChange={(e) => saveNotifSettings({ sla_breach_severity_threshold: e.target.value })}
                  className="w-full bg-[#0A0A0A] border border-[#262626] px-3 py-2 text-sm text-white outline-none focus:border-white"
                >
                  <option value="critical">Critical only</option>
                  <option value="high">High + Critical</option>
                  <option value="medium">Medium + High + Critical</option>
                </select>
              </div>
              <button
                data-testid="scan-sla-btn"
                onClick={scanNow}
                className="w-full py-2.5 bg-white text-black font-mono text-xs uppercase tracking-wider hover:bg-[#E5E5E5] transition-colors"
              >
                Scan SLA now
              </button>

              <div className="border-t border-[#262626] pt-4 mt-2">
                <label className="flex items-center justify-between gap-2 mb-3">
                  <span className="font-mono text-[10px] uppercase tracking-wider text-[#737373]">Daily CFO brief</span>
                  <button
                    data-testid="toggle-daily-brief"
                    onClick={() => saveNotifSettings({ daily_brief_enabled: !notifSettings.daily_brief_enabled })}
                    className={`relative w-10 h-5 transition-colors ${notifSettings.daily_brief_enabled ? "bg-[#30D158]" : "bg-[#262626]"}`}
                  >
                    <span className={`absolute top-0.5 w-4 h-4 bg-white transition-all ${notifSettings.daily_brief_enabled ? "left-5" : "left-0.5"}`}></span>
                  </button>
                </label>
                <div className="flex items-center gap-2 mb-3">
                  <span className="font-mono text-[10px] uppercase tracking-wider text-[#737373]">Send at</span>
                  <input
                    data-testid="daily-brief-hour"
                    type="number" min="0" max="23"
                    value={notifSettings.daily_brief_hour_utc || 8}
                    onChange={(e) => saveNotifSettings({ daily_brief_hour_utc: parseInt(e.target.value, 10) })}
                    className="flex-1 bg-[#0A0A0A] border border-[#262626] px-2 py-1 text-sm text-white outline-none focus:border-white font-mono"
                  />
                  <span className="font-mono text-[10px] text-[#737373]">:00 UTC</span>
                </div>
                <button
                  data-testid="send-brief-btn"
                  onClick={sendBriefNow}
                  className="w-full py-2 bg-[#0A84FF]/10 border border-[#0A84FF]/40 text-[#0A84FF] font-mono text-xs uppercase tracking-wider hover:bg-[#0A84FF]/20 transition-colors"
                >
                  Send daily brief now
                </button>
              </div>
            </div>
          </div>

          <div className="bg-[#141414] p-5">
            <h3 className="font-heading text-base text-white tracking-tight mb-4">Webhook URLs</h3>
            <div className="flex gap-2 mb-3">
              <input
                data-testid="webhook-input"
                value={newWebhook}
                onChange={e => setNewWebhook(e.target.value)}
                placeholder="https://hooks.example.com/..."
                className="flex-1 bg-[#0A0A0A] border border-[#262626] px-3 py-2 text-sm text-white outline-none focus:border-white"
              />
              <button onClick={addWebhook} data-testid="add-webhook-btn" className="px-3 bg-[#0A0A0A] border border-[#404040] hover:bg-[#1F1F1F] transition-colors">
                <Plus size={12} className="text-white" />
              </button>
            </div>
            <div className="space-y-1 max-h-80 overflow-y-auto">
              {(notifSettings.webhook_urls || []).map(url => (
                <div key={url} className="flex items-center justify-between gap-2 bg-[#0A0A0A] border border-[#262626] px-3 py-2">
                  <span className="font-mono text-xs text-[#A3A3A3] truncate">{url}</span>
                  <button onClick={() => removeWebhook(url)} className="text-[#FF3B30] hover:text-white"><Trash size={12} /></button>
                </div>
              ))}
              {(!notifSettings.webhook_urls || notifSettings.webhook_urls.length === 0) && (
                <div className="font-mono text-[10px] text-[#525252]">No webhooks configured.</div>
              )}
            </div>
          </div>

          <div className="bg-[#141414] p-5">
            <h3 className="font-heading text-base text-white tracking-tight mb-4">Email recipients <span className="font-mono text-[10px] text-[#FF9F0A] uppercase tracking-wider ml-2">stub · logs only</span></h3>
            <div className="flex gap-2 mb-3">
              <input
                data-testid="email-input"
                value={newEmail}
                onChange={e => setNewEmail(e.target.value)}
                placeholder="cfo@company.com"
                className="flex-1 bg-[#0A0A0A] border border-[#262626] px-3 py-2 text-sm text-white outline-none focus:border-white"
              />
              <button onClick={addEmail} data-testid="add-email-btn" className="px-3 bg-[#0A0A0A] border border-[#404040] hover:bg-[#1F1F1F] transition-colors">
                <Plus size={12} className="text-white" />
              </button>
            </div>
            <div className="space-y-1 max-h-80 overflow-y-auto">
              {(notifSettings.email_recipients || []).map(email => (
                <div key={email} className="flex items-center justify-between gap-2 bg-[#0A0A0A] border border-[#262626] px-3 py-2">
                  <span className="font-mono text-xs text-[#A3A3A3] truncate">{email}</span>
                  <button onClick={() => removeEmail(email)} className="text-[#FF3B30] hover:text-white"><Trash size={12} /></button>
                </div>
              ))}
              {(!notifSettings.email_recipients || notifSettings.email_recipients.length === 0) && (
                <div className="font-mono text-[10px] text-[#525252]">No email recipients. Wire Resend/SendGrid in /app/backend/app/notifier.py.</div>
              )}
            </div>
          </div>

          <div className="bg-[#141414] p-5 lg:col-span-3">
            <h3 className="font-heading text-base text-white tracking-tight mb-4">Recent notifications ({notifications.length})</h3>
            <DataTable className="rounded-xl border border-[#262626]/70 bg-[#0A0A0A]/25" maxHeightClassName="max-h-[50vh]" testId="admin-notifications-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>When</DataTableTh>
                  <DataTableTh>Event</DataTableTh>
                  <DataTableTh>Title</DataTableTh>
                  <DataTableTh>Dispatched</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {notifications.length === 0 && (
                  <DataTableRow>
                    <DataTableTd colSpan={4} className="p-6 text-center font-mono text-xs text-[#737373]">No notifications yet. Trigger SLA scan or wait for overdue cases.</DataTableTd>
                  </DataTableRow>
                )}
                {notifications.slice(0, 20).map(n => (
                  <DataTableRow key={n.id} testId={`notif-${n.id}`}>
                    <DataTableTd className="font-mono text-xs text-[#A3A3A3]">{fmtDateTime(n.created_at)}</DataTableTd>
                    <DataTableTd className="font-mono text-xs text-[#0A84FF]">{n.event_type}</DataTableTd>
                    <DataTableTd className="text-sm text-white truncate max-w-lg">{n.title}</DataTableTd>
                    <DataTableTd className="font-mono text-xs text-[#A3A3A3]">
                      {(n.dispatched_to || []).length} webhook · {n.email_stub_logged ? "email ✓" : "—"}
                    </DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          </div>
        </div>
      )}

      {tab === "ai-ops" && (
        <div className="space-y-px">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-px bg-[#262626] border border-[#262626]" data-testid="ai-ops-tab">
            <div className="bg-[#141414] p-6">
              <h3 className="font-heading text-base text-white tracking-tight mb-4">Copilot vector index</h3>
              <div className="font-mono text-xs text-[#A3A3A3] space-y-2 mb-4">
                <div>Algorithm: <span className="text-white">{indexStatus?.algorithm || "—"}</span></div>
                <div>Indexed docs: <span className="text-white tabular-nums">{indexStatus?.indexed_docs ?? "—"}</span></div>
                <div>Matrix: <span className="text-white tabular-nums">{indexStatus?.matrix_shape ? `${indexStatus.matrix_shape[0]} × ${indexStatus.matrix_shape[1]}` : "—"}</span></div>
              </div>
              <button
                data-testid="rebuild-index-btn"
                onClick={rebuildIndex}
                className="px-4 py-2 bg-[#0A0A0A] border border-[#404040] text-xs font-mono uppercase tracking-wider text-white hover:bg-[#1F1F1F] transition-colors"
              >
                Rebuild index
              </button>
            </div>
            <div className="bg-[#141414] p-6">
              <h3 className="font-heading text-base text-white tracking-tight mb-4">Anomaly model</h3>
              <div className="font-mono text-xs text-[#A3A3A3] space-y-2 mb-4">
                <div>Model: <span className="text-white">IsolationForest(n=80)</span></div>
                <div>Blend: <span className="text-white">60% iforest + 40% per-control z-score</span></div>
                <div>Governance: <span className="text-white">tier-1 · approved · auditor-registered</span></div>
              </div>
              <div className="flex gap-2">
                <button
                  data-testid="recalibrate-btn"
                  onClick={recalibrate}
                  disabled={recalibrating}
                  className="px-4 py-2 bg-[#0A0A0A] border border-[#404040] text-xs font-mono uppercase tracking-wider text-white hover:bg-[#1F1F1F] transition-colors disabled:opacity-50"
                >
                  {recalibrating ? "Recalibrating..." : "Recalibrate scores"}
                </button>
                <button
                  data-testid="train-model-btn"
                  onClick={trainModel}
                  disabled={training}
                  className="px-4 py-2 bg-white text-black text-xs font-mono uppercase tracking-wider hover:bg-[#E5E5E5] transition-colors disabled:opacity-50"
                >
                  {training ? "Training..." : "Train new version"}
                </button>
              </div>
            </div>
          </div>

          <div className="bg-[#141414] border border-[#262626]">
            <div className="p-5 border-b border-[#262626] flex items-center justify-between">
              <h3 className="font-heading text-base text-white tracking-tight">Model versions · M-002 (anomaly-iforest)</h3>
              <span className="font-mono text-[10px] uppercase tracking-wider text-[#737373]">{modelVersions.length} versions</span>
            </div>
            <DataTable className="rounded-none border-0 bg-transparent" maxHeightClassName="max-h-[55vh]" testId="admin-model-versions-table">
              <DataTableHead>
                <tr>
                  <DataTableTh>Version</DataTableTh>
                  <DataTableTh>Trained by</DataTableTh>
                  <DataTableTh>When</DataTableTh>
                  <DataTableTh align="right">Train / Test</DataTableTh>
                  <DataTableTh align="right">Anomaly rate</DataTableTh>
                  <DataTableTh>Status</DataTableTh>
                  <DataTableTh align="right">Action</DataTableTh>
                </tr>
              </DataTableHead>
              <DataTableBody>
                {modelVersions.length === 0 && (
                  <DataTableRow>
                    <DataTableTd colSpan={7} className="p-6 text-center font-mono text-xs text-[#737373]">No versions yet. Click &quot;Train new version&quot; above.</DataTableTd>
                  </DataTableRow>
                )}
                {modelVersions.map(v => (
                  <DataTableRow key={v.id} testId={`version-${v.version_label}`}>
                    <DataTableTd className="font-mono text-xs text-white">{v.version_label} {v.active && <span className="ml-2 font-mono text-[9px] uppercase tracking-wider text-[#30D158]">· active</span>}</DataTableTd>
                    <DataTableTd className="text-xs text-[#A3A3A3]">{v.trained_by}</DataTableTd>
                    <DataTableTd className="font-mono text-xs text-[#737373]">{fmtDateTime(v.created_at)}</DataTableTd>
                    <DataTableTd align="right" className="font-mono tabular-nums text-xs text-[#A3A3A3]">{v.metrics?.n_train}/{v.metrics?.n_test}</DataTableTd>
                    <DataTableTd align="right" className="font-mono tabular-nums text-xs" style={{ color: (v.metrics?.test_anomaly_rate || 0) > 0.1 ? "#FF9F0A" : "#30D158" }}>
                      {((v.metrics?.test_anomaly_rate || 0) * 100).toFixed(2)}%
                    </DataTableTd>
                    <DataTableTd><span className="font-mono text-[10px] uppercase tracking-wider px-2 py-0.5" style={{
                      color: v.approval_status === "approved" ? "#30D158" : "#FF9F0A",
                      background: v.approval_status === "approved" ? "rgba(48,209,88,0.1)" : "rgba(255,159,10,0.1)",
                    }}>{v.approval_status}</span></DataTableTd>
                    <DataTableTd align="right">
                      {v.approval_status !== "approved" && (
                        <button
                          data-testid={`approve-${v.version_label}`}
                          type="button"
                          onClick={(e) => { e.stopPropagation(); approveVersion(v.id); }}
                          className="px-3 py-1 bg-[#30D158]/10 border border-[#30D158]/40 text-[#30D158] text-xs font-mono uppercase tracking-wider hover:bg-[#30D158]/20 transition-colors"
                        >Approve & activate</button>
                      )}
                    </DataTableTd>
                  </DataTableRow>
                ))}
              </DataTableBody>
            </DataTable>
          </div>
        </div>
      )}
      </div>
    </PageShell>
  );
}
