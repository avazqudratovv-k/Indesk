import { describe, expect, it } from "vitest";
import type { AgentView } from "@/lib/run/mock-run";
import { endedKey, tabStatus } from "./agent-status";

const view = (state: AgentView["state"]): AgentView => ({ state, flags: 0 });

describe("unbuilt agents in a real run", () => {
  it("show Not available yet for Chameleon, whatever their idle state", () => {
    for (const id of ["chameleon"] as const) {
      for (const state of ["waiting", "skipped"] as const) {
        for (const finished of [false, true]) {
          expect(endedKey(id, view(state), finished, true)).toBe("comingLater");
          expect(tabStatus(id, view(state), finished, true)).toBe("comingLater");
        }
      }
    }
  });

  it("show Hound as real: working and done keep their state, and in a CSV run it is Not used, and a run that ended before it started says Did not start", () => {
    expect(tabStatus("hound", view("working"), false, true)).toBe("working");
    expect(tabStatus("hound", view("done"), true, true)).toBe("done");
    expect(tabStatus("hound", view("waiting"), false, true)).toBe("waiting");
    expect(tabStatus("hound", view("skipped"), true, true)).toBe("notUsed");
    expect(tabStatus("hound", view("waiting"), true, true)).toBe("didNotRun");
    expect(endedKey("hound", view("waiting"), true, true)).toBe("didNotRun");
  });

  it("keep the real states of built agents", () => {
    expect(endedKey("beaver", view("waiting"), true, true)).toBe("didNotRun");
    expect(tabStatus("beaver", view("skipped"), true, true)).toBe("notUsed");
    expect(tabStatus("owl", view("done"), true, true)).toBe("done");
    expect(endedKey("cat", view("failed"), true, true)).toBe("failed");
  });

  it("leave the mock run unchanged", () => {
    expect(endedKey("chameleon", view("waiting"), true)).toBe("didNotRun");
    expect(tabStatus("hound", view("skipped"), true)).toBe("didNotRun");
  });
});
