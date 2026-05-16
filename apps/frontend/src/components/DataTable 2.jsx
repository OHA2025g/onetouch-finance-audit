import React from "react";
import clsx from "clsx";

/**
 * Premium table shell:
 * - sticky header
 * - consistent borders/hover
 * - optional max height scroll
 */
export function DataTable({
  children,
  className,
  tableClassName,
  maxHeightClassName = "max-h-[70vh]",
  stickyHeader = true,
  testId,
}) {
  return (
    <div
      data-testid={testId}
      className={clsx(
        "overflow-x-auto rounded-sm border border-zinc-200 bg-zinc-50/90 text-foreground dark:border-zinc-800 dark:bg-zinc-950/50",
        className
      )}
    >
      <div className={clsx(maxHeightClassName, "overflow-y-auto text-foreground")}>
        <table className={clsx("w-full text-sm text-foreground", tableClassName)}>
          {React.Children.map(children, (child) => {
            if (!child) return child;
            if (child.type === DataTableHead) {
              return React.cloneElement(child, {
                sticky: stickyHeader,
              });
            }
            return child;
          })}
        </table>
      </div>
    </div>
  );
}

export function DataTableHead({ children, sticky }) {
  return (
    <thead
      className={clsx(
        "border-b border-zinc-200 dark:border-zinc-800",
        sticky && "sticky top-0 z-10 bg-zinc-100/95 backdrop-blur-md dark:bg-zinc-900/95"
      )}
    >
      {children}
    </thead>
  );
}

export function DataTableBody({ children }) {
  return <tbody>{children}</tbody>;
}

export function DataTableRow({ children, className, onClick, testId }) {
  return (
    <tr
      data-testid={testId}
      onClick={onClick}
      className={clsx(
        "border-b border-zinc-200 text-foreground transition-colors dark:border-zinc-800/80",
        onClick
          ? "cursor-pointer hover:bg-zinc-100/90 dark:hover:bg-zinc-900/70"
          : "hover:bg-zinc-50/80 dark:hover:bg-zinc-900/40",
        className
      )}
    >
      {children}
    </tr>
  );
}

export function DataTableTh({ children, className, align = "left", colSpan, rowSpan }) {
  return (
    <th
      colSpan={colSpan}
      rowSpan={rowSpan}
      className={clsx(
        "crt-num p-3 text-[10px] font-medium uppercase tracking-wider text-muted-foreground",
        align === "right" && "text-right",
        align === "center" && "text-center",
        className
      )}
    >
      {children}
    </th>
  );
}

export function DataTableTd({ children, className, align = "left", colSpan, rowSpan, onClick }) {
  return (
    <td
      colSpan={colSpan}
      rowSpan={rowSpan}
      onClick={onClick}
      className={clsx(
        "p-3 text-foreground",
        align === "right" && "text-right",
        align === "center" && "text-center",
        className
      )}
    >
      {children}
    </td>
  );
}
