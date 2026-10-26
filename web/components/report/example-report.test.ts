import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// The example route must stay public: it may use the example loader and nothing that needs a session.
describe("ExampleReport", () => {
  const source = readFileSync(join(__dirname, "ExampleReport.tsx"), "utf8");

  it("asks for the example only", () => {
    expect(source).toContain("loadExample");
    expect(source).not.toMatch(/loadReport\b|\/api\/(?!example)|apiClient|useSession|SessionProvider|getRun|loadUsage/);
  });

  it("never shows a login prompt", () => {
    expect(source).not.toMatch(/loginHref|kind=\{load\.status\}|kind="unauthorized"/);
  });
});

describe("the example loader", () => {
  const api = readFileSync(join(__dirname, "../../lib/report/real/api.ts"), "utf8");

  it("is asked without a session refresh", () => {
    expect(api).toMatch(/exampleRequest[^\n]*refreshOn401: false/);
  });
});
