/**
 * Wave program: 40 modules × 8 parameters (0–100), depth L2–L4, status ladder.
 * Wave 0 = foundation; Waves 1–8 = delivery roadmap.
 */

/** @typedef {'L2' | 'L3' | 'L4'} ProgramDepth */
/** @typedef {'Partial' | 'Mostly complete' | 'Complete*' | 'Fully Complete'} ProgramStatus */

export const PARAM_KEYS = [
  "scopeCoverage",
  "controlDesign",
  "evidenceMaturity",
  "dataIntegration",
  "automationLevel",
  "policyAlignment",
  "userAdoption",
  "signoffReadiness",
];

export const PARAM_LABELS = [
  "Scope coverage",
  "Control design",
  "Evidence maturity",
  "Data integration",
  "Automation level",
  "Policy alignment",
  "User adoption",
  "Sign-off readiness",
];

/** Target is always 100 per parameter */
export const PARAM_TARGET = 100;

export const WAVE_META = [
  { wave: 0, title: "Wave 0 · Foundation", blurb: "Foundation/IA, integration, enterprise hardening" },
  { wave: 1, title: "Wave 1 · CFO stack", blurb: "Unified model, KPI, CFO command, action queue, Copilot 2.0" },
  { wave: 2, title: "Wave 2 · Close & liquidity", blurb: "Month-end, team performance, WC CC, 13-week cash" },
  { wave: 3, title: "Wave 3 · Ops finance", blurb: "AR, AP, O2C, credit, inventory, physical, fixed assets" },
  { wave: 4, title: "Wave 4 · Planning", blurb: "Budget master, budget vs actual, forecast accuracy" },
  { wave: 5, title: "Wave 5 · GL & procure", blurb: "GL audit, journals, recon, bank, vendor, three-way match" },
  { wave: 6, title: "Wave 6 · Treasury", blurb: "Treasury, forex/hedge, RPT" },
  { wave: 7, title: "Wave 7 · Governance", blurb: "Legal, DoA, policy, access/SoD, master DQ" },
  { wave: 8, title: "Wave 8 · Intelligence", blurb: "Evidence AI, continuous audit, risk scoring, board reporting" },
];

/**
 * Static catalog: id 1–40, wave, display name, deterministic demo seed (0–99) per param.
 * @type {Array<{ id: number, wave: number, name: string, seed: number[] }>}
 */
