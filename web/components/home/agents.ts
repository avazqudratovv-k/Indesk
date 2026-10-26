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

// Chameleon and Hound are not built yet (ROADMAP): the Home page labels them "Coming later".
export const agentBuilt: Record<AgentId, boolean> = { owl: true, chameleon: false, beaver: true, hound: false, cat: true };

export const agentPlate: Record<AgentId, string> = { owl: "I", chameleon: "II", beaver: "III", hound: "IV", cat: "V" };

// "Try with an example" opens the public example from GET /api/example. Check and Compare have no example yet.
export const exampleHref = "/reports/example";
export const workspaceHref = "/workspace";
