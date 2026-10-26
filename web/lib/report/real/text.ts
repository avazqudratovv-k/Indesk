// Server text (claims, labels, table cells) comes from model output and CSV cells. It is shown as plain text only: React
// escapes it, nothing here turns it into HTML, markdown or links. This helper is a second guard: it drops control and
// direction-override characters and cuts a very long string, so one bad cell cannot break the layout or reorder text.
// Dropped: C0 and C1 controls, zero-width and direction marks (U+200B to U+200F), line and paragraph separators and the
// embedding, override and isolate controls (U+2028 to U+202E, U+2060 to U+2064, U+2066 to U+206F), and the BOM (U+FEFF).
const RANGES: readonly (readonly [number, number])[] = [
  [0x0000, 0x001f],
  [0x007f, 0x009f],
  [0x200b, 0x200f],
  [0x2028, 0x202e],
  [0x2060, 0x2064],
  [0x2066, 0x206f],
  [0xfeff, 0xfeff],
];

const hex = (code: number): string => "\\u" + code.toString(16).padStart(4, "0");
const invisible = new RegExp(`[${RANGES.map(([from, to]) => `${hex(from)}-${hex(to)}`).join("")}]`, "g");

export function plainText(value: unknown, max = 400): string {
  if (typeof value !== "string") return "";
  const clean = value.replace(/[\r\n\t]+/g, " ").replace(invisible, "").trim();
  return clean.length > max ? `${clean.slice(0, max - 1).trimEnd()}…` : clean;
}
