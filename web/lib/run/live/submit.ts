import { ApiError, type ApiErrorCode, type RowLimit } from "@/lib/api/errors";
import type { CreateRunBody } from "./api";
import type { UploadedFile } from "./types";

export type SubmitFile = { id: string; file: File };
export type FileStatus = { state: "waiting" | "uploading" | "ready" | "error"; code?: ApiErrorCode; expiresAt?: number };

export type SubmitDeps = {
  upload: (file: File) => Promise<UploadedFile>;
  create: (body: CreateRunBody, idempotencyKey: string) => Promise<{ id: string }>;
  newKey: () => string;
  now: () => number;
};

// A failure the screen can explain: the generic code and, for an upload, which file it was.
export class SubmitError extends Error {
  readonly code: ApiErrorCode;
  readonly fileId: string | null;
  readonly retryAfter?: number;
  // Only on RUN_ACTIVE: the run in the way, as the server named it.
  readonly runId?: string;
  // Only on TOO_MANY_ROWS: what the server counted and its limit.
  readonly rowLimit?: RowLimit;
  constructor(code: ApiErrorCode, fileId: string | null, retryAfter?: number, runId?: string, rowLimit?: RowLimit) {
    super(code);
    this.name = "SubmitError";
    this.code = code;
    this.fileId = fileId;
    this.retryAfter = retryAfter;
    this.runId = runId;
    this.rowLimit = rowLimit;
  }
}

function toSubmitError(error: unknown, fileId: string | null): SubmitError {
  if (error instanceof SubmitError) return error;
  if (error instanceof ApiError) return new SubmitError(error.code, fileId, error.retryAfter, error.runId, error.rowLimit);
  return new SubmitError("UNKNOWN", fileId);
}

// An upload that expires within this time is sent again rather than used.
const EXPIRY_MARGIN_MS = 60_000;

export type SubmitInput = {
  files: readonly SubmitFile[];
  question: string;
  // Uploads that already succeeded for these files; filled in as the uploads finish, so a retry skips them.
  uploaded: Map<string, UploadedFile>;
  onStatus: (fileId: string, status: FileStatus) => void;
  onProgress: (done: number, total: number) => void;
};

// Upload each file (one at a time), then start the run. Returns the run id.
//
// Idempotency (the server replays a request that carries the same key): every call here makes a NEW key, so an edited
// question or a new Run press is never mistaken for the earlier request. A key is reused in one case only: the very
// same request is sent again at once after a network error, because the first one may have reached the server.
export async function submitRun(input: SubmitInput, deps: SubmitDeps): Promise<{ runId: string }> {
  const { files, uploaded } = input;
  let done = 0;
  input.onProgress(0, files.length);
  for (const item of files) {
    const known = uploaded.get(item.id);
    if (known && known.expiresAt - deps.now() > EXPIRY_MARGIN_MS) {
      input.onStatus(item.id, { state: "ready", expiresAt: known.expiresAt });
      done += 1;
      input.onProgress(done, files.length);
      continue;
    }
    input.onStatus(item.id, { state: "uploading" });
    try {
      uploaded.set(item.id, await deps.upload(item.file));
    } catch (error) {
      const failure = toSubmitError(error, item.id);
      input.onStatus(item.id, { state: "error", code: failure.code });
      throw failure;
    }
    input.onStatus(item.id, { state: "ready", expiresAt: uploaded.get(item.id)?.expiresAt });
    done += 1;
    input.onProgress(done, files.length);
  }

  const body: CreateRunBody = {
    mode: "ask",
    question: input.question.trim(),
    files: files.map((item) => ({ upload_id: (uploaded.get(item.id) as UploadedFile).id, role: "subject" as const })),
  };
  const key = deps.newKey();
  try {
    try {
      return { runId: (await deps.create(body, key)).id };
    } catch (error) {
      if (!(error instanceof ApiError) || error.code !== "NETWORK") throw error;
      return { runId: (await deps.create(body, key)).id }; // identical request, same key
    }
  } catch (error) {
    throw toSubmitError(error, null);
  }
}
