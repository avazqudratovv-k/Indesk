import { describe, expect, it } from "vitest";
import { parseDone, parseRunSnapshot, parseStep } from "./parse";

const good = { seq: 1, agent: "manager", kind: "say", state: "running", key: "plan", args: { stub: true, files: 1 }, tok: 0, bubble: "owlSplit" };

describe("parseStep", () => {
  it("accepts a well-formed step", () => {
    expect(parseStep(good)).toMatchObject({ seq: 1, agent: "manager", key: "plan", bubble: "owlSplit" });
  });

  it.each([
    ["unknown agent", { ...good, agent: "dog" }],
    ["unknown state", { ...good, state: "sleeping" }],
    ["bad key", { ...good, key: "has space" }],
    ["negative seq", { ...good, seq: -1 }],
    ["fractional seq", { ...good, seq: 1.5 }],
    ["not an object", "text"],
  ])("drops %s", (_name, value) => {
    expect(parseStep(value)).toBeNull();
  });

  it("keeps only plain argument values", () => {
    const step = parseStep({ ...good, args: { rows: 3, nested: { a: 1 }, list: [1], "bad key": 1, text: "x" } });
    expect(step?.args).toEqual({ rows: 3, text: "x" });
  });

  it("drops an unknown bubble instead of keeping it", () => {
    expect(parseStep({ ...good, bubble: "<b>hi</b>" })?.bubble).toBeNull();
  });
});

describe("parseDone and parseRunSnapshot", () => {
  it("reads outcome, reason and report id", () => {
    expect(parseDone({ outcome: "failed", reason: "internal_error", report_id: null })).toEqual({ outcome: "failed", reason: "internal_error", reportId: null });
    expect(parseDone({ outcome: "made_up" })).toBeNull();
  });

  it("needs a uuid run id and a known status", () => {
    const id = "123e4567-e89b-12d3-a456-426614174000";
    expect(parseRunSnapshot({ id, status: "running", steps: [good, { nope: 1 }] })?.steps).toHaveLength(1);
    expect(parseRunSnapshot({ id: "r1", status: "running" })).toBeNull();
    expect(parseRunSnapshot({ id, status: "weird" })).toBeNull();
  });
});
