import { describe, expect, it, vi } from "vitest";
import en from "@/messages/en.json";
import ko from "@/messages/ko.json";
import { ApiError } from "@/lib/api/errors";
import { alreadyGone, deleteFile, deleteReport, errorKey, hoursLeft, loadFiles, loadReports, parseFileRow, parseFiles, parseReportRow, parseReportsPage } from "./api";
import { confirmDelete } from "./delete-flow";

const id = "11111111-1111-4111-8111-111111111111";
const id2 = "22222222-2222-4222-8222-222222222222";

const report = (extra: Record<string, unknown> = {}) => ({
  id,
  title: "Fastest-growing stations",
  created_at: "2026-10-30T08:00:00Z",
  expires_at: "2026-11-06T08:00:00Z",
  verified_count: 5,
  total_claims: 6,
  outcome: "answered",
  language: "en",
  file_kind: "csv",
  file_count: 2,
  ...extra,
});

const upload = (extra: Record<string, unknown> = {}) => ({
  id,
  user_id: id2,
  filename: "seoul.csv",
  mime: "text/csv",
  size: 1_800_000,
  page_count: null,
  row_count: 4200,
  status: "ready",
  moderation: "passed",
  created_at: "2026-10-31T01:00:00Z",
  expires_at: "2026-11-01T01:00:00Z",
  ...extra,
});

describe("parseReportRow", () => {
  it("reads a valid row and ignores unknown fields", () => {
    const row = parseReportRow(report({ owner_id: "x", summary: "secret" }));
    expect(row).toEqual({
      id,
      title: "Fastest-growing stations",
      createdAt: "2026-10-30T08:00:00Z",
      expiresAt: "2026-11-06T08:00:00Z",
      verified: 5,
      total: 6,
      outcome: "answered",
      fileKind: "csv",
      fileCount: 2,
    });
    expect(JSON.stringify(row)).not.toContain("secret");
  });

  it("accepts a partial outcome and a null file kind", () => {
    expect(parseReportRow(report({ outcome: "partial", file_kind: null }))).toMatchObject({ outcome: "partial", fileKind: null });
  });

  it.each([
    ["not an object", "text"],
    ["an array", []],
    ["a bad id", report({ id: "rep_01" })],
    ["a missing title", report({ title: undefined })],
    ["an empty title after cleaning", report({ title: "‮​  " })],
    ["a number title", report({ title: 7 })],
    ["a bad date", report({ created_at: "yesterday" })],
    ["a negative count", report({ verified_count: -1 })],
    ["a fractional count", report({ total_claims: 2.5 })],
    ["more verified than total", report({ verified_count: 7 })],
    ["an unknown outcome", report({ outcome: "failed" })],
    ["an unknown file kind", report({ file_kind: "exe" })],
    ["a string file count", report({ file_count: "2" })],
  ])("drops a row with %s", (_name, raw) => {
    expect(parseReportRow(raw)).toBeNull();
  });

  it("strips control and direction characters and caps a very long title", () => {
    expect(parseReportRow(report({ title: "a‮b\nc" }))?.title).toBe("ab c");
    const long = parseReportRow(report({ title: "x".repeat(5000) }))?.title ?? "";
    expect(long.length).toBeLessThanOrEqual(200);
    expect(long.endsWith("…")).toBe(true);
  });
});

describe("parseReportsPage", () => {
  it("keeps good rows, drops bad ones and keeps the cursor", () => {
    const page = parseReportsPage({ items: [report(), { nope: 1 }, report({ id: id2 })], next_cursor: "abc" });
    expect(page?.items.map((r) => r.id)).toEqual([id, id2]);
    expect(page?.nextCursor).toBe("abc");
  });

  it("accepts the last page", () => {
    expect(parseReportsPage({ items: [], next_cursor: null })).toEqual({ items: [], nextCursor: null });
  });

  it.each([
    ["no items", { next_cursor: null }],
    ["items that are not a list", { items: {}, next_cursor: null }],
    ["a missing cursor", { items: [] }],
    ["an empty cursor", { items: [], next_cursor: "" }],
    ["an oversize cursor", { items: [], next_cursor: "c".repeat(513) }],
    ["a body that is not an object", null],
  ])("rejects a page with %s", (_name, raw) => {
    expect(parseReportsPage(raw)).toBeNull();
  });
});

describe("parseFileRow", () => {
  it("reads a valid upload and ignores internal-looking extra fields", () => {
    const row = parseFileRow(upload({ storage_key: "k", sha256: "h" }));
    expect(row).toEqual({ id, name: "seoul.csv", kind: "csv", size: 1_800_000, pages: null, rows: 4200, deleted: false, expiresAt: "2026-11-01T01:00:00Z" });
    expect(JSON.stringify(row)).not.toContain("storage_key");
  });

  it("marks a deleted upload and reads a PDF's pages", () => {
    expect(parseFileRow(upload({ mime: "application/pdf", page_count: 12, row_count: null, status: "deleted" }))).toMatchObject({ kind: "pdf", pages: 12, rows: null, deleted: true });
  });

  it.each([
    ["an unknown mime", upload({ mime: "application/zip" })],
    ["an unknown status", upload({ status: "weird" })],
    ["a negative size", upload({ size: -5 })],
    ["a bad id", upload({ id: "nope" })],
    ["a bad expiry", upload({ expires_at: "soon" })],
    ["a name that is only control characters", upload({ filename: "\u0000​" })],
    ["a string row count", upload({ row_count: "4200" })],
  ])("drops a row with %s", (_name, raw) => {
    expect(parseFileRow(raw)).toBeNull();
  });

  it("caps a very long file name", () => {
    expect(parseFileRow(upload({ filename: "n".repeat(1000) }))?.name.length).toBeLessThanOrEqual(255);
  });

  it("parseFiles drops bad rows and rejects a body that is not a list", () => {
    expect(parseFiles([upload(), 3, upload({ id: id2 })])?.length).toBe(2);
    expect(parseFiles({ items: [] })).toBeNull();
  });
});

