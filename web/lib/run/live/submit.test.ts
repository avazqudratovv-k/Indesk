import { describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/errors";
import { SubmitError, submitRun, type FileStatus, type SubmitDeps, type SubmitFile } from "./submit";
import type { UploadedFile } from "./types";

const file = (id: string, name = `${id}.csv`): SubmitFile => ({ id, file: new File(["a,b\n1,2"], name, { type: "text/csv" }) });

function setup(over: Partial<SubmitDeps> = {}) {
  let keyNumber = 0;
  const calls: { body: unknown; key: string }[] = [];
  const deps: SubmitDeps = {
    upload: vi.fn(async (f: File) => ({ id: `up-${f.name}`, expiresAt: 10_000_000, rowCount: 1 }) satisfies UploadedFile),
    create: vi.fn(async (body, key) => {
      calls.push({ body, key });
      return { id: "run-1" };
    }),
    newKey: () => `key-${++keyNumber}`,
    now: () => 1_000,
    ...over,
  };
  const statuses: Record<string, FileStatus> = {};
  const input = (files: SubmitFile[], question: string, uploaded = new Map<string, UploadedFile>()) => ({
    files,
    question,
    uploaded,
    onStatus: (id: string, status: FileStatus) => {
      statuses[id] = status;
    },
    onProgress: () => {},
  });
  return { deps, calls, statuses, input };
}

describe("submitRun", () => {
  it("uploads each file once, then creates one Ask run with the uploads as subjects", async () => {
    const t = setup();
    const result = await submitRun(t.input([file("a"), file("b")], "  What changed?  "), t.deps);
    expect(result.runId).toBe("run-1");
    expect(t.deps.upload).toHaveBeenCalledTimes(2);
    expect(t.calls[0].body).toEqual({ mode: "ask", question: "What changed?", files: [{ upload_id: "up-a.csv", role: "subject" }, { upload_id: "up-b.csv", role: "subject" }] });
    expect(t.statuses.a.state).toBe("ready");
  });

  it("does not upload a file again on a retry", async () => {
    const t = setup();
    const uploaded = new Map<string, UploadedFile>();
    await submitRun(t.input([file("a")], "one", uploaded), t.deps);
    await submitRun(t.input([file("a")], "two", uploaded), t.deps);
    expect(t.deps.upload).toHaveBeenCalledTimes(1);
  });

  it("uploads again when the earlier upload is about to expire", async () => {
    const t = setup();
    const uploaded = new Map<string, UploadedFile>([["a", { id: "old", expiresAt: 1_000 + 30_000, rowCount: 1 }]]);
    await submitRun(t.input([file("a")], "q", uploaded), t.deps);
    expect(t.deps.upload).toHaveBeenCalledTimes(1);
  });

  it("an edited question gets a new Idempotency-Key", async () => {
    const t = setup();
    const uploaded = new Map<string, UploadedFile>();
    await submitRun(t.input([file("a")], "first question", uploaded), t.deps);
    await submitRun(t.input([file("a")], "edited question", uploaded), t.deps);
    expect(t.calls.map((c) => c.key)).toEqual(["key-1", "key-2"]);
  });

  it("pressing Run again with the same question is also a new attempt, so a new key", async () => {
    const t = setup();
    const uploaded = new Map<string, UploadedFile>();
    await submitRun(t.input([file("a")], "same", uploaded), t.deps);
    await submitRun(t.input([file("a")], "same", uploaded), t.deps);
    expect(new Set(t.calls.map((c) => c.key)).size).toBe(2);
  });

  it("re-sends the identical request with the SAME key after a network error, once", async () => {
    let attempts = 0;
    const t = setup({
      create: vi.fn(async (_body, key) => {
        attempts += 1;
        t.calls.push({ body: _body, key });
        if (attempts === 1) throw new ApiError(0, "NETWORK");
        return { id: "run-9" };
      }),
    });
    const result = await submitRun(t.input([file("a")], "q"), t.deps);
    expect(result.runId).toBe("run-9");
    expect(t.calls).toHaveLength(2);
    expect(t.calls[1].key).toBe(t.calls[0].key);
    expect(t.calls[1].body).toEqual(t.calls[0].body);
  });

  it("gives up after the one automatic re-send", async () => {
    const t = setup({ create: vi.fn(async () => { throw new ApiError(0, "NETWORK"); }) });
    await expect(submitRun(t.input([file("a")], "q"), t.deps)).rejects.toMatchObject({ code: "NETWORK" });
    expect(t.deps.create).toHaveBeenCalledTimes(2);
  });

  it.each(["RUN_ACTIVE", "UPLOAD_NOT_READY", "MODE_NOT_AVAILABLE", "RATE_LIMITED"] as const)("does not re-send after %s", async (code) => {
    const t = setup({ create: vi.fn(async () => { throw new ApiError(code === "RATE_LIMITED" ? 429 : 409, code, code === "RATE_LIMITED" ? 60 : undefined); }) });
    await expect(submitRun(t.input([file("a")], "q"), t.deps)).rejects.toMatchObject({ code });
    expect(t.deps.create).toHaveBeenCalledTimes(1);
  });

  it("passes the run_id of RUN_ACTIVE on to the screen", async () => {
    const runId = "11111111-1111-4111-8111-111111111111";
    const t = setup({ create: vi.fn(async () => { throw new ApiError(409, "RUN_ACTIVE", undefined, runId); }) });
    await expect(submitRun(t.input([file("a")], "q"), t.deps)).rejects.toMatchObject({ code: "RUN_ACTIVE", runId });
  });

  it("names the file whose upload failed and stops before the run request", async () => {
    const t = setup({ upload: vi.fn(async (f: File) => { if (f.name === "bad.csv") throw new ApiError(422, "BAD_CSV"); return { id: "x", expiresAt: 9_999_999, rowCount: 1 }; }) });
    const error = await submitRun(t.input([file("a"), file("b", "bad.csv"), file("c")], "q"), t.deps).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(SubmitError);
    expect(error).toMatchObject({ code: "BAD_CSV", fileId: "b" });
    expect(t.deps.create).not.toHaveBeenCalled();
    expect(t.deps.upload).toHaveBeenCalledTimes(2);
    expect(t.statuses.b).toEqual({ state: "error", code: "BAD_CSV" });
  });

  it("keeps the retry-after of a rate limit", async () => {
    const t = setup({ upload: vi.fn(async () => { throw new ApiError(429, "RATE_LIMITED", 90); }) });
    await expect(submitRun(t.input([file("a")], "q"), t.deps)).rejects.toMatchObject({ code: "RATE_LIMITED", retryAfter: 90 });
  });
});
