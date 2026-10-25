export const agentIds = ["owl", "chameleon", "beaver", "hound", "cat"] as const;
export type AgentId = (typeof agentIds)[number];

// Agent color tokens from tokens.css.
export const agentColor: Record<AgentId, string> = {
  owl: "var(--c-owl)",
  chameleon: "var(--c-cham)",
  beaver: "var(--c-bea)",
  hound: "var(--c-hou)",
  cat: "var(--c-cat)",
};

export const agentPlate: Record<AgentId, string> = { owl: "I", chameleon: "II", beaver: "III", hound: "IV", cat: "V" };

// "Try with an example" opens the mock reports until the cached example exists (ROADMAP 4.7):
// rep_01 Ask, rep_02 Check, rep_03 Compare.
export const exampleHref = "/reports/rep_01";
export const exampleReportHref = { ask: "/reports/rep_01", check: "/reports/rep_02", compare: "/reports/rep_03" } as const;
export const workspaceHref = "/workspace";
