import React from "react";
import { Link } from "react-router-dom";
import { useTheme } from "../lib/theme";
import {
  Lightning,
  ShieldCheck,
  Scales,
  Graph,
  ChatCircleDots,
  ListChecks,
  UploadSimple,
  Eye,
  ArrowRight,
  Sparkle,
  Sun,
  Moon,
} from "@phosphor-icons/react";

const FEATURES = [
  {
    title: "Continuous Controls Monitoring",
    desc:
      "Run controls across 100% of transactions (P2P, R2R, O2C, Payroll, Treasury, Tax, Fixed Assets) and detect exceptions early — before audit fieldwork.",
    icon: ShieldCheck,
  },
  {
    title: "Evidence Explorer",
    desc:
      "Trace the end-to-end record chain behind an exception (PO → GRN → Invoice → Payment, Journal lineage, access events) with drill-downs you can defend.",
    icon: Graph,
  },
  {
    title: "Case Management + SLA",
    desc:
      "Convert exceptions into remediation cases with priorities, owners, comments, status history, and SLA monitoring so nothing slips.",
    icon: ListChecks,
  },
  {
    title: "AI Copilot (RAG)",
    desc:
      "Ask questions across controls, exceptions, policies, and cases. Get grounded answers with sources so teams can move fast with confidence.",
    icon: ChatCircleDots,
  },
  {
    title: "Audit Workspace",
    desc:
      "An auditor-first view to plan, test, and document findings across controls and entities with consistency and traceability.",
    icon: Scales,
  },
  {
    title: "Entity Rollups (CFO-ready)",
    desc:
      "Roll up readiness, exposure, control failure rate, repeat findings, SLA health, and evidence completeness across your org hierarchy — with drill-downs.",
    icon: Graph,
  },
  {
    title: "Governance: WORM + Legal Hold",
    desc:
      "Close cases into immutable WORM-protected records, apply legal holds to preserve evidence, and surface governance badges across cases and evidence.",
    icon: ShieldCheck,
  },
  {
    title: "Approvals (Policy-driven)",
    desc:
      "Approval-gate sensitive operations like connector activation, retention changes, legal-hold release, and copilot index rebuilds — with a unified queue.",
    icon: Scales,
  },
  {
    title: "Connectors + Data Quality",
    desc:
      "Pluggable connector runs (SAP/Oracle mock today) with run history, schema validation, ingestion health, and errors — built for data trust workflows.",
    icon: UploadSimple,
  },
  {
    title: "External Auditor Portal",
    desc:
      "Provide a clean auditor pack and evidence access with role-based guardrails — built for read-only review workflows.",
    icon: Eye,
  },
];

const USE_CASES = [
  {
    title: "CFO / Finance Leadership",
    points: [
      "Audit readiness, exposure, and remediation progress in one cockpit",
      "Board-ready pack exports and trend visibility across entities",
      "Prioritize what matters (high materiality + repeat findings)",
    ],
  },
  {
    title: "Controller / Close Owners",
    points: [
      "Detect and resolve close-impacting exceptions earlier",
      "Reduce rework with evidence-linked remediation tasks",
      "Prove controls are operating across the population",
    ],
  },
  {
    title: "Internal Audit",
    points: [
      "Continuous auditing posture rather than point-in-time sampling",
      "Standardized exception → case workflow with audit trails",
      "Drill-down support for walkthroughs and testing evidence",
    ],
  },
  {
    title: "Compliance / SoD",
    points: [
      "Access/SoD monitoring with documented actions and ownership",
      "Policy-aligned narratives and governance visibility",
      "Preparation for regulatory and external assurance reviews",
    ],
  },
  {
    title: "External Auditors",
    points: [
      "Read-only auditor pack + evidence explorer for substantiation",
      "Consistent, traceable data lineage for testing",
      "Faster requests, fewer back-and-forths",
    ],
  },
];

function Pill({ children }) {
  return (
    <span className="inline-flex items-center gap-2 px-3 h-8 rounded-full border border-border bg-white/70 backdrop-blur font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground dark:bg-card/70">
      {children}
    </span>
  );
}

