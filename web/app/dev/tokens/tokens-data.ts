// Token names from styles/tokens.css, grouped as in docs/design/DESIGN.md.
export const colorGroups: { title: string; tokens: string[] }[] = [
  { title: "Surfaces", tokens: ["paper", "paper2", "card", "rule", "rule2"] },
  { title: "Text", tokens: ["ink", "ink2", "mute"] },
  { title: "Accent", tokens: ["accent", "accentInk", "accentSoft", "accentText"] },
  { title: "Status", tokens: ["green", "greenBg", "bad", "badBg", "badLine", "warn", "warnBg", "warm"] },
  { title: "Highlight and misc", tokens: ["hl", "hlInk", "medal", "track", "disabled", "grid", "dot", "glow"] },
  { title: "Code and quotes", tokens: ["code", "codeInk", "quoteBg", "quoteInk"] },
  { title: "Agents", tokens: ["c-owl", "c-cham", "c-bea", "c-hou", "c-cat"] },
];

export const reportPaperTokens = ["report-paper", "report-ink", "report-ok", "report-bad", "report-mute"];
