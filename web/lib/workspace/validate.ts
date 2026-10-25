// Browser-side checks for the Workspace upload area (ROADMAP 2.5). Files never leave the browser in this step;
// the server repeats every one of these checks later (ROADMAP section 3).

export type WorkspaceMode = "ask" | "check" | "compare";
export type SlotId = "files" | "document" | "sources" | "fileA" | "fileB";
export type FileKind = "csv" | "pdf" | "image";

// Largest file on the Free plan: 5 MB, an owner decision that differs from DATA.md `uploads.size` ("Free 2 MB").
// SPEC.md does not set a number. This is the only place the size is written; the UI reads it from here.
export const MAX_FILE_BYTES = 5 * 1024 * 1024;
// DATA.md `runs.question`: "max 1,000 characters (rec)"; accepted by DECISIONS #25.
export const MAX_QUESTION_CHARS = 1000;
// Counter appears from here. Owner decision for this task, not in SPEC.
export const QUESTION_COUNTER_FROM = 800;
// DATA.md `uploads.filename`: "max 255 (rec)"; accepted by DECISIONS #25.
export const MAX_FILE_NAME_CHARS = 255;

// Files per slot. SPEC.md and DECISIONS give no counts; these are the owner's answers for task 2.5
// (Ask 5, Check 1 document + 4 sources, Compare exactly 2).
export const SLOT_MAX: Record<SlotId, number> = { files: 5, document: 1, sources: 4, fileA: 1, fileB: 1 };

export const MODE_SLOTS: Record<WorkspaceMode, SlotId[]> = {
  ask: ["files"],
  check: ["document", "sources"],
  compare: ["fileA", "fileB"],
};

// Types from DATA.md `uploads.mime` (CSV, PDF, JPG, PNG). TXT is left out on purpose: it only exists as pasted text.
const EXTENSION_KIND: Record<string, FileKind> = { csv: "csv", pdf: "pdf", jpg: "image", jpeg: "image", png: "image" };

// Browsers disagree about CSV (Windows reports Excel's type, some report nothing), so those are allowed too.
const MIME_BY_EXTENSION: Record<string, readonly string[]> = {
  csv: ["text/csv", "application/csv", "application/vnd.ms-excel", ""],
  pdf: ["application/pdf"],
  jpg: ["image/jpeg"],
  jpeg: ["image/jpeg"],
  png: ["image/png"],
};

export const ACCEPT_ATTRIBUTE = ".csv,.pdf,.jpg,.jpeg,.png,text/csv,application/pdf,image/jpeg,image/png";

export type FileErrorCode =
  | "type"
  | "empty"
  | "tooBig"
  | "nameTooLong"
  | "duplicate"
  | "slotFull"
  | "documentMustBePdf"
  | "sameKind";

export type FileError = { code: FileErrorCode; name: string };

export type SlotFile = { id: string; file: File; kind: FileKind };

export function extensionOf(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot < 0 ? "" : name.slice(dot + 1).toLowerCase();
}

export function kindOf(file: File): FileKind | null {
  const extension = extensionOf(file.name);
  const kind = Object.hasOwn(EXTENSION_KIND, extension) ? EXTENSION_KIND[extension] : undefined;
  if (!kind) return null;
  // Extension and MIME type must agree; a renamed spreadsheet or script is rejected.
  return MIME_BY_EXTENSION[extension].includes(file.type) ? kind : null;
}

export type SlotRules = {
  slot: SlotId;
  // Every name already in the current mode, compared without case.
  takenNames: ReadonlySet<string>;
  // Files already in this slot.
  count: number;
  // Kind of the file in the other Compare slot, if there is one.
  partnerKind: FileKind | null;
};

// Returns the first reason a file cannot be added, or null. The caller adds files one at a time and updates
// `takenNames` and `count` between calls so a drop of several files is checked as a whole.
export function checkFile(file: File, rules: SlotRules): FileErrorCode | null {
  const kind = kindOf(file);
  if (!kind) return "type";
  if (file.name.length > MAX_FILE_NAME_CHARS) return "nameTooLong";
  if (file.size === 0) return "empty";
  if (file.size > MAX_FILE_BYTES) return "tooBig";
  if (rules.takenNames.has(file.name.toLowerCase())) return "duplicate";
  if (rules.count >= SLOT_MAX[rules.slot]) return "slotFull";
  if (rules.slot === "document" && kind !== "pdf") return "documentMustBePdf";
  if ((rules.slot === "fileA" || rules.slot === "fileB") && rules.partnerKind && rules.partnerKind !== kind) return "sameKind";
  return null;
}

export function formatSize(bytes: number): { value: number; unit: "B" | "KB" | "MB" } {
  if (bytes < 1024) return { value: bytes, unit: "B" };
  if (bytes < 1024 * 1024) return { value: Math.round((bytes / 1024) * 10) / 10, unit: "KB" };
  return { value: Math.round((bytes / (1024 * 1024)) * 100) / 100, unit: "MB" };
}

export const kindLabel: Record<FileKind, string> = { csv: "CSV", pdf: "PDF", image: "IMG" };

export function questionLength(value: string): number {
  return value.trim().length;
}

// UI guard only, not a product limit: stops a huge paste from freezing the page. The 1,000 character rule above is what blocks a run.
export const MAX_QUESTION_INPUT_CHARS = 5000;
