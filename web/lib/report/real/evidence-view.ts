import type { Evidence } from "@/lib/types";
import type { EvidenceView } from "../view";
import { methodId, pageOf, parseRowsLocation, reasonId, toolLabelId } from "./codes";
import { plainText } from "./text";

// The evidence panel of a real report. The server sends closed codes, never sentences, so every title and text here is
// built from a message key. `say` is the translator of the "report" namespace.
export type Say = (key: string, values?: Record<string, string | number>) => string;

const asTable = (value: unknown): EvidenceView["table"] => {
  if (typeof value !== "object" || value === null) return null;
  const { headers, rows } = value as { headers?: unknown; rows?: unknown };
  return Array.isArray(headers) && Array.isArray(rows) ? { headers: headers.map(String), rows: rows.map((row) => (Array.isArray(row) ? row.map(String) : [])) } : null;
};

export function toRealEvidenceView(item: Evidence, say: Say): EvidenceView {
  const base = { ref: item.ref, type: item.type, code: null, quote: null, fileName: item.file_name, location: null, tool: null };
  if (item.type === "critic_note") {
    const reason = reasonId(item.payload.reason);
    return { ...base, title: say(`reason.${reason}.title`), body: say(`reason.${reason}.body`), table: null, metaText: null };
  }
  if (item.type === "passage") return passageView(item, base, say);
  const method = say(`method.${methodId(item.payload.method)}`);
  const rowsUsed = typeof item.payload.rows_used === "number" ? say("evidence.rowsUsed", { n: item.payload.rows_used }) : "";
  const range = parseRowsLocation(item.location);
  const tool = toolLabelId(item.payload.tool);
  const file = plainText(item.file_name, 200);
  const parts = [tool ? say(`evidence.tool.${tool}`) : "", file, range ? say("evidence.rows", { from: range.from, to: range.to }) : ""].filter(Boolean);
  return {
    ...base,
    title: say("evidence.d1Title"),
    body: [method, rowsUsed].filter(Boolean).join(". "),
    table: asTable(item.payload.table),
    metaText: parts.join(" · ") || null,
  };
}

// The reason a claim is not verified: the title of its critic note (U#), or null when it has none.
export function claimReason(refs: string[], evidence: Evidence[], say: Say): string | null {
  for (const ref of refs) {
    const note = evidence.find((item) => item.ref === ref && item.type === "critic_note");
    if (note) return say(`reason.${reasonId(note.payload.reason)}.title`);
  }
  return null;
}

// A passage of the user's PDF (Hound). The quote slot shows the words the report cites, falling back to the passage;
// the source line reads "file.pdf · p. 4 · similarity 0.83" as on the Workspace report board. Nothing here is a model sentence.
function passageView(item: Evidence, base: Omit<EvidenceView, "title" | "body" | "table" | "metaText">, say: Say): EvidenceView {
  const page = typeof item.payload.page === "number" ? item.payload.page : pageOf(item.location);
  const similarity = typeof item.payload.similarity === "number" ? item.payload.similarity : null;
  const quote = [item.payload.quote, item.payload.passage].find((text): text is string => typeof text === "string" && text !== "") ?? null;
  const parts = [plainText(item.file_name, 200), page !== null ? say("evidence.page", { n: page }) : "", similarity !== null ? say("evidence.similarity", { value: Math.round(similarity * 100) / 100 }) : ""].filter(Boolean);
  return { ...base, quote, title: say("evidence.passageTitle"), body: say("evidence.passageBody"), table: null, metaText: parts.join(" · ") || null };
}
