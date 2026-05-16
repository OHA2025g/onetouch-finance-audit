import {
  aggregateOpenMetricsForControls,
  buildRunsSparklineByControl,
  catalogPassFailNotRun,
  controlListStatus,
  deriveViewSummary,
  filterControls,
  firstControlIdByProcess,
  formatRelativeRun,
  hasActiveListFilters,
  isCatalogAllGreen,
  kpiSeverityForPassRate,
  kpiSeverityForReadiness,
  passRateFromPfn,
  sumLastRunExceptions,
} from "./auditWorkspaceSummary";

describe("auditWorkspaceSummary", () => {
  const controls = [
    { id: "1", code: "C1", name: "A", process: "P2P", criticality: "high", last_run_at: "2026-01-01", last_run_pass: true },
    { id: "2", code: "C2", name: "B", process: "P2P", criticality: "medium", last_run_at: "2026-01-01", last_run_pass: false },
    { id: "3", code: "C3", name: "C", process: "O2C", criticality: "low", last_run_at: null },
  ];

  const apiSummary = {
    audit_readiness_pct: 72,
    open_exceptions_count: 10,
    open_exposure_usd: 5000,
    pass_fail_not_run: { pass: 5, fail: 2, not_run: 3 },
    pass_rate_pct: 71.4,
    by_process: [
      { process: "P2P", open_count: 7, open_exposure_usd: 3000 },
      { process: "O2C", open_count: 3, open_exposure_usd: 2000 },
    ],
    top_failing_controls: [
      { id: "2", code: "C2", exceptions: 4, open_exposure_usd: 1000 },
    ],
    by_severity: [{ severity: "high", open_count: 2, open_exposure_usd: 800 }],
    heatmap: [{ process: "P2P", criticality: "high", open_count: 2 }],
  };

  test("passRateFromPfn uses only run controls", () => {
    expect(passRateFromPfn({ pass: 2, fail: 1, not_run: 5 })).toBe(66.7);
    expect(passRateFromPfn({ pass: 0, fail: 0, not_run: 3 })).toBeNull();
  });

  test("deriveViewSummary applies list filters to catalog metrics", () => {
    const filtered = filterControls(controls, { status: "fail" });
    const view = deriveViewSummary(apiSummary, filtered, controls, { status: "fail" });
    expect(view.view_filtered).toBe(true);
    expect(view.pass_fail_not_run).toEqual({ pass: 0, fail: 1, not_run: 0 });
    expect(view.pass_rate_pct).toBe(0);
    expect(view.controls_in_view).toBe("1 / 3");
    expect(view.readiness_in_view).toBe(true);
    expect(view.audit_readiness_pct).toBe(0);
    expect(view.catalog_readiness_pct).toBe(72);
    expect(view.last_run_exceptions_sum).toBe(0);
  });

  test("deriveViewSummary re-aggregates open metrics for filtered controls", () => {
    const filtered = filterControls(controls, { process: "P2P" });
    const view = deriveViewSummary(apiSummary, filtered, controls, { process: "P2P" });
    const agg = aggregateOpenMetricsForControls(filtered, apiSummary);
    expect(view.open_exceptions_count).toBe(agg.open_exceptions_count);
    expect(view.open_exposure_usd).toBe(agg.open_exposure_usd);
  });

  test("sumLastRunExceptions and sparklines", () => {
    const withExc = [{ last_run_exceptions: 2 }, { last_run_exceptions: 0 }, { last_run_exceptions: 3 }];
    expect(sumLastRunExceptions(withExc)).toBe(5);
    const spark = buildRunsSparklineByControl([
      { control_id: "1", run_ts: "2026-02-01", exceptions_count: 1 },
      { control_id: "1", run_ts: "2026-02-02", exceptions_count: 2 },
    ]);
    expect(spark["1"]).toHaveLength(2);
  });

  test("isCatalogAllGreen and firstControlIdByProcess", () => {
    const allPass = controls.map((c) => ({ ...c, last_run_pass: true, last_run_at: "2026-05-01" }));
    const greenSummary = deriveViewSummary(
      { ...apiSummary, open_exceptions_count: 0, pass_fail_not_run: { pass: 3, fail: 0, not_run: 0 } },
      allPass,
      allPass,
      {}
    );
    expect(isCatalogAllGreen(allPass, greenSummary)).toBe(true);
    expect(firstControlIdByProcess(controls).P2P).toBe("1");
  });

  test("deriveViewSummary keeps global API metrics without list filters", () => {
    const view = deriveViewSummary(apiSummary, controls, controls, {});
    expect(view.view_filtered).toBe(false);
    expect(view.open_exceptions_count).toBe(10);
    expect(hasActiveListFilters({})).toBe(false);
  });

  test("catalogPassFailNotRun counts not_run", () => {
    expect(catalogPassFailNotRun(controls)).toEqual({ pass: 1, fail: 1, not_run: 1 });
  });

  test("controlListStatus prefers stale over pass/fail", () => {
    const stalePass = {
      last_run_at: "2020-01-01",
      last_run_pass: true,
      frequency: "daily",
    };
    expect(controlListStatus(stalePass).key).toBe("stale");
    expect(controlListStatus(controls[0]).key).toBe("pass");
    expect(controlListStatus(controls[2]).key).toBe("not_run");
  });

  test("kpi severity thresholds", () => {
    expect(kpiSeverityForReadiness(85)).toBe("success");
    expect(kpiSeverityForReadiness(65)).toBe("warning");
    expect(kpiSeverityForPassRate(90)).toBe("success");
    expect(kpiSeverityForPassRate(50)).toBe("critical");
  });

  test("formatRelativeRun returns human labels", () => {
    const recent = new Date();
    recent.setDate(recent.getDate() - 2);
    expect(formatRelativeRun(recent.toISOString())).toMatch(/ago|Today/);
    expect(formatRelativeRun(null)).toBeNull();
  });
});
