/** Client-side audit workspace KPIs (fallback when API summary absent). */

import { daysFromNow, fmtDate } from "./format";

const STALE_DAYS = { daily: 2, weekly: 10, monthly: 35, quarterly: 100 };
const DEFAULT_STALE = 14;

export function parseIso(ts) {
  if (!ts) return null;
  try {
    return new Date(ts);
  } catch {
    return null;
  }
}

export function controlIsStale(control, now = new Date()) {
  const at = parseIso(control?.last_run_at);
  if (!at) return false;
  const freq = String(control?.frequency || "").toLowerCase();
  const limit = STALE_DAYS[freq] ?? DEFAULT_STALE;
  return Math.floor((now - at) / (1000 * 60 * 60 * 24)) > limit;
}

export function controlRunStatus(control) {
  if (!control?.last_run_at) return "not_run";
  if (control.last_run_pass === true) return "pass";
  if (control.last_run_pass === false) return "fail";
  return "not_run";
}

export function catalogPassFailNotRun(controls = []) {
  let pass = 0;
  let fail = 0;
  let not_run = 0;
  for (const c of controls) {
    const s = controlRunStatus(c);
    if (s === "pass") pass += 1;
    else if (s === "fail") fail += 1;
    else not_run += 1;
  }
  return { pass, fail, not_run };
}

/** Pass rate among controls that have been run (pass / (pass + fail)). */
export function passRateFromPfn(pfn) {
  const ran = (pfn?.pass ?? 0) + (pfn?.fail ?? 0);
  return ran ? Math.round((100 * pfn.pass) / ran * 10) / 10 : null;
}

export function buildClientSummary(controls = []) {
  const pfn = catalogPassFailNotRun(controls);
  const stale_control_count = controls.filter((c) => controlIsStale(c)).length;
  const critical_failing_count = controls.filter(
    (c) => ["critical", "high"].includes(String(c.criticality || "").toLowerCase()) && c.last_run_pass === false
  ).length;
  return {
    audit_readiness_pct: null,
    open_exceptions_count: null,
    open_exposure_usd: null,
    pass_fail_not_run: pfn,
    pass_rate_pct: passRateFromPfn(pfn),
    stale_control_count,
    critical_failing_count,
    by_process: [],
    by_severity: [],
    top_failing_controls: [],
    heatmap: [],
    control_count: controls.length,
  };
}

/** Prefer API summary; fill gaps from full catalog where safe. */
export function mergeSummary(apiSummary, controls = []) {
  const client = buildClientSummary(controls);
  if (!apiSummary) return client;
  const pfn = apiSummary.pass_fail_not_run || client.pass_fail_not_run;
  return {
    ...client,
    ...apiSummary,
    pass_fail_not_run: pfn,
    pass_rate_pct: passRateFromPfn(pfn) ?? apiSummary.pass_rate_pct ?? client.pass_rate_pct,
    control_count: apiSummary.control_count ?? client.control_count,
  };
}

export function hasActiveListFilters(filter = {}) {
  return Boolean(filter.process || filter.crit || filter.status || (filter.q && String(filter.q).trim()));
}

/** Sum last-run exception counts for controls in the current list. */
export function sumLastRunExceptions(controls = []) {
  return controls.reduce((s, c) => {
    const n = c?.last_run_exceptions;
    return s + (typeof n === "number" && n > 0 ? n : 0);
  }, 0);
}

/** Open exception load attributed to controls in the filtered set. */
export function aggregateOpenMetricsForControls(filteredControls = [], apiSummary) {
  const codes = new Set(filteredControls.map((c) => c.code));
  const topByCode = Object.fromEntries((apiSummary?.top_failing_controls || []).map((t) => [t.code, t]));
  let open_exceptions_count = 0;
  let open_exposure_usd = 0;
  const attributed = new Set();
  for (const code of codes) {
    const row = topByCode[code];
    if (row) {
      open_exceptions_count += row.exceptions || 0;
      open_exposure_usd += row.open_exposure_usd || 0;
      attributed.add(code);
    }
  }
  for (const c of filteredControls) {
    if (c.last_run_pass === false && !attributed.has(c.code)) {
      const exc = c.last_run_exceptions ?? 0;
      if (exc > 0) {
        open_exceptions_count += exc;
        attributed.add(c.code);
      }
    }
  }
  return {
    open_exceptions_count,
    open_exposure_usd: Math.round(open_exposure_usd * 100) / 100,
  };
}

