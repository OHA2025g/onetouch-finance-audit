import React from "react";

function Pulse({ className }) {
  return <div className={`animate-pulse rounded-sm bg-zinc-200/80 dark:bg-zinc-800/80 ${className}`} />;
}

export default function AuditWorkspaceSkeleton() {
  return (
    <div className="space-y-4" data-testid="audit-workspace-skeleton">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <Pulse key={i} className="h-24" />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <Pulse className="h-48 xl:col-span-3" />
        <Pulse className="h-48 xl:col-span-3" />
        <Pulse className="h-48 xl:col-span-3" />
        <Pulse className="h-48 xl:col-span-3" />
        <Pulse className="h-52 xl:col-span-7" />
        <Pulse className="h-52 xl:col-span-5" />
      </div>
      <Pulse className="h-28" />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        <Pulse className="h-[50vh] lg:col-span-2" />
        <Pulse className="h-[50vh] lg:col-span-3" />
      </div>
    </div>
  );
}
