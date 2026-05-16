import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { Plug, Plus, Heartbeat, ArrowsClockwise, Bug } from "@phosphor-icons/react";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";

const PROVIDERS = [
  { id: "sap", label: "SAP" },
  { id: "oracle_erp", label: "Oracle ERP" },
];

export default function ConnectorsConsole() {
  const [connectors, setConnectors] = useState([]);
  const [selected, setSelected] = useState(null);
  const [runs, setRuns] = useState([]);
  const [errors, setErrors] = useState([]);
  const [dqHealth, setDqHealth] = useState(null);
  const [schemaVals, setSchemaVals] = useState([]);

  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [provider, setProvider] = useState("sap");
  const [entityCode, setEntityCode] = useState("US-HQ");
  const [envKey, setEnvKey] = useState("");

  const load = async () => {
    const [c, h, sv] = await Promise.all([
      http.get("/connectors"),
      http.get("/dq/health"),
      http.get("/dq/schema-validations", { params: { limit: 200 } }),
    ]);
    setConnectors(c.data);
    setDqHealth(h.data);
    setSchemaVals(sv.data);
    if (!selected && c.data.length) setSelected(c.data[0]);
  };

  const loadSelected = async (conn) => {
    if (!conn?.id) return;
    const [r, e] = await Promise.all([
      http.get(`/connectors/${conn.id}/runs`),
      http.get(`/connectors/${conn.id}/errors`),
    ]);
    setRuns(r.data);
    setErrors(e.data);
  };

  useEffect(() => { load(); }, []); // eslint-disable-line
  useEffect(() => { if (selected) loadSelected(selected); }, [selected?.id]); // eslint-disable-line

  const create = async () => {
    setCreating(true);
    try {
      const { data } = await http.post("/connectors", {
        name: name || undefined,
        provider,
        config: { entity_code: entityCode },
        credentials_ref: envKey ? { kind: "env_ref", env_key: envKey } : { kind: "none" },
      });
      toast.success("Connector created");
      setName(""); setEnvKey("");
      await load();
      setSelected(data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Create failed");
    }
    setCreating(false);
  };

  const test = async () => {
    try {
      const { data } = await http.post(`/connectors/${selected.id}/test`);
      toast.success(data.health?.ok ? `OK: ${data.health.message}` : `FAIL: ${data.health.message}`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Test failed");
    }
  };

  const run = async (mode) => {
    try {
      await http.post(`/connectors/${selected.id}/${mode}`);
      toast.success(`${mode} started`);
      await loadSelected(selected);
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || `${mode} failed`);
    }
  };

  return (
    <PageShell maxWidth="max-w-[1600px]">
      <div data-testid="connectors-console">
        <PageHeader
          kicker="DATA TRUST"
          title="Connectors"
          icon={<Plug size={18} />}
          subtitle="Manage sources, run sync/backfill, and monitor schema validation + ingestion health."
        />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-8">
          <SectionCard className="lg:col-span-1" kicker="SOURCES" title="Connectors" bodyClassName="p-0">
            <div className="p-4 border-b border-[#262626]/70 flex items-center justify-between">
              <div className="font-mono text-[10px] uppercase text-[#737373]">Connectors</div>
              <button onClick={load} className="px-3 h-10 rounded-full border border-[#262626] bg-[#141414]/70 hover:bg-[#1F1F1F]/70 text-white" data-testid="connectors-refresh">
                <ArrowsClockwise size={14} />
              </button>
            </div>
            <div className="p-4 space-y-2">
              {connectors.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setSelected(c)}
                  className={`w-full text-left px-3 py-3 border rounded-xl transition-colors ${
                    selected?.id === c.id ? "border-white bg-[#0A0A0A]/55" : "border-[#262626] hover:bg-[#0A0A0A]/40"
                  }`}
                >
                  <div className="text-white text-sm">{c.name}</div>
                  <div className="text-[#737373] text-[10px] font-mono">{c.provider} · {c.status} · last={c.last_run_status || "—"}</div>
                </button>
              ))}
              {!connectors.length && <div className="text-xs text-[#737373] font-mono">No connectors yet.</div>}
            </div>

            <div className="p-4 border-t border-[#262626]/70">
              <div className="font-mono text-[10px] uppercase text-[#737373] mb-2">Add connector</div>
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" className="w-full mb-2 bg-[#141414]/70 backdrop-blur border border-[#404040] px-3 h-10 text-xs text-white rounded-xl" />
              <select value={provider} onChange={(e) => setProvider(e.target.value)} className="w-full mb-2 bg-[#141414]/70 backdrop-blur border border-[#404040] px-3 h-10 text-xs text-white rounded-xl">
                {PROVIDERS.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
              </select>
              <input value={entityCode} onChange={(e) => setEntityCode(e.target.value)} placeholder="Entity code (e.g. US-HQ)" className="w-full mb-2 bg-[#141414]/70 backdrop-blur border border-[#404040] px-3 h-10 text-xs text-white rounded-xl" />
              <input value={envKey} onChange={(e) => setEnvKey(e.target.value)} placeholder="Env key for secret (optional)" className="w-full mb-3 bg-[#141414]/70 backdrop-blur border border-[#404040] px-3 h-10 text-xs text-white rounded-xl" />
              <button disabled={creating} onClick={create} className="flex items-center gap-2 px-4 h-10 bg-white text-black text-xs font-mono uppercase disabled:opacity-40 rounded-full shadow-[0_18px_55px_rgba(255,255,255,0.08)]">
                <Plus size={14} /> Create
              </button>
            </div>
          </SectionCard>

          <SectionCard className="lg:col-span-2" kicker="MONITORING" title={selected ? selected.name : "Select a connector"}>
            {!selected ? (
              <div className="text-xs font-mono text-[#737373]">Select a connector.</div>
            ) : (
              <>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="text-[#737373] text-xs font-mono">{selected.provider} · entity {selected.config?.entity_code || "—"}</div>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={test} className="flex items-center gap-2 px-4 h-10 rounded-full border border-[#262626] bg-[#141414]/70 hover:bg-[#1F1F1F]/70 text-xs font-mono uppercase text-white">
                      <Heartbeat size={14} /> Test
                    </button>
                    <button onClick={() => run("sync")} className="flex items-center gap-2 px-4 h-10 rounded-full border border-[#0A84FF] bg-[#0A84FF]/10 hover:bg-[#0A84FF]/15 text-xs font-mono uppercase text-[#0A84FF]">
                      <ArrowsClockwise size={14} /> Sync
                    </button>
                    <button onClick={() => run("backfill")} className="flex items-center gap-2 px-4 h-10 rounded-full border border-[#FF9F0A] bg-[#FF9F0A]/10 hover:bg-[#FF9F0A]/15 text-xs font-mono uppercase text-[#FF9F0A]">
                      Backfill
                    </button>
                  </div>
                </div>

                <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <div className="border border-[#262626] p-3 bg-[#0A0A0A]/55 backdrop-blur rounded-xl">
                    <div className="font-mono text-[10px] uppercase text-[#737373] mb-2">Run history</div>
                    <pre className="text-[10px] text-[#A3A3A3] overflow-x-auto max-h-72">{JSON.stringify(runs.slice(0, 10), null, 2)}</pre>
                  </div>
                  <div className="border border-[#262626] p-3 bg-[#0A0A0A]/55 backdrop-blur rounded-xl">
                    <div className="font-mono text-[10px] uppercase text-[#737373] mb-2 flex items-center gap-1"><Bug size={12} /> Errors</div>
                    <div className="mb-2 font-mono text-[10px] uppercase">
                      <Link to="/app/evidence" className="text-[#0A84FF] hover:underline">Open evidence explorer →</Link>
                    </div>
                    <pre className="text-[10px] text-[#A3A3A3] overflow-x-auto max-h-72">{JSON.stringify(errors.slice(0, 10), null, 2)}</pre>
                  </div>
                </div>

                <div className="mt-6 border border-[#262626] p-3 bg-[#0A0A0A]/55 backdrop-blur rounded-xl">
                  <div className="font-mono text-[10px] uppercase text-[#737373] mb-2">Schema validations (recent)</div>
                  <pre className="text-[10px] text-[#A3A3A3] overflow-x-auto max-h-64">{JSON.stringify(schemaVals.slice(0, 20), null, 2)}</pre>
                </div>

                <div className="mt-6 border border-[#262626] p-3 bg-[#0A0A0A]/55 backdrop-blur rounded-xl">
                  <div className="font-mono text-[10px] uppercase text-[#737373] mb-2">Ingestion health</div>
                  <pre className="text-[10px] text-[#A3A3A3] overflow-x-auto max-h-64">{JSON.stringify(dqHealth, null, 2)}</pre>
                </div>
              </>
            )}
          </SectionCard>
        </div>
      </div>
    </PageShell>
  );
}

