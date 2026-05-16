import { fmtNum, fmtPct, fmtUSD } from "./format";

/** Ordered keys for primary rollup tiles (remaining scalar metrics follow in “More”). */
export const ROLLUP_PRIMARY_KEYS = [
  "audit_readiness_pct",
  "unresolved_high_risk_exposure",
  "open_critical_cases",
  "open_cases",
  "remediation_sla_pct",
  "evidence_completeness_pct",
  "repeat_finding_rate_pct",
  "control_failure_rate",
  "median_open_case_age_days",
  "median_open_exception_age_days",
  "pct_open_cases_past_due",
  "distinct_controls_with_open_exceptions",
  "exposure_concentration_hhi",
  "action_queue_open_count",
  "action_queue_open_exposure_usd",
  "close_readiness_items_open",
];

function rollupMetricKey(key) {
  if (key == null) return "";
  return typeof key === "string" ? key : String(key);
}

export function formatRollupMetricValue(key, raw) {
  const k = rollupMetricKey(key);
  if (raw == null || raw === "") return "—";
  if (k === "control_failure_rate") return fmtPct(Number(raw) * 100);
  if (k.includes("exposure") || k.includes("usd")) return fmtUSD(Number(raw));
  if (k.endsWith("_pct") || k.includes("readiness") || k === "repeat_finding_rate_pct") return fmtPct(Number(raw));
  if (k.includes("rate") && typeof raw === "number") return `${fmtNum(raw * (raw <= 1 ? 100 : 1))}${raw <= 1 ? "%" : ""}`;
  if (typeof raw === "number") return fmtNum(raw);
  return String(raw);
}

export function statSeverityForRollupKey(key, value) {
  const k = rollupMetricKey(key);
  if (value == null || typeof value !== "number") return undefined;
  if (k === "audit_readiness_pct" && value < 70) return "critical";
  if (k === "audit_readiness_pct" && value < 85) return "warning";
  if (k.includes("exposure") && value > 500_000) return "critical";
  if (k === "open_critical_cases" && value > 0) return "critical";
  if (k === "pct_open_cases_past_due" && value > 25) return "warning";
  if (k === "remediation_sla_pct" && value < 75) return "warning";
  if (k === "evidence_completeness_pct" && value < 80) return "warning";
  return undefined;
}
