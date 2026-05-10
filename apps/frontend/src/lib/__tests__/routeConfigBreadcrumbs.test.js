import { labelForPath } from "../routeConfig";

describe("labelForPath (breadcrumbs)", () => {
  it("uses workspace instead of generic App for /app", () => {
    expect(labelForPath("/app")).toBe("Workspace");
  });

  it("uses distinct labels for finance-operations hub vs month-end close", () => {
    expect(labelForPath("/app/finance-operations")).toBe("Finance operations");
    expect(labelForPath("/app/finance-operations/month-end-close")).toBe("Month-end close");
    expect(labelForPath("/app/finance-operations/month-end-close/cycle-2025-03")).toBe("Month-end close");
  });

  it("labels KPI and cases with identifiers", () => {
    expect(labelForPath("/app/kpi/revenue_yoy")).toBe("KPI · revenue yoy");
    expect(labelForPath("/app/cases/case-uuid-123")).toBe("Case · case-uuid-123");
  });

  it("respects executive-review tab in query on leaf path", () => {
    expect(labelForPath("/app/executive-review?tab=assurance")).toBe(
      "Executive review · Continuous assurance"
    );
  });
});