export function isCatalogAllGreen(allControls = [], summary) {
  if (!allControls.length) return false;
  const pfn = summary?.pass_fail_not_run || catalogPassFailNotRun(allControls);
  return (
    (pfn.fail ?? 0) === 0 &&
    (summary?.stale_control_count ?? 0) === 0 &&
    (summary?.critical_failing_count ?? 0) === 0 &&
    (summary?.open_exceptions_count ?? 0) === 0
  );
}

/** Group dashboard recent runs by control_id for list sparklines. */
export function buildRunsSparklineByControl(recentRuns = [], limitPerControl = 6) {
  const map = {};
  const sorted = [...recentRuns].sort((a, b) => String(b.run_ts || "").localeCompare(String(a.run_ts || "")));
  for (const r of sorted) {
    const cid = r.control_id;
    if (!cid) continue;
    if (!map[cid]) map[cid] = [];
    if (map[cid].length < limitPerControl) {
      map[cid].push({ exc: r.exceptions_count ?? 0, ts: r.run_ts });
    }
  }
  return map;
}

/** First control id per process (for chart drill). */
export function firstControlIdByProcess(controls = []) {
  const map = {};
  for (const c of controls) {
    const p = c.process || "Unknown";
    if (!map[p]) map[p] = c.id;
  }
  return map;
}

function filterApiSlices(apiSummary, filteredControls, filter) {
  const codes = new Set(filteredControls.map((c) => c.code));
  const processes = new Set(filteredControls.map((c) => c.process));
  let byProcess = (apiSummary?.by_process || []).filter((p) => processes.has(p.process));
  let topFailing = (apiSummary?.top_failing_controls || []).filter((t) => codes.has(t.code));
  let heatmap = (apiSummary?.heatmap || []).filter((h) => processes.has(h.process));
  let bySeverity = apiSummary?.by_severity || [];
  if (filter.crit) {
    bySeverity = bySeverity.filter((s) => s.severity === filter.crit);
    heatmap = heatmap.filter((h) => h.criticality === filter.crit);
  }
  const { open_exceptions_count, open_exposure_usd } = aggregateOpenMetricsForControls(filteredControls, apiSummary);
  return { byProcess, topFailing, heatmap, bySeverity, open_exceptions_count, open_exposure_usd };
}

/**
 * KPI + chart payload for the current list filters.
 * Catalog metrics (pass/fail/stale) always follow `filteredControls`.
 */
export function deriveViewSummary(apiSummary, filteredControls, allControls, filter) {
  const catalog = buildClientSummary(filteredControls);
  const base = mergeSummary(apiSummary, allControls);

  if (!hasActiveListFilters(filter)) {
    return {
      ...base,
      controls_in_view: String(allControls.length),
      view_filtered: false,
      readiness_in_view: false,
      catalog_readiness_pct: base.audit_readiness_pct,
      last_run_exceptions_sum: sumLastRunExceptions(allControls),
    };
  }

  const slices = filterApiSlices(apiSummary, filteredControls, filter);
  const globalReadiness = base.audit_readiness_pct;
  return {
    ...base,
    pass_fail_not_run: catalog.pass_fail_not_run,
    pass_rate_pct: catalog.pass_rate_pct,
    audit_readiness_pct: catalog.pass_rate_pct ?? globalReadiness,
    catalog_readiness_pct: globalReadiness,
    readiness_in_view: true,
    stale_control_count: catalog.stale_control_count,
    critical_failing_count: catalog.critical_failing_count,
    open_exceptions_count: slices.open_exceptions_count,
    open_exposure_usd: slices.open_exposure_usd,
    last_run_exceptions_sum: sumLastRunExceptions(filteredControls),
    by_process: slices.byProcess,
    by_severity: slices.bySeverity,
    top_failing_controls: slices.topFailing,
    heatmap: slices.heatmap,
    controls_in_view: `${filteredControls.length} / ${allControls.length}`,
    view_filtered: true,
  };
}

