import { describe, expect, it } from "vitest";
import { runSeconds } from "@/components/workspace/run/RunTiles";
import { parseRunSnapshot } from "./parse";

const T0 = Date.parse("2026-10-31T10:00:00Z");
const MIN10 = 10 * 60 * 1000;
const base = { id: "11111111-1111-4111-8111-111111111111", status: "running", started_at: "2026-10-31T10:00:00Z" };

describe("runSeconds", () => {
  it("finished run uses server times only", () => {
    expect(runSeconds({ startMs: T0, endMs: T0 + 12_500, offsetMs: MIN10 }, 0)).toBe(12.5);
  });
  it("running with an offset uses browser now plus offset", () => {
    expect(runSeconds({ startMs: T0, endMs: null, offsetMs: 5000 }, T0 + 3000)).toBe(8);
  });
  it("running without an offset uses the browser clock", () => {
    expect(runSeconds({ startMs: T0, endMs: null }, T0 + 3000)).toBe(3);
    expect(runSeconds({ startMs: T0, endMs: null, offsetMs: null }, T0 + 3000)).toBe(3);
  });
  it("browser clock 10 minutes ahead is corrected by the offset", () => {
    const browser = T0 + 4000 + MIN10;
    expect(runSeconds({ startMs: T0, endMs: null, offsetMs: -MIN10 }, browser)).toBe(4);
  });
  it("browser clock 10 minutes behind is corrected by the offset", () => {
    const browser = T0 + 4000 - MIN10;
    expect(runSeconds({ startMs: T0, endMs: null, offsetMs: MIN10 }, browser)).toBe(4);
  });
  it("never negative", () => {
    expect(runSeconds({ startMs: T0, endMs: null }, T0 - 5000)).toBe(0);
    expect(runSeconds({ startMs: T0, endMs: T0 - 1 }, 0)).toBe(0);
  });
  it("missing or malformed times give null", () => {
    expect(runSeconds({ startMs: null, endMs: null }, T0)).toBeNull();
    expect(runSeconds({ startMs: Number.NaN, endMs: null }, T0)).toBeNull();
    expect(runSeconds({ startMs: T0, endMs: null, offsetMs: Number.NaN }, T0)).toBeNull();
  });
});

describe("server_now in the run view parser", () => {
  it("offset is server_now minus arrival time", () => {
    expect(parseRunSnapshot({ ...base, server_now: "2026-10-31T10:00:05Z" }, T0)?.clockOffsetMs).toBe(5000);
    expect(parseRunSnapshot({ ...base, server_now: "2026-10-31T10:00:00Z" }, T0 + MIN10)?.clockOffsetMs).toBe(-MIN10);
  });
  it("missing or invalid server_now means no offset, not an error", () => {
    expect(parseRunSnapshot(base, T0)?.clockOffsetMs).toBeNull();
    for (const bad of ["nope", 5, null, {}, ""]) expect(parseRunSnapshot({ ...base, server_now: bad }, T0)?.clockOffsetMs).toBeNull();
  });
});
