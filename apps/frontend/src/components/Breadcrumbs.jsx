import React from "react";
import { Link, useLocation } from "react-router-dom";
import { CaretRight, House } from "@phosphor-icons/react";
import clsx from "clsx";
import { labelForPath } from "../lib/routeConfig";
import { toProperHeadingLabel } from "../lib/headingCase";

/**
 * Builds cumulative path segments under `/app/*` for wayfinding.
 */
function crumbsForLocation(pathname, search) {
  const parts = pathname.split("/").filter(Boolean);
  if (!parts.length) return [{ to: "/", label: "Home" }];

  const out = [{ to: "/", label: "Home" }];
  if (parts[0] !== "app") {
    out.push({ to: pathname, label: labelForPath(pathname + search) });
    return out;
  }

  let acc = "";
  for (let i = 0; i < parts.length; i += 1) {
    acc += `/${parts[i]}`;
    const isLast = i === parts.length - 1;
    const label = labelForPath(acc + (isLast ? search : ""));
    out.push({ to: acc, label });
  }
  return out;
}

export default function Breadcrumbs({ className }) {
  const { pathname, search } = useLocation();
  const items = crumbsForLocation(pathname, search);

  return (
    <nav
      aria-label="Breadcrumb"
      className={clsx(
        "flex min-w-0 flex-wrap items-center gap-1 border-b border-zinc-200/90 bg-gradient-to-b from-zinc-100/90 to-transparent px-4 py-2.5 text-[11px] font-medium tracking-wide text-muted-foreground backdrop-blur-[2px] dark:border-zinc-800/90 dark:from-zinc-950/80 dark:to-transparent lg:px-8",
        className
      )}
      data-testid="breadcrumbs"
    >
      {items.map((c, idx) => {
        const last = idx === items.length - 1;
        return (
          <React.Fragment key={c.to}>
            {idx > 0 ? <CaretRight className="inline shrink-0 text-zinc-400" size={12} aria-hidden /> : null}
            {last ? (
              <span className="min-w-0 truncate text-foreground tabular-nums" aria-current="page">
                {idx === 0 ? (
                  <span className="inline-flex items-center gap-1">
                    <House size={12} className="inline" weight="regular" /> {toProperHeadingLabel(c.label)}
                  </span>
                ) : (
                  toProperHeadingLabel(c.label)
                )}
              </span>
            ) : (
              <Link
                to={c.to}
                className="shrink-0 rounded-none border border-transparent px-1.5 py-0.5 text-muted-foreground transition-[color,background-color,border-color,box-shadow] hover:border-primary/20 hover:bg-primary/[0.06] hover:text-foreground hover:shadow-sm"
              >
                {idx === 0 ? (
                  <span className="inline-flex items-center gap-1">
                    <House size={12} className="inline" weight="regular" /> {toProperHeadingLabel(c.label)}
                  </span>
                ) : (
                  toProperHeadingLabel(c.label)
                )}
              </Link>
            )}
          </React.Fragment>
        );
      })}
    </nav>
  );
}
