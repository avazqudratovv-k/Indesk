import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api/errors";
import { freePill, loadUsage, parseUsage } from "./api";

const ok = (body: unknown) => (async () => body) as never;

describe("parseUsage", () => {
  it("reads the free-run counts of the Free plan", () => {
    expect(parseUsage({ plan: "free", free_runs_total: 3, free_runs_used: 1, free_runs_left: 2 })).toEqual({ plan: "free", free: { total: 3, left: 2 } });
    expect(parseUsage({ plan: "free", free_runs_total: 3, free_runs_used: 3, free_runs_left: 0 })?.free).toEqual({ total: 3, left: 0 });
  });

  it("has no free counts on other plans", () => {
    expect(parseUsage({ plan: "pro", free_runs_total: null, free_runs_used: null, free_runs_left: null })).toEqual({ plan: "pro", free: null });
  });

  it("is null for a body it cannot trust, so no number is shown", () => {
    for (const bad of [null, "x", [], {}, { plan: 3 }, { plan: "free" }, { plan: "free", free_runs_total: "3", free_runs_left: 1 }, { plan: "free", free_runs_total: 3, free_runs_left: 4 }, { plan: "free", free_runs_total: 3, free_runs_left: -1 }, { plan: "free", free_runs_total: 3.5, free_runs_left: 1 }]) {
      expect(parseUsage(bad), JSON.stringify(bad)).toBeNull();
    }
  });
});

describe("loadUsage", () => {
  it("asks only GET /api/usage", async () => {
    const paths: string[] = [];
    await loadUsage(undefined, (async (path: string) => { paths.push(path); return { plan: "free", free_runs_total: 3, free_runs_left: 3 }; }) as never);
    expect(paths).toEqual(["/api/usage"]);
  });

  it("gives null, never a default count, when the request fails (401, 500, network, odd body)", async () => {
    for (const make of [() => new ApiError(401, "UNAUTHENTICATED"), () => new ApiError(500, "INTERNAL"), () => new ApiError(0, "NETWORK"), () => new Error("boom")]) {
      expect(await loadUsage(undefined, (async () => { throw make(); }) as never)).toBeNull();
    }
    expect(await loadUsage(undefined, ok({ nope: true }))).toBeNull();
  });
});

describe("freePill", () => {
  it("shows the counts only when the server gave them", () => {
    expect(freePill({ plan: "free", free: { total: 3, left: 2 } })).toEqual({ key: "usage.free", values: { left: 2, total: 3 } });
  });

  it("falls back to the plain 'Free plan' with no number when usage is unknown", () => {
    expect(freePill(null)).toEqual({ key: "usage.freeNoCount" });
    expect(freePill({ plan: "free", free: null })).toEqual({ key: "usage.freeNoCount" });
  });
});
