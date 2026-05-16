import { toProperHeadingLabel } from "../headingCase";

describe("toProperHeadingLabel", () => {
  it("title-cases all-caps kickers and middot segments", () => {
    expect(toProperHeadingLabel("CONTINUOUS AUDIT · PHASE 35")).toBe("Continuous Audit · Phase 35");
  });

  it("preserves acronyms", () => {
    expect(toProperHeadingLabel("CFO COCKPIT")).toBe("CFO Cockpit");
    expect(toProperHeadingLabel("FP&A SNAPSHOT")).toBe("FP&A Snapshot");
    expect(toProperHeadingLabel("SAP CONNECTOR")).toBe("SAP Connector");
  });

  it("leaves Home and mixed labels sensible", () => {
    expect(toProperHeadingLabel("Home")).toBe("Home");
    expect(toProperHeadingLabel("CFO Cockpit")).toBe("CFO Cockpit");
  });

  it("coerces non-strings without throwing (StatCard / API edge cases)", () => {
    expect(toProperHeadingLabel(404)).toBe("404");
    expect(toProperHeadingLabel("ROLLUP-ITEM")).toBe("Rollup-Item");
  });
});
