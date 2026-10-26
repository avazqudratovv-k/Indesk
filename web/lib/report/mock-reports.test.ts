import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { mockReportsEnabled, reportIdServed } from "./mock-reports";

describe("mockReportsEnabled", () => {
  it("is off in a production build and on in dev and test", () => {
    expect(mockReportsEnabled("production")).toBe(false);
    expect(mockReportsEnabled("development")).toBe(true);
    expect(mockReportsEnabled("test")).toBe(true);
  });
});

describe("reportIdServed", () => {
  const uuid = "11111111-1111-4111-8111-111111111111";

  it("in production serves the example and real reports, and 404s every mock id", () => {
    expect(reportIdServed("example", "production")).toBe(true);
    expect(reportIdServed(uuid, "production")).toBe(true);
    for (const mock of ["rep_01", "rep_02", "rep_03", "rep_04", "", "EXAMPLE", "../etc"]) expect(reportIdServed(mock, "production")).toBe(false);
  });

  it("in dev and test still serves the mock reports", () => {
    for (const env of ["development", "test"]) {
      expect(reportIdServed("rep_01", env)).toBe(true);
      expect(reportIdServed("example", env)).toBe(true);
      expect(reportIdServed(uuid, env)).toBe(true);
    }
  });
});

// The reports route: only the mock lookup sits behind the gate. The public example and real (UUID) reports are decided before it.
describe("the reports route", () => {
  const layout = readFileSync(join(__dirname, "../../app/reports/[id]/layout.tsx"), "utf8");
  const source = readFileSync(join(__dirname, "../../app/reports/[id]/page.tsx"), "utf8");
  const at = (needle: string) => source.indexOf(needle);

  it("answers the example and real reports before the mock gate", () => {
    const example = at("if (id === EXAMPLE_ID) return <ExampleReport />;");
    const real = at("if (isRealReportId(id)) return <RealReport id={id} />;");
    const gate = at("if (!mockReportsEnabled()) notFound();");
    const mockLookup = at("const bundle = await getReport(");
    expect(example).toBeGreaterThan(-1);
    expect(real).toBeGreaterThan(example);
    expect(gate).toBeGreaterThan(real);
    expect(mockLookup).toBeGreaterThan(gate);
  });

  it("checks the id in a layout, which runs before loading.tsx streams a 200", () => {
    expect(layout).toContain("if (!reportIdServed(id)) notFound();");
  });

  it("does not put a mock title in the tab in production", () => {
    expect(source).toMatch(/mockReportsEnabled\(\) \? currentLocale\(\)\.then/);
  });
});