describe("requests", () => {
  it("asks for the first page without a cursor and follows next_cursor on the next", async () => {
    const request = vi.fn().mockResolvedValue({ items: [], next_cursor: null });
    await loadReports(null, undefined, request);
    await loadReports("c/1 2", undefined, request);
    expect(request.mock.calls[0][0]).toBe("/api/reports?limit=20");
    expect(request.mock.calls[1][0]).toBe("/api/reports?limit=20&cursor=c%2F1+2");
  });

  it("throws on a malformed list body so the screen shows its error state", async () => {
    await expect(loadReports(null, undefined, vi.fn().mockResolvedValue({ items: "x" }))).rejects.toBeInstanceOf(ApiError);
    await expect(loadFiles(undefined, vi.fn().mockResolvedValue({}))).rejects.toBeInstanceOf(ApiError);
  });

  it("asks for uploads including deleted ones", async () => {
    const request = vi.fn().mockResolvedValue([upload()]);
    expect(await loadFiles(undefined, request)).toHaveLength(1);
    expect(request.mock.calls[0][0]).toBe("/api/uploads?limit=100&include_deleted=true");
  });

  it("sends DELETE to the report and upload paths", async () => {
    const request = vi.fn().mockResolvedValue(undefined);
    await deleteReport(id, request);
    await deleteFile(id2, request);
    expect(request).toHaveBeenNthCalledWith(1, `/api/reports/${id}`, { method: "DELETE" });
    expect(request).toHaveBeenNthCalledWith(2, `/api/uploads/${id2}`, { method: "DELETE" });
  });

  it("treats a 404 on delete as already gone, and passes other errors on", async () => {
    await expect(deleteReport(id, vi.fn().mockRejectedValue(new ApiError(404, "NOT_FOUND")))).resolves.toBeUndefined();
    await expect(deleteReport(id, vi.fn().mockRejectedValue(new ApiError(409, "RUN_IN_PROGRESS")))).rejects.toMatchObject({ code: "RUN_IN_PROGRESS" });
    expect(alreadyGone(new ApiError(409, "UPLOAD_IN_USE"))).toBe(false);
  });
});

describe("the delete confirm flow", () => {
  it("succeeds when the server says yes", async () => {
    expect(await confirmDelete(() => Promise.resolve())).toEqual({ ok: true });
  });

  it("returns RUN_IN_PROGRESS for a report whose run is still going", async () => {
    expect(await confirmDelete(() => deleteReport(id, vi.fn().mockRejectedValue(new ApiError(409, "RUN_IN_PROGRESS"))))).toEqual({ ok: false, key: "RUN_IN_PROGRESS" });
  });

  it("returns UPLOAD_IN_USE for a file a run still uses", async () => {
    expect(await confirmDelete(() => deleteFile(id, vi.fn().mockRejectedValue(new ApiError(409, "UPLOAD_IN_USE"))))).toEqual({ ok: false, key: "UPLOAD_IN_USE" });
  });

  it("returns a generic key for network and unexpected failures, never the error text", async () => {
    expect(await confirmDelete(() => Promise.reject(new ApiError(0, "NETWORK")))).toEqual({ ok: false, key: "NETWORK" });
    expect(await confirmDelete(() => Promise.reject(new Error("stack trace here")))).toEqual({ ok: false, key: "UNKNOWN" });
    expect(errorKey("boom")).toBe("UNKNOWN");
  });

  it("has an English and a Korean message for every key it can return", () => {
    for (const m of [en, ko]) {
      for (const key of ["RUN_IN_PROGRESS", "UPLOAD_IN_USE", "NETWORK", "UNKNOWN"] as const) expect(m.apiErrors[key].length).toBeGreaterThan(0);
    }
    expect(en.apiErrors.RUN_IN_PROGRESS).not.toBe(en.apiErrors.UPLOAD_IN_USE);
  });
});

describe("hoursLeft", () => {
  const now = Date.parse("2026-10-31T00:00:00Z");

  it("rounds up to whole hours and never shows less than 1", () => {
    expect(hoursLeft("2026-10-31T17:00:00Z", now)).toBe(17);
    expect(hoursLeft("2026-10-31T16:00:01Z", now)).toBe(17);
    expect(hoursLeft("2026-10-31T00:10:00Z", now)).toBe(1);
  });

  it("is null once the time has passed", () => {
    expect(hoursLeft("2026-10-31T00:00:00Z", now)).toBeNull();
    expect(hoursLeft("2026-10-30T00:00:00Z", now)).toBeNull();
  });
});
