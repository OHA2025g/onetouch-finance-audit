import React from "react";
import { Link } from "react-router-dom";
import clsx from "clsx";
import { StatCard } from "../StatCard";

/** StatCard wrapped in a drill link (CFO cockpit pattern). */
export default function AuditLinkStatCard({ to, className, ...statProps }) {
  if (!to) {
    return <StatCard {...statProps} />;
  }
  return (
    <Link
      to={to}
      className={clsx("block rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-primary", className)}
      data-testid={statProps.testId ? `${statProps.testId}-link` : undefined}
    >
      <StatCard {...statProps} />
    </Link>
  );
}
