// Non-language literals for the demo film (board Home.dc.html). Every value here is PLACEHOLDER sample data,
// not a real run: file names, scores, row counts and the code snippet only make the loop look real.
// Words that a person reads live in messages (home.film.*), never here.
export const film = {
  caseNo: "0147",
  agentCount: 5,
  // CSV / PDF / JPG sample files that fly in first; colour is the agent that reads them.
  files: [
    { kind: "CSV", color: "var(--c-bea)" },
    { kind: "PDF", color: "var(--c-hou)" },
    { kind: "JPG", color: "var(--c-cham)" },
  ],
  owl: { field: "question_type", value: ["numeric_", "comparison"], confidence: "0.96 → data + docs" },
  vision: { quotes: [["“2019”", "4,812"], ["“2024”", "7,265"]], confidence: "conf 0.93" },
  data: { codeStart: "df.groupby(", codeArg: "\"st\"", codeEnd: ")", codeLine2: ".riders.pct()", summary: "3 rows · 0.04 s" },
  retrieval: { source: "report.pdf · p.4", score: "score 0.91" },
  // Row labels and agent colour for the dots on the report paper (last row is the flagged one).
  reportRows: [
    { label: "D1", color: "var(--c-bea)", width: 72 },
    { label: "R1", color: "var(--c-hou)", width: 58 },
    { label: "V1", color: "var(--c-cham)", width: 66 },
  ],
  flaggedRow: { label: "U1", width: 60 },
  // Trace log (desktop only): time stamp and the technical detail after the agent name.
  trace: [
    { time: "00:03", detail: "route → numeric_comparison" },
    { time: "00:04", detail: "OCR chart.jpg · conf 0.93" },
    { time: "00:05", detail: "groupby → 3 rows · 0.04 s" },
    { time: "00:06", detail: "report.pdf p.4 · 0.91" },
    { time: "00:07", detail: "" },
  ],
} as const;

// Thread end points (x in the 640 x 400 board space) from the question box down to each agent card.
export const threadX = [162, 268, 374, 480, 586] as const;
