import React from "react";
import { Link } from "react-router-dom";

/**
 * Lightweight breadcrumb row for deep drill / evidence views.
 * @param {{ label: string, to?: string }[]} props.crumbs — last item may omit `to` (current page)
 */
export default function DrillContextBar({ crumbs = [] }) {
  if (!crumbs.length) return null;
  return (
    <nav
      className="mb-4 flex flex-wrap items-center gap-x-1 gap-y-0.5 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground"
      aria-label="Breadcrumb"
      data-testid="drill-context-bar"
    >
      {crumbs.map((c, i) => (
        <span key={`${c.label}-${i}`} className="flex items-center gap-1">
          {i > 0 ? <span className="text-zinc-400 dark:text-zinc-600">/</span> : null}
          {c.to ? (
            <Link to={c.to} className="text-primary hover:underline">
              {c.label}
            </Link>
          ) : (
            <span className="text-muted-foreground">{c.label}</span>
          )}
        </span>
      ))}
    </nav>
  );
}