export function postureSentence(summary) {
  if (!summary) return "";
  const parts = [];
  if (summary.view_filtered && summary.controls_in_view) {
    parts.push(`${summary.controls_in_view} controls in view`);
  }
  const readiness = summary.audit_readiness_pct;
  if (readiness != null) parts.push(`Audit readiness ${readiness}%`);
  const open = summary.open_exceptions_count;
  if (open != null) parts.push(`${open} open exception${open === 1 ? "" : "s"}`);
  const stale = summary.stale_control_count ?? 0;
  if (stale > 0) parts.push(`${stale} stale control${stale === 1 ? "" : "s"}`);
  const crit = summary.critical_failing_count ?? 0;
  if (crit > 0) parts.push(`${crit} critical/high failing`);
  return parts.join(" · ") || "Run controls to establish continuous assurance posture.";
}

export function filterControls(controls, { process = "", crit = "", status = "", q = "" }) {
  const query = q.trim().toLowerCase();
  return controls.filter((c) => {
    if (process && c.process !== process) return false;
    if (crit && c.criticality !== crit) return false;
    if (status) {
      const st = controlIsStale(c) ? "stale" : controlRunStatus(c);
      if (st !== status) return false;
    }
    if (query) {
      const hay = `${c.code} ${c.name} ${c.process}`.toLowerCase();
      if (!hay.includes(query)) return false;
    }
    return true;
  });
}

export function sortControls(controls, sortKey) {
  const list = [...controls];
  const byCode = (a, b) => String(a.code).localeCompare(String(b.code));
  switch (sortKey) {
    case "code_desc":
      return list.sort((a, b) => -byCode(a, b));
    case "name":
      return list.sort((a, b) => String(a.name).localeCompare(String(b.name)) || byCode(a, b));
    case "criticality":
      return list.sort((a, b) => {
        const rank = { critical: 4, high: 3, medium: 2, low: 1 };
        return (rank[b.criticality] || 0) - (rank[a.criticality] || 0) || byCode(a, b);
      });
    case "exceptions":
      return list.sort(
        (a, b) => (b.last_run_exceptions ?? -1) - (a.last_run_exceptions ?? -1) || byCode(a, b)
      );
    case "last_run":
      return list.sort((a, b) => {
        const ta = parseIso(a.last_run_at)?.getTime() ?? 0;
        const tb = parseIso(b.last_run_at)?.getTime() ?? 0;
        return tb - ta || byCode(a, b);
      });
    default:
      return list.sort(byCode);
  }
}

/** Human-readable last-run age for control list. */
export function formatRelativeRun(iso) {
  if (!iso) return null;
  const offset = daysFromNow(iso);
  if (offset == null) return null;
  const ago = -offset;
  if (ago <= 0) return "Today";
  if (ago === 1) return "1d ago";
  if (ago < 14) return `${ago}d ago`;
  return fmtDate(iso);
}

export function controlListStatus(control) {
  if (controlIsStale(control)) return { key: "stale", label: "STALE" };
  const st = controlRunStatus(control);
  if (st === "pass") return { key: "pass", label: "PASS" };
  if (st === "fail") return { key: "fail", label: "FAIL" };
  return { key: "not_run", label: "NOT RUN" };
}

export function kpiSeverityForReadiness(pct) {
  if (pct == null || Number.isNaN(pct)) return undefined;
  if (pct >= 80) return "success";
  if (pct >= 60) return "warning";
  return "critical";
}

export function kpiSeverityForPassRate(pct) {
  if (pct == null || Number.isNaN(pct)) return undefined;
  if (pct >= 85) return "success";
  if (pct >= 70) return "warning";
  return "critical";
}

export function healthDonutData(passFailNotRun) {
  const pfn = passFailNotRun || { pass: 0, fail: 0, not_run: 0 };
  return [
    { name: "Pass", value: pfn.pass, fill: "hsl(var(--chart-4))" },
    { name: "Fail", value: pfn.fail, fill: "hsl(var(--destructive))" },
    { name: "Not run", value: pfn.not_run, fill: "hsl(var(--muted-foreground))" },
  ].filter((d) => d.value > 0);
}
