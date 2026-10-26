import { describe, expect, it } from "vitest";
import type { AgentView } from "@/lib/run/mock-run";
import { endedKey, tabStatus } from "./agent-status";

const view = (state: AgentView["state"]): AgentView => ({ state, flags: 0 });

describe("unbuilt agents in a real run", () => {
  it("show Coming later for Chameleon and Hound, whatever their idle state", () => {
    for (const id of ["chameleon", "hound"] as const) {
      for (const state of ["waiting", "skipped"] as const) {
        for (const finished of [false, true]) {
          expect(endedKey(id, view(state), finished, true)).toBe("comingLater");
          expect(tabStatus(id, view(state), finished, true)).toBe("comingLater");
        }
      }
    }
  });

  it("keep the real states of built agents", () => {
    expect(endedKey("beaver", view("waiting"), true, true)).toBe("didNotRun");
    expect(tabStatus("beaver", view("skipped"), true, true)).toBe("didNotRun");
    expect(tabStatus("owl", view("done"), true, true)).toBe("done");
    expect(endedKey("cat", view("failed"), true, true)).toBe("failed");
  });

  it("leave the mock run unchanged", () => {
    expect(endedKey("chameleon", view("waiting"), true)).toBe("didNotRun");
    expect(tabStatus("hound", view("skipped"), true)).toBe("didNotRun");
  });
});
