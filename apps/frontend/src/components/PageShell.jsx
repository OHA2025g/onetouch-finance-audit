import React, { useState } from "react";
import clsx from "clsx";
import { CaretDown, CaretUp } from "@phosphor-icons/react";
import { toProperHeadingLabel } from "../lib/headingCase";

export function PageShell({ children, className, maxWidth = "max-w-[1700px]" }) {
  return (
    <div
      className={clsx(
        "min-h-full bg-zinc-50 text-foreground dark:bg-zinc-950 dark:text-foreground",
        "p-6 lg:p-8",
        maxWidth,
        className
      )}
      data-testid="page-shell"
    >
      {children}
    </div>
  );
}

export function PageHeader({ kicker, title, subtitle, right, icon, className }) {
  return (
    <div className={clsx("mb-6", className)} data-testid="page-header">
      {kicker && <div className="crt-overline text-muted-foreground">{toProperHeadingLabel(kicker)}</div>}
      <div className="mt-2 flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
        <div className="min-w-0">
          <h1 className="font-display text-3xl lg:text-4xl text-foreground tracking-tight flex items-center gap-2 min-w-0">
            {icon ? (
              <span className="crt-card inline-flex h-10 w-10 items-center justify-center rounded-sm border p-0">
                {icon}
              </span>
            ) : null}
            <span className="truncate">{toProperHeadingLabel(title)}</span>
          </h1>
          {subtitle ? <div className="text-sm text-muted-foreground mt-2 max-w-3xl">{subtitle}</div> : null}
        </div>
        {right ? <div className="flex items-center gap-2 flex-wrap">{right}</div> : null}
      </div>
    </div>
  );
}

export function SectionCard({
  title,
  kicker,
  subtitle,
  right,
  children,
  className,
  bodyClassName,
  collapsible = false,
  defaultCollapsed = false,
  collapseTestId,
  "data-testid": dataTestId,
}) {
  const [collapsed, setCollapsed] = useState(Boolean(defaultCollapsed));
  const showHeader = title || kicker || right || collapsible;
  const showBody = !collapsible || !collapsed;

  return (
    <section className={clsx("crt-card overflow-hidden", className)} data-testid={dataTestId || "section-card"}>
      {showHeader && (
        <div className="flex items-start justify-between gap-4 border-b border-zinc-200 px-5 py-4 dark:border-zinc-800">
          <div className="min-w-0">
            {kicker ? <div className="crt-overline text-muted-foreground">{toProperHeadingLabel(kicker)}</div> : null}
            {title ? (
              <h3 className="font-display mt-1 text-base font-semibold tracking-tight text-foreground">
                {toProperHeadingLabel(title)}
              </h3>
            ) : null}
            {subtitle ? (
              <p className="mt-1.5 text-sm leading-snug text-muted-foreground">{subtitle}</p>
            ) : null}
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-1">
            {right ? <div className="flex flex-wrap items-center gap-2">{right}</div> : null}
            {collapsible ? (
              <button
                type="button"
                onClick={() => setCollapsed((c) => !c)}
                title={collapsed ? "Expand" : "Collapse"}
                className="crt-card flex h-8 w-8 items-center justify-center text-muted-foreground transition-colors hover:text-foreground"
                data-testid={collapseTestId || "section-card-collapse"}
              >
                {collapsed ? <CaretDown size={12} /> : <CaretUp size={12} />}
              </button>
            ) : null}
          </div>
        </div>
      )}
      {showBody ? <div className={clsx("p-5 text-foreground", bodyClassName)}>{children}</div> : null}
    </section>
  );
}
