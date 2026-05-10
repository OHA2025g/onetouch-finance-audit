import React from "react";
import { render, screen } from "@testing-library/react";

jest.mock("../../lib/api", () => ({
  __esModule: true,
  http: {
    get: jest.fn(),
    post: jest.fn(),
  },
}));

jest.mock("../../lib/MastersFilterContext", () => ({
  __esModule: true,
  useMastersFilters: () => ({
    entityCode: "",
    periodYm: "2026-04",
    periodExplicit: false,
    departmentId: "",
    costCenterId: "",
    hrefWithMasterParams: (p) => p,
  }),
}));

jest.mock("../../components/filters/MastersFilterStrip", () => ({
  __esModule: true,
  default: () => null,
}));

// require() ensures mocks apply before module eval
const ReceivablesArAgeingPage = require("../ReceivablesArAgeingPage").default;
const PayablesApAgeingPage = require("../PayablesApAgeingPage").default;
const CashForecast13WeekPage = require("../CashForecast13WeekPage").default;
const BudgetMasterPage = require("../BudgetMasterPage").default;
const BudgetVsActualPage = require("../BudgetVsActualPage").default;
const ForecastAccuracyPage = require("../ForecastAccuracyPage").default;

function renderPage(ui) {
  return render(ui);
}

describe("Phase 9–14 dedicated pages render", () => {
  beforeEach(() => {
    const { http } = require("../../lib/api");
    http.get.mockResolvedValue({ data: { items: [], count: 0, total: 0, kpis: {}, data: { kpis: {} }, weeks: [] } });
    http.post.mockResolvedValue({ data: { status: "ok" } });
  });

  test("ReceivablesArAgeingPage renders", async () => {
    renderPage(<ReceivablesArAgeingPage />);
    expect(await screen.findByTestId("ar-receivables-page")).toBeInTheDocument();
  });

  test("PayablesApAgeingPage renders", async () => {
    renderPage(<PayablesApAgeingPage />);
    expect(await screen.findByTestId("ap-payables-page")).toBeInTheDocument();
  });

  test("CashForecast13WeekPage renders", async () => {
    renderPage(<CashForecast13WeekPage />);
    expect(await screen.findByTestId("cash-forecast-page")).toBeInTheDocument();
  });

  test("BudgetMasterPage renders", async () => {
    renderPage(<BudgetMasterPage />);
    expect(await screen.findByTestId("budget-master-page")).toBeInTheDocument();
  });

  test("BudgetVsActualPage renders", async () => {
    renderPage(<BudgetVsActualPage />);
    expect(await screen.findByTestId("budget-vs-actual-page")).toBeInTheDocument();
  });

  test("ForecastAccuracyPage renders", async () => {
    renderPage(<ForecastAccuracyPage />);
    expect(await screen.findByTestId("forecast-accuracy-page")).toBeInTheDocument();
  });
});

