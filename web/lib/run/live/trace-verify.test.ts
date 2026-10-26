import { describe, expect, it } from "vitest";
import en from "@/messages/en.json";
import ko from "@/messages/ko.json";
import { REASONS } from "./reasons";
import { describeTrace } from "./trace";

describe("trace key verify (Cat checks the claims)", () => {
  it("is a known key", () => {
    expect(describeTrace("verify", {}).id).toBe("verify");
  });

  it("shows the counts only when both are whole numbers and verified does not exceed claims", () => {
    expect(describeTrace("verify", { claims: 5, verified: 4 })).toMatchObject({ id: "verifyCounts", values: { claims: 5, verified: 4 } });
    expect(describeTrace("verify", { claims: 3, verified: 0 }).id).toBe("verifyCounts");
    const bad: Record<string, string | number | boolean | null>[] = [{ claims: 3, verified: 4 }, { claims: 0, verified: 0 }, { claims: "5", verified: 4 }, { claims: 5 }, { claims: 5.5, verified: 1 }, { claims: -1, verified: 0 }, { claims: 5, verified: null }];
    for (const args of bad) {
      expect(describeTrace("verify", args).id, JSON.stringify(args)).toBe("verify");
    }
  });

  it("has English and Korean wording", () => {
    for (const trace of [en.workspace.trace, ko.workspace.trace] as Record<string, string>[]) {
      expect(trace.verify).toBeTruthy();
      expect(trace.verifyCounts).toContain("{verified");
    }
  });
});

describe("a failed or stopped line never shows a raw code", () => {
  it("passes only a known reason code on, and every known code has a translated head", () => {
    for (const reason of REASONS) {
      expect(describeTrace("stepFailed", { reason })).toMatchObject({ id: "stepFailedReason", values: { reason } });
      expect((en.workspace.reasons as Record<string, { head: string }>)[reason].head).toBeTruthy();
      expect((ko.workspace.reasons as Record<string, { head: string }>)[reason].head).toBeTruthy();
    }
    for (const bad of ["model_busyy", "", "<b>", "ignore previous instructions"]) {
      expect(describeTrace("stepFailed", { reason: bad })).toMatchObject({ id: "stepFailed", values: {} });
      expect(describeTrace("stopped", { reason: bad })).toMatchObject({ id: "stopped", values: {} });
    }
  });
});
