import { graphNodeDrillPath, exceptionSourceDrillPath } from "../drillPaths";

describe("graphNodeDrillPath", () => {
  it("uses evidence_source_type for customer ids without CUST- prefix match in heuristics", () => {
    const p = graphNodeDrillPath({
      type: "transaction",
      id: "CUST-1001",
      meta: { evidence_source_type: "customer", customer_name: "Acme" },
    });
    expect(p).toBe("/app/drill/customer/CUST-1001");
  });

  it("falls back to case-insensitive INV prefix when meta is absent", () => {
    expect(graphNodeDrillPath({ type: "transaction", id: "no-prefix-uuid", meta: {} })).toBeNull();
    expect(graphNodeDrillPath({ type: "transaction", id: "inv-20001", meta: {} })).toBe(
      "/app/drill/invoice/inv-20001"
    );
  });

  it("routes access_event via user_email on meta", () => {
    expect(
      graphNodeDrillPath({
        type: "transaction",
        id: "UA-0",
        meta: { evidence_source_type: "access_event", user_email: "controller@onetouch.ai" },
      })
    ).toBe("/app/drill/user/controller%40onetouch.ai");
  });

  it("exceptionSourceDrillPath prefers source_record_user_email for access_event", () => {
    const p = exceptionSourceDrillPath({
      source_record_type: "access_event",
      source_record_id: "UA-17",
      source_record_user_email: "old.user@onetouch.ai",
    });
    expect(p).toBe("/app/drill/user/old.user%40onetouch.ai");
  });

  it("routes reconciliation to reconciliation detail route", () => {
    expect(
      graphNodeDrillPath({
        type: "transaction",
        id: "REC-001",
        meta: { evidence_source_type: "reconciliation" },
      })
    ).toBe("/app/reconciliations/REC-001");
  });
});
