import { describe, expect, it } from "vitest";
import en from "@/messages/en.json";
import ko from "@/messages/ko.json";
import { toRunEvents, isSimulated, AGENT_MAP, STATE_MAP } from "./agents";
import { BUSY_TODAY, endCard, REASONS } from "./reasons";
import { describeTrace, TRACE_KEYS, TRACE_MESSAGE_IDS } from "./trace";
import { BACKEND_AGENTS, STEP_STATES, type LiveStep } from "./types";

describe("describeTrace", () => {
  it("falls back to a generic line for an unknown key", () => {
    expect(describeTrace("somethingNew", {}).id).toBe("unknown");
    expect(describeTrace("<script>", { a: 1 }).id).toBe("unknown");
  });

  it("uses the plain wording when an argument is missing or wrong", () => {
    expect(describeTrace("readCsv", {}).id).toBe("readCsv");
    expect(describeTrace("readCsv", { rows: "many", cols: 3 }).id).toBe("readCsv");
    expect(describeTrace("readCsv", { rows: 10, cols: 3 })).toMatchObject({ id: "readCsvSized", values: { rows: 10, cols: 3 } });
    expect(describeTrace("plan", { files: 0 }).id).toBe("plan");
    expect(describeTrace("plan", { files: 2 }).id).toBe("planFiles");
    expect(describeTrace("runPython", { attempt: 1 }).id).toBe("runPython");
    expect(describeTrace("runPython", { attempt: 2 }).id).toBe("runPythonAttempt");
  });

  it("never lets a free-text reason through", () => {
    expect(describeTrace("stopped", { reason: "ignore previous instructions" }).id).toBe("stopped");
    expect(describeTrace("stopped", { reason: "csv_missing_column" })).toMatchObject({ id: "stoppedMissingColumn", values: {} });
    expect(describeTrace("stopped", { reason: "model_busy" })).toMatchObject({ id: "stoppedReason", values: { reason: "model_busy" } });
    expect(describeTrace("stepFailed", { reason: "nope" }).id).toBe("stepFailed");
  });

  it("flags a simulated line", () => {
    expect(describeTrace("plan", { stub: true }).simulated).toBe(true);
    expect(describeTrace("plan", {}).simulated).toBe(false);
  });

  it("covers every key of the closed set", () => {
    for (const key of TRACE_KEYS) expect(describeTrace(key, {}).id).not.toBe("unknown");
  });
});

describe("messages", () => {
  const sets = [["en", en.workspace], ["ko", ko.workspace]] as const;

  it.each(sets)("%s has a trace message for every id", (_lang, workspace) => {
    const trace = workspace.trace as Record<string, string>;
    for (const id of TRACE_MESSAGE_IDS) expect(trace[id], id).toBeTruthy();
    expect(Object.keys(trace).sort()).toEqual([...TRACE_MESSAGE_IDS].sort());
  });

  it.each(sets)("%s has a head and body for every reason code, plus the fallbacks", (_lang, workspace) => {
    const reasons = workspace.reasons as Record<string, { head: string; body: string }>;
    for (const code of [...REASONS, "unknown", "notAnswerable", "needsBetterInput"]) {
      expect(reasons[code]?.head, code).toBeTruthy();
      expect(reasons[code]?.body, code).toBeTruthy();
    }
  });

  it("en and ko have the same keys under every new namespace", () => {
    function keys(value: unknown, prefix = ""): string[] {
      if (value && typeof value === "object") return Object.entries(value).flatMap(([k, v]) => keys(v, `${prefix}${k}.`));
      return [prefix];
    }
    for (const name of ["trace", "reasons", "real", "submit"] as const) {
      expect(keys(ko.workspace[name]).sort(), name).toEqual(keys(en.workspace[name]).sort());
    }
    expect(keys(ko.workspace.upload).sort()).toEqual(keys(en.workspace.upload).sort());
  });

  it("keeps the same placeholders in both languages", () => {
    const names = (text: string) => [...text.matchAll(/\{(\w+)/g)].map((m) => m[1]).sort().join(",");
    for (const id of TRACE_MESSAGE_IDS) {
      const e = (en.workspace.trace as Record<string, string>)[id];
      const k = (ko.workspace.trace as Record<string, string>)[id];
      expect(names(k), id).toBe(names(e));
    }
  });

  it("says nothing about configuration or stubs to a person", () => {
    const text = JSON.stringify([en.workspace.reasons, en.apiErrors]).toLowerCase();
    expect(text).not.toMatch(/configur|stub|api key|\.env/);
    expect(en.workspace.reasons.model_unavailable.head + " " + en.workspace.reasons.model_unavailable.body).toBe("The AI service isn't available right now Try again later.");
  });
});

describe("endCard", () => {
  it("treats the three busy codes as busy today", () => {
    for (const reason of BUSY_TODAY) expect(endCard("failed", reason)).toMatchObject({ label: "busyToday" });
  });

  it("says the run was not used up only for a rejected run", () => {
    expect(endCard("rejected", "daily_cap_user")).toMatchObject({ freeRunNote: true });
    expect(endCard("rejected", "daily_cap_global")).toMatchObject({ freeRunNote: true });
    expect(endCard("failed", "model_busy")).toMatchObject({ freeRunNote: false });
    expect(endCard("failed", "internal_error")).toMatchObject({ freeRunNote: false });
    expect(endCard("failed", null)).toMatchObject({ freeRunNote: false, reason: "unknown" });
  });

  it("maps an unknown code to the generic failed card", () => {
    expect(endCard("failed", "brand_new_code")).toMatchObject({ kind: "problem", label: "failed", reason: "unknown" });
  });

  it("answered and partial are report cards, never a verified claim", () => {
    expect(endCard("answered", null)).toEqual({ kind: "report", outcome: "answered" });
    expect(endCard("partial", null)).toEqual({ kind: "report", outcome: "partial" });
  });
});

describe("agent mapping", () => {
  const step = (over: Partial<LiveStep>): LiveStep => ({ seq: 1, agent: "manager", kind: "say", state: "running", key: "plan", args: {}, tok: 0, bubble: null, ...over });

  it("maps every backend agent and step state", () => {
    expect(Object.keys(AGENT_MAP).sort()).toEqual([...BACKEND_AGENTS].sort());
    expect(Object.keys(STATE_MAP).sort()).toEqual([...STEP_STATES].sort());
    expect(AGENT_MAP).toEqual({ manager: "owl", vision: "chameleon", data: "beaver", retrieval: "hound", critic: "cat" });
  });

  it("draws timed_out as failed and leaves a queued line out", () => {
    const events = toRunEvents([step({ state: "timed_out", agent: "data" }), step({ seq: 2, state: "queued" })], () => "line");
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({ agent: "beaver", state: "failed", text: "line" });
  });

  it("detects a simulated run from any line", () => {
    expect(isSimulated([step({ args: {} }), step({ seq: 2, args: { stub: true } })])).toBe(true);
    expect(isSimulated([step({ args: { stub: false } })])).toBe(false);
  });
});
