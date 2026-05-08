import React from "react";
import clsx from "clsx";

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
      {kicker && <div className="crt-overline text-muted-foreground">{kicker}</div>}
      <div className="mt-2 flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
        <div className="min-w-0">
          <h1 className="font-display text-3xl lg:text-4xl text-foreground tracking-tight flex items-center gap-2 min-w-0">
            {icon ? (
              <span className="crt-card inline-flex h-10 w-10 items-center justify-center rounded-sm border p-0">
                {icon}
              </span>
            ) : null}
            <span className="truncate">{title}</span>
          </h1>
          {subtitle ? <div className="text-sm text-muted-foreground mt-2 max-w-3xl">{subtitle}</div> : null}
        </div>
        {right ? <div className="flex items-center gap-2 flex-wrap">{right}</div> : null}
      </div>
    </div>
  );
}

export function SectionCard({ title, kicker, right, children, className, bodyClassName }) {
  return (
    <section className={clsx("crt-card overflow-hidden", className)} data-testid="section-card">
      {(title || kicker || right) && (
        <div className="flex items-start justify-between gap-4 border-b border-zinc-200 px-5 py-4 dark:border-zinc-800">
          <div className="min-w-0">
            {kicker ? <div className="crt-overline text-muted-foreground">{kicker}</div> : null}
            {title ? (
              <h3 className="font-display mt-1 text-base font-semibold tracking-tight text-foreground">{title}</h3>
            ) : null}
          </div>
          {right ? <div className="flex flex-wrap items-center gap-2">{right}</div> : null}
        </div>
      )}
      <div className={clsx("p-5 text-foreground", bodyClassName)}>{children}</div>
    </section>
  );
}
