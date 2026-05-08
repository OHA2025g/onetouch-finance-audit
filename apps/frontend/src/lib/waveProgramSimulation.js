import {
  PARAM_TARGET,
  WAVE_PROGRAM_MODULE_CATALOG,
  buildInitialModuleStates,
  recomputeDerivedFields,
} from "../data/waveProgramDeliveryModel";

/** Min parameter (0–100) required on every module in wave W before wave W+1 is eligible for delivery actions */
export const WAVE_UNLOCK_MIN_PARAM = 90;

function bumpToward100(value, delta) {
  return Math.min(PARAM_TARGET, Math.max(0, Math.round(value + delta)));
}

function advanceDepthIfReady(m) {
  const all100 = m.parameters.every((p) => p >= PARAM_TARGET);
  if (!all100) return m.depth;
  if (m.depth === "L2") return "L3";
  if (m.depth === "L3") return "L4";
  return m.depth;
}

function normalizeModule(m) {
  const depth = advanceDepthIfReady(m);
  const next = { ...m, depth };
  return { ...next, ...recomputeDerivedFields(next) };
}

export function modulesInWave(modules, waveId) {
  return modules.filter((x) => x.wave === waveId);
}

/** Wave w unlocks when w === 0 or every module in wave w−1 has min(param) ≥ threshold. */
export function isWaveUnlockedForDelivery(waveId, modules) {
  if (waveId <= 0) return true;
  const prev = modulesInWave(modules, waveId - 1);
  if (prev.length === 0) return true;
  return prev.every((m) => {
    const minP = Math.min(...m.parameters);
    return minP >= WAVE_UNLOCK_MIN_PARAM;
  });
}

/** @param {object[]} modules */
export function maxUnlockedWaveIndex(modules) {
  let max = -1;
  for (let w = 0; w <= 8; w += 1) {
    if (!isWaveUnlockedForDelivery(w, modules)) break;
    max = w;
  }
  return Math.max(0, max);
}

export function aggregateParamCompletion(modules) {
  const n = modules.length * 8;
  if (n === 0) return 0;
  const sum = modules.reduce((acc, m) => acc + m.parameters.reduce((a, p) => a + p, 0), 0);
  return sum / (n * PARAM_TARGET);
}

export function waveAggregateCompletion(modules, waveId) {
  const subset = modulesInWave(modules, waveId);
  if (subset.length === 0) return 0;
  const sum = subset.reduce((acc, m) => acc + m.parameters.reduce((a, p) => a + p, 0), 0);
  return sum / (subset.length * 8 * PARAM_TARGET);
}

/** Deterministic pseudo-step from module id and wave (repeatable). */
function deliveryDelta(moduleId, waveId, salt) {
  const h = (moduleId * 17 + waveId * 31 + salt * 13) % 7;
  return 5 + h;
}

/** @param {object[]} modules */
export function applyWaveDeliveryAction(modules, waveId, mode) {
  const salt = mode === "advance" ? 11 : 3;
  const mult = mode === "advance" ? 1.35 : 1;
  return modules.map((m) => {
    if (m.wave !== waveId) return m;
    const deltaBase = deliveryDelta(m.id, waveId, salt) * mult;
    const nextParams = m.parameters.map((p) => bumpToward100(p, deltaBase));
    return normalizeModule({ ...m, parameters: nextParams });
  });
}

/** Global recheck: nudge parameters for modules in unlocked waves (parallel delivery). @param {object[]} modules */
export function applyRecheckCloseGaps(modules) {
  const capWave = maxUnlockedWaveIndex(modules);
  return modules.map((m) => {
    if (m.wave > capWave) return m;
    const nextParams = m.parameters.map((p) => bumpToward100(p, 4));
    return normalizeModule({ ...m, parameters: nextParams });
  });
}

export function isProgramTargetAchieved(modules) {
  return modules.every(
    (m) =>
      m.depth === "L4" &&
      m.status === "Fully Complete" &&
      m.parameters.length === 8 &&
      m.parameters.every((p) => p >= PARAM_TARGET)
  );
}

export { buildInitialModuleStates, WAVE_PROGRAM_MODULE_CATALOG };
