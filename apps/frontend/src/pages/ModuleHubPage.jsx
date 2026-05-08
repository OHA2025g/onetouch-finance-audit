import React from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "@phosphor-icons/react";
import { PageHeader, PageShell, SectionCard } from "../components/PageShell";
import MastersFilterBar from "../components/filters/MastersFilterBar";
import { MODULE_HUBS } from "../lib/routeConfig";
import { useMastersFilters } from "../lib/MastersFilterContext";

function HubCardLink({ to, children, className, testId }) {
  const { hrefWithMasterParams } = useMastersFilters();
  return (
    <Link to={hrefWithMasterParams(to)} className={className} data-testid={testId || undefined}>
      {children}
    </Link>
  );
}

/**
 * Phase 1 module landing — hubKey must exist in MODULE_HUBS.
 */
export default function ModuleHubPage({ hubKey }) {
  const hub = MODULE_HUBS[hubKey];

  if (!hub) {
    return (
      <PageShell>
        <PageHeader kicker="MODULE" title="Hub not found" subtitle="This module map is not configured yet." />
      </PageShell>
    );
  }

  return (
    <div data-testid={`module-hub-${hubKey}`}>
      <PageShell maxWidth="max-w-[1400px]">
        <PageHeader kicker={hub.kicker} title={hub.title} subtitle={hub.subtitle} />

        {hub.showMasterFilters ? (
          <div className="mb-6" data-testid="masters-filter-bar-wrap">
            <MastersFilterBar />
          </div>
        ) : null}

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {hub.cards.map((c) => (
            <HubCardLink
              key={`${c.to}-${c.title}`}
              to={c.to}
              testId={c.testId}
              className="group crt-card block overflow-hidden border border-zinc-200 bg-white p-5 transition-colors hover:border-primary/40 hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-950/40 dark:hover:bg-zinc-900/60"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="font-display text-lg font-semibold tracking-tight text-foreground">{c.title}</div>
                  {c.badge ? (
                    <span className="crt-num mt-2 inline-block border border-primary/30 bg-primary/5 px-2 py-0.5 text-[9px] uppercase tracking-wider text-primary">
                      {c.badge}
                    </span>
                  ) : null}
                </div>
                <ArrowRight
                  size={18}
                  className="shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-foreground"
                  aria-hidden
                />
              </div>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{c.body}</p>
            </HubCardLink>
          ))}
        </div>

        <SectionCard
          kicker="ROADMAP"
          title="What ships next"
          className="mt-8"
          bodyClassName="text-sm text-muted-foreground leading-relaxed"
        >
          This hub is part of Phase 1 (information architecture). Upcoming phases add KPI engines, working capital,
          treasury, continuous audit rules, and production integrations — without breaking the links above.
        </SectionCard>
      </PageShell>
    </div>
  );
}
