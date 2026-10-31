import type { ApiErrorCode } from "@/lib/api/errors";
import { errorKey } from "./api";

export type DeleteResult = { ok: true } | { ok: false; key: ApiErrorCode };

// One confirmed delete: the row goes away only on { ok: true }. A refusal (RUN_IN_PROGRESS, UPLOAD_IN_USE) or any other
// failure comes back as the `apiErrors` key to show, never as server text.
export async function confirmDelete(run: () => Promise<void>): Promise<DeleteResult> {
  try {
    await run();
    return { ok: true };
  } catch (caught) {
    return { ok: false, key: errorKey(caught) };
  }
}
