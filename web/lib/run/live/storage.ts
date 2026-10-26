// The id of the person's latest run, so a reload or a second tab can find it again. Only the run id (a UUID) is
// stored, never the question or any server text, and it is keyed by user id so nobody sees another account's run.
// localStorage may be blocked or full: every access is wrapped and the screen works without it.
import { isRunId } from "./parse";

const prefix = "indesk:run:";

function key(userId: string): string {
  return `${prefix}${userId}`;
}

export function readRunId(userId: string): string | null {
  try {
    const value = globalThis.localStorage?.getItem(key(userId)) ?? null;
    return isRunId(value) ? value : null;
  } catch {
    return null;
  }
}

export function writeRunId(userId: string, runId: string): void {
  try {
    if (isRunId(runId)) globalThis.localStorage?.setItem(key(userId), runId);
  } catch {
    // Without storage a reload simply starts from the empty Ask tab.
  }
}

export function clearRunId(userId: string): void {
  try {
    globalThis.localStorage?.removeItem(key(userId));
  } catch {
    // Nothing to do.
  }
}
