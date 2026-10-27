// The Seoul sample on the Ask tab: attached as a pending card, turned into a File only when Run is pressed.
// Nothing here uploads; the File goes through the normal upload path like any file the person chose.
import { checkFile, kindOf, type SlotFile } from "./validate";

// The public Seoul subway file the example report was made from.
export const SAMPLE_FILE_HREF = "/demo/seoul_subway_2026-09.csv";
export const SAMPLE_FILE_NAME = "seoul_subway_2026-09.csv";
// Byte size of the file above, shown on the card without fetching it. sample.test.ts compares it with the file on disk.
export const SAMPLE_FILE_BYTES = 264902;
// The id of the sample in the files list, so its upload status and cached upload can be found again.
export const SAMPLE_ID = "sample";

export class SampleLoadError extends Error {
  constructor() {
    super("SAMPLE_LOAD");
    this.name = "SampleLoadError";
  }
}

// GET the static asset (default fetch: the browser's own HTTP cache rules apply) and build the File.
// The same browser-side checks as for a chosen file run on it.
export async function loadSampleFile(fetchFn: typeof fetch = (input, init) => fetch(input, init)): Promise<SlotFile> {
  let blob: Blob;
  try {
    const response = await fetchFn(SAMPLE_FILE_HREF);
    if (!response.ok) throw new SampleLoadError();
    blob = await response.blob();
  } catch {
    throw new SampleLoadError();
  }
  const file = new File([blob], SAMPLE_FILE_NAME, { type: "text/csv" });
  const kind = kindOf(file);
  if (!kind || checkFile(file, { slot: "files", takenNames: new Set(), count: 0, partnerKind: null, csvOnly: true })) throw new SampleLoadError();
  return { id: SAMPLE_ID, file, kind };
}

// "The person removed the sample" is a per-user preference kept in localStorage (the user id, never the email).
// Storage may be blocked or full: every access is wrapped and the card simply shows again on the next visit.
const prefix = "indesk:sample-dismissed:";

export function readSampleDismissed(userId: string): boolean {
  try {
    return globalThis.localStorage?.getItem(`${prefix}${userId}`) === "1";
  } catch {
    return false;
  }
}

export function writeSampleDismissed(userId: string): void {
  try {
    globalThis.localStorage?.setItem(`${prefix}${userId}`, "1");
  } catch {
    // Without storage the sample comes back on reload.
  }
}

export function clearSampleDismissed(userId: string): void {
  try {
    globalThis.localStorage?.removeItem(`${prefix}${userId}`);
  } catch {
    // Nothing to do.
  }
}
