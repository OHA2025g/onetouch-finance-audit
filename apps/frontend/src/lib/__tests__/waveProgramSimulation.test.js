import {
  applyRecheckCloseGaps,
  applyWaveDeliveryAction,
  buildInitialModuleStates,
  isProgramTargetAchieved,
  isWaveUnlockedForDelivery,
  maxUnlockedWaveIndex,
  modulesInWave,
  WAVE_UNLOCK_MIN_PARAM,
} from "../waveProgramSimulation";

describe("waveProgramSimulation", () => {
  test("buildInitialModuleStates has 40 modules", () => {
    const m = buildInitialModuleStates();
    expect(m).toHaveLength(40);
    expect(m.every((x) => x.parameters.length === 8)).toBe(true);
  });

  test("wave 0 unlocked, wave 1 locked until wave 0 min threshold", () => {
    let m = buildInitialModuleStates();
    expect(isWaveUnlockedForDelivery(0, m)).toBe(true);
    expect(maxUnlockedWaveIndex(m)).toBe(0);
    expect(isWaveUnlockedForDelivery(1, m)).toBe(false);

    m = m.map((mod) => {
      if (mod.wave !== 0) return mod;
      return { ...mod, parameters: mod.parameters.map(() => WAVE_UNLOCK_MIN_PARAM) };
    });
    expect(isWaveUnlockedForDelivery(1, m)).toBe(true);
    expect(maxUnlockedWaveIndex(m)).toBeGreaterThanOrEqual(1);
  });

  test("applyWaveDeliveryAction is deterministic for same input", () => {
    const a = buildInitialModuleStates();
    const b = buildInitialModuleStates();
    const outA = applyWaveDeliveryAction(a, 0, "simulate");
    const outB = applyWaveDeliveryAction(b, 0, "simulate");
    expect(outA).toEqual(outB);
  });

  test("recheck only touches modules in unlocked waves", () => {
    const base = buildInitialModuleStates();
    const w1Before = modulesInWave(base, 1)[0].parameters[0];
    const next = applyRecheckCloseGaps(base);
    const w1After = modulesInWave(next, 1)[0].parameters[0];
    expect(w1After).toBe(w1Before);
  });

  test("isProgramTargetAchieved false on seed", () => {
    expect(isProgramTargetAchieved(buildInitialModuleStates())).toBe(false);
  });
});