export const WAVE_PROGRAM_MODULE_CATALOG = [
  { id: 1, wave: 0, name: "Foundation/IA", seed: [12, 18, 14, 20, 10, 22, 8, 16] },
  { id: 2, wave: 1, name: "Unified finance model", seed: [24, 20, 22, 18, 16, 26, 14, 20] },
  { id: 3, wave: 1, name: "KPI engine", seed: [22, 28, 20, 24, 18, 20, 16, 22] },
  { id: 4, wave: 1, name: "CFO Command Center 2.0", seed: [18, 22, 20, 16, 24, 18, 20, 14] },
  { id: 5, wave: 1, name: "CFO action queue", seed: [20, 16, 24, 22, 14, 24, 18, 20] },
  { id: 6, wave: 2, name: "Month-end close", seed: [26, 22, 18, 20, 20, 18, 22, 16] },
  { id: 7, wave: 2, name: "Finance team performance", seed: [16, 24, 22, 18, 22, 20, 24, 18] },
  { id: 8, wave: 2, name: "Working capital CC", seed: [22, 18, 26, 20, 16, 22, 20, 24] },
  { id: 9, wave: 3, name: "AR / receivables", seed: [24, 20, 20, 22, 18, 16, 22, 20] },
  { id: 10, wave: 3, name: "AP / payables", seed: [20, 22, 18, 24, 20, 22, 16, 26] },
  { id: 11, wave: 2, name: "13-week cash", seed: [18, 20, 22, 16, 26, 20, 22, 18] },
  { id: 12, wave: 4, name: "Budget master", seed: [22, 24, 18, 20, 22, 18, 20, 24] },
  { id: 13, wave: 4, name: "Budget vs actual", seed: [20, 18, 24, 22, 18, 26, 20, 16] },
  { id: 14, wave: 4, name: "Forecast accuracy", seed: [16, 22, 20, 24, 22, 18, 24, 20] },
  { id: 15, wave: 5, name: "GL audit", seed: [24, 20, 22, 18, 20, 22, 18, 24] },
  { id: 16, wave: 5, name: "Journal risk", seed: [22, 22, 18, 20, 24, 20, 22, 18] },
  { id: 17, wave: 5, name: "Reconciliations", seed: [20, 24, 20, 22, 18, 24, 20, 22] },
  { id: 18, wave: 5, name: "Bank recon", seed: [18, 20, 26, 20, 22, 18, 24, 20] },
  { id: 19, wave: 5, name: "Vendor risk", seed: [22, 18, 20, 24, 20, 22, 18, 24] },
  { id: 20, wave: 5, name: "Three-way match", seed: [20, 22, 22, 18, 26, 20, 20, 18] },
  { id: 21, wave: 3, name: "O2C / revenue", seed: [24, 18, 22, 22, 20, 20, 18, 24] },
  { id: 22, wave: 3, name: "Credit notes", seed: [18, 24, 18, 20, 22, 22, 20, 24] },
  { id: 23, wave: 3, name: "Inventory audit", seed: [22, 20, 24, 18, 18, 24, 22, 20] },
  { id: 24, wave: 3, name: "Physical verification", seed: [20, 22, 20, 26, 20, 18, 24, 18] },
  { id: 25, wave: 3, name: "Fixed assets / CAPEX", seed: [16, 20, 22, 22, 24, 20, 22, 22] },
  { id: 26, wave: 6, name: "Treasury (debt / investments)", seed: [22, 22, 20, 18, 20, 24, 18, 24] },
  { id: 27, wave: 6, name: "Forex / hedge", seed: [20, 18, 22, 24, 22, 20, 22, 20] },
  { id: 28, wave: 6, name: "RPT", seed: [18, 24, 18, 22, 24, 22, 20, 20] },
  { id: 29, wave: 7, name: "Legal / litigation", seed: [24, 20, 20, 20, 18, 22, 22, 22] },
  { id: 30, wave: 7, name: "DoA", seed: [22, 22, 18, 24, 20, 20, 24, 18] },
  { id: 31, wave: 7, name: "Policy compliance", seed: [20, 20, 24, 18, 22, 24, 18, 22] },
  { id: 32, wave: 7, name: "Access / SoD", seed: [18, 26, 20, 22, 24, 18, 22, 20] },
  { id: 33, wave: 7, name: "Master DQ", seed: [22, 18, 22, 24, 20, 20, 20, 22] },
  { id: 34, wave: 8, name: "Evidence intelligence", seed: [16, 22, 24, 20, 22, 18, 24, 20] },
  { id: 35, wave: 8, name: "Continuous audit rules", seed: [20, 20, 22, 22, 20, 26, 18, 20] },
  { id: 36, wave: 8, name: "Risk intelligence scoring", seed: [22, 24, 18, 18, 24, 20, 20, 22] },
  { id: 37, wave: 1, name: "Copilot 2.0", seed: [24, 16, 20, 28, 22, 18, 26, 14] },
  { id: 38, wave: 0, name: "Integration hub", seed: [14, 20, 16, 24, 18, 20, 12, 22] },
  { id: 39, wave: 8, name: "Board reporting", seed: [18, 22, 20, 20, 18, 22, 22, 26] },
  { id: 40, wave: 0, name: "Enterprise hardening", seed: [20, 14, 18, 22, 24, 26, 16, 18] },
];

export function catalogModuleToRuntime(row) {
  const params = row.seed.map((s) => Math.min(55, 12 + (s % 38)));
  return {
    id: row.id,
    wave: row.wave,
    name: row.name,
    parameters: [...params],
    depth: /** @type {ProgramDepth} */ ("L2"),
  };
}

export function buildInitialModuleStates() {
  return WAVE_PROGRAM_MODULE_CATALOG.map(catalogModuleToRuntime).map((m) => {
    const clamped = recomputeDerivedFields({ ...m });
    return { ...m, ...clamped };
  });
}

/**
 * @param {{ parameters: number[], depth: ProgramDepth }} m
 */
export function recomputeDerivedFields(m) {
  const params = m.parameters.map((p) => Math.max(0, Math.min(PARAM_TARGET, Math.round(p))));
  const minP = Math.min(...params);
  const all100 = params.every((p) => p >= PARAM_TARGET);
  /** @type {ProgramStatus} */
  let status = "Partial";
  if (all100 && m.depth === "L4") status = "Fully Complete";
  else if (all100 && (m.depth === "L2" || m.depth === "L3")) status = "Complete*";
  else if (minP >= 40) status = "Mostly complete";
  return { parameters: params, status };
}
