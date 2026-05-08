import React, { useEffect, useRef, useState } from "react";
import { http } from "../lib/api";
import { toast } from "sonner";
import { PaperPlaneRight, Sparkle, Warning, CheckCircle } from "@phosphor-icons/react";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";

const SUGGESTED = [
  "Why did audit readiness decline this week?",
  "Which three issues most threaten close?",
  "Summarize the top duplicate-payment exposures.",
  "Show open SoD conflicts by entity.",
  "Draft an audit committee note on our AP controls.",
  "Summarize high risks from the RACM for our statutory engagement.",
  "What control improvements would reduce fraud risk in procure-to-pay?",
  "Draft bullet points for a management letter on revenue cut-off.",
];

export default function Copilot() {
  const [sessions, setSessions] = useState([]);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const boxRef = useRef(null);

  const loadSessions = async () => {
    const { data } = await http.get("/copilot/sessions");
    setSessions(data);
  };
  useEffect(() => { loadSessions(); }, []);

  useEffect(() => {
    if (boxRef.current) boxRef.current.scrollTop = boxRef.current.scrollHeight;
  }, [sessions]);

  const ask = async (q) => {
    const question_text = (q || question).trim();
    if (!question_text) return;
    setAsking(true);
    setQuestion("");
    // Optimistic insert
    const tempId = `tmp-${Date.now()}`;
    setSessions(s => [{ id: tempId, question: question_text, answer: "", citations: [], confidence: 0, needs_human_review: false, model: "gemini/...", created_at: new Date().toISOString(), pending: true }, ...s]);
    try {
      const { data } = await http.post("/copilot/ask", { question: question_text, session_id: sessionId });
      setSessionId(data.session_id);
      setSessions(s => s.filter(x => x.id !== tempId));
      await loadSessions();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Copilot failed");
      setSessions(s => s.filter(x => x.id !== tempId));
    }
    setAsking(false);
  };

  return (
    <div className="h-full flex flex-col" data-testid="copilot-page">
      <div className="border-b border-zinc-200 bg-white/90 backdrop-blur-xl dark:border-zinc-800 dark:bg-zinc-950/80">
        <PageShell maxWidth="max-w-[1800px]">
          <PageHeader
            kicker="AI COPILOT · GOVERNED"
            title="Audit copilot"
            icon={<Sparkle size={18} weight="fill" className="text-primary" />}
            subtitle={
              <>
                RAG over controls, findings, evidence, and policies ·{" "}
                <span className="crt-num text-primary">gemini/gemini-3-flash-preview</span>
              </>
            }
          />
        </PageShell>
      </div>

      <div className="flex min-h-0 flex-1 overflow-hidden">
        {/* Messages */}
        <div ref={boxRef} className="beam-border relative min-h-0 flex-1 overflow-y-auto">
          <PageShell maxWidth="max-w-[1800px]">
          {sessions.length === 0 && (
            <div className="max-w-2xl">
              <div className="crt-overline mb-4 text-muted-foreground">Suggested prompts</div>
              <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                {SUGGESTED.map((s, i) => (
                  <button
                    key={i}
                    type="button"
                    data-testid={`suggested-${i}`}
                    onClick={() => ask(s)}
                    className="rounded-sm border border-zinc-200 bg-zinc-50/90 p-4 text-left text-sm text-zinc-800 transition-colors hover:border-zinc-300 hover:bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-900/50 dark:text-zinc-100 dark:hover:border-zinc-700 dark:hover:bg-zinc-900"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          <div className="space-y-6 max-w-4xl">
            {sessions.map(s => <Message key={s.id} s={s} />)}
          </div>
          </PageShell>
        </div>
      </div>

      {/* Input */}
      <div
        className="border-t border-zinc-200 bg-white/95 backdrop-blur-xl dark:border-zinc-800 dark:bg-zinc-950/90"
        data-testid="copilot-input-area"
      >
        <PageShell maxWidth="max-w-[1800px]">
          <SectionCard kicker="PROMPT" title="Ask a question" bodyClassName="p-4">
            <form onSubmit={(e) => { e.preventDefault(); ask(); }} className="flex max-w-4xl gap-2">
              <input
                data-testid="copilot-question"
                value={question}
                onChange={e => setQuestion(e.target.value)}
                placeholder="Ask about controls, exposure, cases, policies…"
                className="font-body h-11 min-w-0 flex-1 rounded-sm border border-zinc-300 bg-white px-4 text-sm text-foreground placeholder:text-zinc-400 outline-none focus:border-primary focus:ring-1 focus:ring-primary dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100 dark:placeholder:text-zinc-500"
              />
              <button
                data-testid="copilot-submit-btn"
                type="submit"
                disabled={asking || !question.trim()}
                className="crt-num flex h-11 shrink-0 items-center gap-2 rounded-sm border border-primary bg-primary px-6 text-xs font-medium uppercase tracking-wider text-white transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {asking ? "Thinking..." : <>Ask <PaperPlaneRight size={12} weight="fill" /></>}
              </button>
            </form>
            <div className="crt-num mt-2 max-w-4xl text-[10px] uppercase tracking-wider text-muted-foreground">
              All prompts and responses are logged · material conclusions require human review
            </div>
          </SectionCard>
        </PageShell>
      </div>
    </div>
  );
}

function Message({ s }) {
  return (
    <div className="fade-up">
      {/* user question */}
      <div className="mb-3 flex gap-3">
        <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-sm border border-zinc-300 bg-zinc-100 font-mono text-xs text-zinc-800 dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100">
          Q
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-sm text-foreground">{s.question}</div>
          <div className="crt-num mt-1 text-[10px] text-muted-foreground">{new Date(s.created_at).toLocaleTimeString()}</div>
        </div>
      </div>

      {/* answer */}
      <div className="ml-4 flex gap-3 border-l border-zinc-200 pl-4 dark:border-zinc-700">
        <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-sm bg-primary font-mono text-xs text-white">
          <Sparkle size={10} weight="fill" />
        </div>
        <div className="min-w-0 flex-1">
          {s.pending ? (
            <div className="crt-num text-xs italic text-muted-foreground">analyzing context…</div>
          ) : (
            <>
              <div className="whitespace-pre-wrap text-sm leading-relaxed text-zinc-800 dark:text-zinc-200">{s.answer}</div>
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <ConfidenceBadge value={s.confidence} />
                {s.needs_human_review && (
                  <span className="crt-num flex items-center gap-1 text-[10px] uppercase tracking-wider text-[hsl(var(--chart-3))]">
                    <Warning size={12} /> Human review required
                  </span>
                )}
                <span className="crt-num text-[9px] uppercase tracking-wider text-muted-foreground">{s.model}</span>
              </div>
              {s.citations && s.citations.length > 0 && (
                <div className="mt-3 rounded-sm border border-zinc-200 bg-zinc-50/90 p-3 dark:border-zinc-800 dark:bg-zinc-900/50">
                  <div className="crt-num mb-2 text-[10px] uppercase tracking-[0.1em] text-muted-foreground">Sources ({s.citations.length})</div>
                  <div className="space-y-1">
                    {s.citations.slice(0, 8).map((c, i) => (
                      <div key={i} className="flex items-start gap-2 text-xs">
                        <span className="crt-num w-6 shrink-0 text-primary">[#{i + 1}]</span>
                        <div className="min-w-0">
                          <div className="crt-num text-[10px] uppercase tracking-wider text-muted-foreground">{c.source_type}</div>
                          <div className="truncate text-foreground">{c.label}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function ConfidenceBadge({ value }) {
  const pct = Math.round((value || 0) * 100);
  const color =
    pct >= 80 ? "hsl(var(--chart-4))" : pct >= 60 ? "hsl(var(--chart-3))" : "hsl(var(--destructive))";
  return (
    <span className="crt-num flex items-center gap-1 text-[10px] uppercase tracking-wider" style={{ color }}>
      <CheckCircle size={12} /> confidence {pct}%
    </span>
  );
}