export default function Landing() {
  const { theme, toggle } = useTheme();
  return (
    <div className="min-h-screen bg-background text-foreground wow-bg">
      {/* Top nav */}
      <header className="sticky top-0 z-20 border-b border-border bg-background/60 backdrop-blur-xl">
        <div className="max-w-[1200px] mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-md bg-primary text-primary-foreground flex items-center justify-center shadow-[0_10px_24px_rgba(0,0,0,0.08)]">
              <Lightning size={16} weight="fill" />
            </div>
            <div className="leading-none">
              <div className="font-heading text-sm tracking-tight">OneTouch Audit AI</div>
              <div className="font-mono text-[9px] uppercase tracking-[0.18em] text-muted-foreground">
                continuous assurance
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={toggle}
              title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
              aria-label="Toggle theme"
              data-testid="landing-theme-toggle"
              className="flex items-center gap-2 px-3 h-9 rounded-full border border-border bg-white/70 hover:bg-white/90 transition-colors font-mono text-[10px] uppercase tracking-[0.15em] text-foreground dark:bg-card/70 dark:hover:bg-card/85"
            >
              {theme === "dark" ? <Sun size={13} weight="regular" /> : <Moon size={13} weight="regular" />}
              <span>{theme === "dark" ? "light" : "dark"}</span>
            </button>
            <Link
              to="/login"
              className="px-3 h-9 inline-flex items-center rounded-full border border-border bg-white/70 hover:bg-white/90 transition-colors font-mono text-[10px] uppercase tracking-[0.15em] text-foreground dark:bg-card/70 dark:hover:bg-card/85"
              data-testid="landing-signin"
            >
              Sign in
            </Link>
            <Link
              to="/login"
              className="px-3 h-9 inline-flex items-center gap-2 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 transition-colors font-mono text-[10px] uppercase tracking-[0.15em] shadow-[0_14px_40px_rgba(0,0,0,0.10)]"
              data-testid="landing-demo"
            >
              Demo login <ArrowRight size={12} />
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-grid opacity-[0.22] dark:opacity-15" />
        <div className="max-w-[1200px] mx-auto px-6 py-16 lg:py-20 relative">
          <div className="flex flex-wrap items-center gap-2 mb-6">
            <Pill>
              <span className="w-1.5 h-1.5 bg-[#30D158] pulse-dot" /> system · live
            </Pill>
            <Pill>population testing</Pill>
            <Pill>evidence-first</Pill>
            <Pill>governed AI</Pill>
            <span className="wow-badge px-3 h-8 inline-flex items-center font-mono text-[10px] uppercase tracking-[0.15em] text-muted-foreground">
              approvals · WORM · legal hold
            </span>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-start">
            <div className="lg:col-span-7">
              <h1 className="font-heading text-5xl lg:text-6xl tracking-tight leading-[1.02]">
                Know if you’re audit-ready.
                <br />
                <span className="text-muted-foreground">In one touch.</span>
              </h1>
              <p className="mt-6 text-muted-foreground text-base lg:text-lg leading-relaxed max-w-2xl">
                Continuous assurance for finance. Monitor controls across the full population, convert exceptions into
                evidence-backed cases, and govern every sensitive action with approvals, legal hold, and WORM protection.
              </p>
              <div className="mt-8 flex flex-wrap gap-2">
                <Link
                  to="/login"
                  className="inline-flex items-center gap-2 px-5 h-11 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 transition-colors font-mono text-xs uppercase tracking-[0.15em] shadow-[0_18px_55px_rgba(0,0,0,0.10)]"
                >
                  Enter the app <ArrowRight size={14} />
                </Link>
                <a
                  href="#features"
                  className="inline-flex items-center px-5 h-11 rounded-full border border-border bg-white/70 hover:bg-white/90 transition-colors font-mono text-xs uppercase tracking-[0.15em] text-foreground dark:bg-card/70 dark:hover:bg-card/85"
                >
                  Explore features
                </a>
              </div>
              <div className="mt-10 grid grid-cols-3 gap-px bg-border border border-border max-w-xl rounded-2xl overflow-hidden">
                {[
                  { k: "Exception → case flow", v: "built-in" },
                  { k: "Governance", v: "WORM + holds" },
                  { k: "Rollups", v: "org-wide" },
                ].map((s) => (
                  <div key={s.k} className="bg-card/70 p-4 backdrop-blur">
                    <div className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">{s.k}</div>
                    <div className="font-mono tabular-nums text-xl mt-1">{s.v}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="lg:col-span-5">
              <div className="wow-ring wow-card p-6 beam-border">
                <div className="flex items-center gap-2 mb-3">
                  <Sparkle size={14} weight="fill" className="text-[#0A84FF]" />
                  <div className="font-heading text-base tracking-tight">What you get</div>
                  <span className="ml-auto font-mono text-[9px] uppercase tracking-wider text-[#0A84FF] border border-[#0A84FF]/40 px-1.5 py-0.5">
                    explainable
                  </span>
                </div>
                <ul className="space-y-3 text-sm text-foreground leading-relaxed">
                  <li className="flex gap-2">
                    <span className="text-[#30D158]">■</span> Always-on control testing and exception detection
                  </li>
                  <li className="flex gap-2">
                    <span className="text-[#30D158]">■</span> Evidence lineage and drill-down for substantiation
                  </li>
                  <li className="flex gap-2">
                    <span className="text-[#30D158]">■</span> Case workflow with SLA, owners, and audit trails
                  </li>
                  <li className="flex gap-2">
                    <span className="text-[#30D158]">■</span> Governance-grade controls: rollups, approvals, WORM, legal hold
                  </li>
                </ul>
                <div className="mt-5 flex flex-wrap gap-2">
                  <Pill>audit logged</Pill>
                  <Pill>rbac</Pill>
                  <Pill>approvals</Pill>
                  <Pill>data trust</Pill>
                  <Pill>exports</Pill>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="border-t border-border">
        <div className="max-w-[1200px] mx-auto px-6 py-14">
          <div className="flex items-end justify-between gap-6 mb-8">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Capabilities</div>
              <h2 className="font-heading text-3xl tracking-tight mt-2">Features built for assurance</h2>
              <p className="text-muted-foreground mt-2 max-w-2xl">
                Designed to replace point-in-time sampling with continuous, evidence-backed monitoring — without
                sacrificing governance.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-px bg-border border border-border">
            {FEATURES.map((f) => {
              const Icon = f.icon;
              return (
                <div key={f.title} className="bg-card p-5">
                  <div className="flex items-center gap-2 mb-3">
                    <Icon size={16} className="text-foreground" />
                    <div className="font-heading text-base tracking-tight">{f.title}</div>
                  </div>
                  <div className="text-sm text-muted-foreground leading-relaxed">{f.desc}</div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Use cases */}
      <section className="border-t border-border">
        <div className="max-w-[1200px] mx-auto px-6 py-14">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
            <div className="lg:col-span-4">
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Use cases</div>
              <h2 className="font-heading text-3xl tracking-tight mt-2">Who it’s for</h2>
              <p className="text-muted-foreground mt-2 leading-relaxed">
                Different roles see the same truth — tailored to how they work.
              </p>
            </div>
            <div className="lg:col-span-8 grid grid-cols-1 md:grid-cols-2 gap-px bg-border border border-border">
              {USE_CASES.map((u) => (
                <div key={u.title} className="bg-card p-6">
                  <div className="font-heading text-base tracking-tight">{u.title}</div>
                  <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                    {u.points.map((p) => (
                      <li key={p} className="flex gap-2">
                        <span className="text-[#0A84FF]">→</span> {p}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-border">
        <div className="max-w-[1200px] mx-auto px-6 py-14">
          <div className="border border-border bg-card p-8 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Get started</div>
              <h3 className="font-heading text-2xl tracking-tight mt-2">Try the demo personas</h3>
              <p className="text-muted-foreground mt-2 max-w-2xl">
                Use the built-in demo accounts to explore CFO, Controller, Audit, Compliance, and External Auditor
                experiences.
              </p>
            </div>
            <Link
              to="/login"
              className="inline-flex items-center gap-2 px-4 h-11 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 transition-colors font-mono text-xs uppercase tracking-[0.15em]"
              data-testid="landing-cta-login"
            >
              Go to login <ArrowRight size={14} />
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border">
        <div className="max-w-[1200px] mx-auto px-6 py-10 text-muted-foreground text-xs font-mono uppercase tracking-[0.12em] flex flex-col md:flex-row gap-3 md:items-center md:justify-between">
          <span>OneTouch Audit AI · evidence-first continuous assurance</span>
          <span>Built for: IIA continuous auditing · CCM workflows · governed AI</span>
        </div>
      </footer>
    </div>
  );
}

