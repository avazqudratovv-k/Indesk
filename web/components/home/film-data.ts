// Non-language literals for the sample animation (board Home.dc.html). Every value here is PLACEHOLDER sample data,
// not a real run: scores, row counts and the code snippet only make the loop look real. Chameleon and Hound are
// not built, so their lanes say "later" (home.film.later) and carry no sample data.
// Words that a person reads live in messages (home.film.*), never here.
export const film = {
  caseNo: "0147",
  agentCount: 3,
  // The stamp on the sample report: matches the report rows below (three marked, one flagged).
  verified: 3,
  total: 4,
  // Ask takes exactly one CSV, so one sample file flies in.
  files: [{ kind: "CSV", color: "var(--c-bea)" }],
  owl: { field: "question_type", value: ["numeric_", "comparison"], confidence: "0.96 → data" },
  data: { codeStart: "df.groupby(", codeArg: "\"st\"", codeEnd: ")", codeLine2: ".riders.pct()", summary: "3 rows · 0.04 s" },
  // Row labels and agent colour for the dots on the report paper (last row is the flagged one). Only Beaver's data rows exist today.
  reportRows: [
    { label: "D1", color: "var(--c-bea)", width: 72 },
    { label: "D2", color: "var(--c-bea)", width: 58 },
    { label: "D3", color: "var(--c-bea)", width: 66 },
  ],
  flaggedRow: { label: "U1", width: 60 },
  // Trace log (desktop only): time stamp and the technical detail after the agent name.
  trace: [
    { time: "00:03", detail: "route → numeric_comparison", later: false },
    { time: "00:04", detail: "", later: true },
    { time: "00:05", detail: "groupby → 3 rows · 0.04 s", later: false },
    { time: "00:06", detail: "", later: true },
    { time: "00:07", detail: "", later: false },
  ],
} as const;

// Thread end points (x in the 640 x 400 board space) from the question box down to each agent card.
export const threadX = [162, 268, 374, 480, 586] as const;
