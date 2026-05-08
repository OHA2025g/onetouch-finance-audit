import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { http } from "../lib/api";
import { toast } from "sonner";
import { SectionCard } from "../components/PageShell";
import { Folder, FileText, Plus } from "@phosphor-icons/react";

const FOLDER_ORDER = [
  "Planning",
  "Risk Assessment",
  "Financial Statements",
  "Controls Testing",
  "Substantive Testing",
  "Compliance",
  "Reporting",
];

function sortFolders(folders) {
  const idx = (n) => {
    const i = FOLDER_ORDER.indexOf(n);
    return i === -1 ? 999 : i;
  };
  return [...(folders || [])].sort((a, b) => idx(a.name) - idx(b.name));
}

export default function WorkingPapersHubPage() {
  const { engagementId } = useParams();
  const eid = decodeURIComponent(engagementId || "");
  const [folders, setFolders] = useState([]);
  const [papers, setPapers] = useState([]);
  const [selectedFolderId, setSelectedFolderId] = useState(null);
  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newBody, setNewBody] = useState("");
  const [newRefs, setNewRefs] = useState("");

  const load = useCallback(async () => {
    const { data } = await http.get(`/audit-engagements/${encodeURIComponent(eid)}/working-papers`);
    const f = sortFolders(data.folders || []);
    setFolders(f);
    setPapers(data.working_papers || []);
    setSelectedFolderId((prev) => prev || f[0]?.id || null);
  }, [eid]);

  useEffect(() => {
    if (!eid) return;
    load().catch(() => toast.error("Failed to load working papers"));
  }, [eid, load]);

  const folderById = useMemo(() => Object.fromEntries(folders.map((f) => [f.id, f])), [folders]);

  const filteredPapers = useMemo(() => {
    if (!selectedFolderId) return papers;
    return papers.filter((p) => p.folder_id === selectedFolderId);
  }, [papers, selectedFolderId]);

  const ensureFolders = async () => {
    try {
      await http.post(`/audit-engagements/${encodeURIComponent(eid)}/working-papers/folders`);
      await load();
      toast.success("Folders ready");
    } catch {
      toast.error("Could not seed folders");
    }
  };

  const createPaper = async (e) => {
    e.preventDefault();
    if (!selectedFolderId || !newTitle.trim()) {
      toast.error("Select a folder and enter a title");
      return;
    }
    const refLines = newRefs.split("\n").map((s) => s.trim()).filter(Boolean);
    const references = refLines.map((line) => {
      const [code, ...rest] = line.split(/\s+—\s+|\s+-\s+/);
      return { ref_code: code?.trim() || line, description: rest.join(" — ").trim() || null };
    });
    setCreating(true);
    try {
      await http.post("/working-papers", {
        engagement_id: eid,
        folder_id: selectedFolderId,
        title: newTitle.trim(),
        body: newBody.trim() || null,
        references,
        linked_risk_ids: [],
        linked_control_ids: [],
        linked_case_ids: [],
        evidence_ids: [],
      });
      setNewTitle("");
      setNewBody("");
      setNewRefs("");
      await load();
      toast.success("Working paper created");
    } catch {
      toast.error("Create failed");
    } finally {
      setCreating(false);
    }
  };

  const base = `/app/audit-planning/engagements/${encodeURIComponent(eid)}/working-papers`;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      <div className="lg:col-span-4 space-y-4">
        <SectionCard kicker="FILE" title="Folder tree" bodyClassName="p-4">
          <button
            type="button"
            onClick={ensureFolders}
            className="mb-4 w-full px-3 h-9 border border-[#262626] text-xs font-mono uppercase text-[#A3A3A3] hover:text-white"
          >
            Ensure CA folders
          </button>
          <ul className="space-y-1 text-sm">
            {folders.map((f) => (
              <li key={f.id}>
                <button
                  type="button"
                  onClick={() => setSelectedFolderId(f.id)}
                  className={`w-full text-left px-3 py-2 flex items-center gap-2 border ${
                    selectedFolderId === f.id ? "border-white text-white" : "border-[#262626] text-[#A3A3A3] hover:text-white"
                  }`}
                >
                  <Folder size={18} className="shrink-0 opacity-80" />
                  <span>{f.name}</span>
                </button>
              </li>
            ))}
          </ul>
        </SectionCard>
      </div>
      <div className="lg:col-span-8 space-y-4">
        <SectionCard
          kicker="NEW WP"
          title="Create working paper"
          right={<span className="font-mono text-[10px] text-[#737373]">Refs e.g. WP-REV-001 — Revenue analytical</span>}
          bodyClassName="p-4 space-y-3"
        >
          <form onSubmit={createPaper} className="space-y-3">
            <div>
              <label className="block font-mono text-[10px] uppercase text-[#737373] mb-1">Folder</label>
              <select
                value={selectedFolderId || ""}
                onChange={(ev) => setSelectedFolderId(ev.target.value)}
                className="w-full bg-black border border-[#262626] px-3 py-2 text-sm text-white"
              >
                {folders.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block font-mono text-[10px] uppercase text-[#737373] mb-1">Title</label>
              <input
                value={newTitle}
                onChange={(ev) => setNewTitle(ev.target.value)}
                className="w-full bg-black border border-[#262626] px-3 py-2 text-sm text-white"
                placeholder="e.g. Revenue — cut-off procedures"
              />
            </div>
            <div>
              <label className="block font-mono text-[10px] uppercase text-[#737373] mb-1">Procedure / conclusions (body)</label>
              <textarea
                value={newBody}
                onChange={(ev) => setNewBody(ev.target.value)}
                rows={4}
                className="w-full bg-black border border-[#262626] px-3 py-2 text-sm text-white font-mono"
              />
            </div>
            <div>
              <label className="block font-mono text-[10px] uppercase text-[#737373] mb-1">Cross-references (one per line)</label>
              <textarea
                value={newRefs}
                onChange={(ev) => setNewRefs(ev.target.value)}
                rows={3}
                placeholder={"WP-REV-001 — Tie to TB\nTB-AR-03"}
                className="w-full bg-black border border-[#262626] px-3 py-2 text-sm text-white font-mono"
              />
            </div>
            <button
              type="submit"
              disabled={creating}
              className="inline-flex items-center gap-2 px-4 h-10 bg-white text-black font-mono text-xs uppercase disabled:opacity-50"
            >
              <Plus size={16} weight="bold" /> Create &amp; allocate ref
            </button>
          </form>
        </SectionCard>

        <SectionCard kicker="INDEX" title="Working papers in folder" bodyClassName="p-0">
          <ul className="divide-y divide-[#262626]">
            {filteredPapers.length === 0 ? (
              <li className="px-4 py-6 text-sm text-[#737373]">No papers in this folder yet.</li>
            ) : (
              filteredPapers.map((p) => (
                <li key={p.id}>
                  <Link
                    to={`${base}/${encodeURIComponent(p.id)}`}
                    className="flex items-start gap-3 px-4 py-3 hover:bg-[#141414] text-left"
                  >
                    <FileText size={20} className="text-[#737373] shrink-0 mt-0.5" />
                    <div className="min-w-0 flex-1">
                      <div className="text-white text-sm">{p.title}</div>
                      <div className="font-mono text-[10px] text-[#0A84FF] mt-1">{p.reference}</div>
                      <div className="font-mono text-[10px] text-[#737373] mt-0.5">
                        {folderById[p.folder_id]?.name || p.folder_id}
                      </div>
                    </div>
                  </Link>
                </li>
              ))
            )}
          </ul>
        </SectionCard>
      </div>
    </div>
  );
}
