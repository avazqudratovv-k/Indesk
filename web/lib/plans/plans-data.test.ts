import { describe, expect, it } from "vitest";
import plans from "@/mocks/plans.json";
import { getMockCustomPlanOffer, getMockDemoLimits, listMockPlanOffers } from "@/mocks";
import { quoteCustomPlan } from "./calc";

describe("plans mock", () => {
  it("states the real demo limits (api/config/limits.toml)", () => {
    expect(getMockDemoLimits()).toEqual({ max_file_mb: 5, csv_rows: 20000, pdf_pages: 30, runs_per_day: 10 });
  });

  it("keeps 3 free runs and the run counts and prices", () => {
    const byPlan = Object.fromEntries(listMockPlanOffers().map((offer) => [offer.plan, offer]));
    expect(byPlan.free).toMatchObject({ runs: 3, price: 0 });
    expect(byPlan.pro).toMatchObject({ runs: 50, price: 12000 });
    expect(byPlan.payg).toMatchObject({ runs: 20, price: 6500 });
  });

  it("gives no plan its own file, row, page or retention limit", () => {
    for (const record of plans.records) {
      for (const key of ["max_file_mb", "csv_rows", "pdf_pages", "retention_days"]) expect(record, `${record.plan}.${key}`).not.toHaveProperty(key);
    }
  });

  it("has no calculator option groups, only runs and the price", () => {
    const custom = getMockCustomPlanOffer();
    expect(Object.keys(custom).sort()).toEqual(["minimum", "per_run", "runs"]);
    expect(quoteCustomPlan(100, custom).total).toBe(13000);
    expect(quoteCustomPlan(10, custom).total).toBe(12000);
  });
});
