import React from "react";
import { render, screen } from "@testing-library/react";

jest.mock("../../lib/api", () => ({
  __esModule: true,
  http: {
    get: jest.fn(() => Promise.resolve({ data: { items: [] } })),
  },
}));

// Use `require` so the mock above is applied before module evaluation.
const AdminMasterAuditTrailPage = require("../AdminMasterAuditTrailPage").default;
const AdminMasterDataQualityPage = require("../AdminMasterDataQualityPage").default;

describe("Admin master pages", () => {
  test("AdminMasterAuditTrailPage renders empty state", async () => {
    render(<AdminMasterAuditTrailPage />);
    expect(await screen.findByText(/Master data audit trail/i)).toBeInTheDocument();
  });

  test("AdminMasterDataQualityPage renders", async () => {
    render(<AdminMasterDataQualityPage />);
    expect(await screen.findByText(/Master data quality/i)).toBeInTheDocument();
  });
});

