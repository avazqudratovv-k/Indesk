import { ApiError } from "@/lib/api/errors";
import { apiClient } from "@/lib/api/client";
import { parseCreated, parseRunSnapshot, parseUpload } from "./parse";
import type { RunSnapshot, UploadedFile } from "./types";

// An upload of a few MB over a slow link needs more than the client's usual 15 s.
const UPLOAD_TIMEOUT_MS = 120_000;

// A body that arrives but is not the shape we expect is treated as an unknown server error (the text is never shown).
function unexpected(): ApiError {
  return new ApiError(502, "UNKNOWN");
}

export async function uploadCsv(file: File, signal?: AbortSignal): Promise<UploadedFile> {
  const form = new FormData();
  form.append("file", file);
  form.append("consent", "true"); // the person ticked the consent box before Run was possible
  const raw = await apiClient().request<unknown>("/api/uploads", { method: "POST", form, timeoutMs: UPLOAD_TIMEOUT_MS, signal });
  const upload = parseUpload(raw);
  if (!upload) throw unexpected();
  return upload;
}

export type CreateRunBody = { mode: "ask"; question: string; files: { upload_id: string; role: "subject" }[] };

export async function createRun(body: CreateRunBody, idempotencyKey: string): Promise<{ id: string }> {
  const raw = await apiClient().request<unknown>("/api/runs", { method: "POST", json: body, headers: { "Idempotency-Key": idempotencyKey } });
  const created = parseCreated(raw);
  if (!created) throw unexpected();
  return created;
}

export async function getRun(id: string, signal?: AbortSignal): Promise<RunSnapshot> {
  const raw = await apiClient().request<unknown>(`/api/runs/${encodeURIComponent(id)}`, { signal });
  const run = parseRunSnapshot(raw);
  if (!run) throw unexpected();
  return run;
}
