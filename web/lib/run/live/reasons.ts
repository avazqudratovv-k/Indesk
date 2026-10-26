import type { Outcome } from "./types";

// Every reason code the API can end a run with (api/app/core/enums.py RunReason). The browser holds the text.
export const REASONS = [
  "daily_cap_user", "daily_cap_global", "model_busy", "model_timeout", "model_unavailable", "bad_model_output",
  "analysis_failed", "sandbox_unavailable", "input_unusable", "step_cap", "run_timeout", "worker_lost",
  "budget_exceeded", "internal_error",
] as const;
export type Reason = (typeof REASONS)[number];

export function isKnownReason(value: string): value is Reason {
  return (REASONS as readonly string[]).includes(value);
}

// api/app/runs/mapping.py: P10 treats these three as "busy today".
export const BUSY_TODAY: readonly Reason[] = ["daily_cap_user", "daily_cap_global", "model_busy"];

export type CardTone = "ok" | "warn" | "accent" | "bad" | "neutral";

// What a finished run shows. `reason` is the id of workspace.reasons.* ("unknown" for a code we do not have).
export type EndCard =
  | { kind: "report"; outcome: "answered" | "partial" }
  | { kind: "problem"; label: "busyToday" | "notAccepted" | "failed" | "notAnswerable" | "needsBetterInput"; tone: CardTone; reason: Reason | "unknown" | "notAnswerable" | "needsBetterInput"; freeRunNote: boolean };

export function endCard(outcome: Outcome, reason: string | null): EndCard {
  if (outcome === "answered" || outcome === "partial") return { kind: "report", outcome };
  if (outcome === "not_answerable") return { kind: "problem", label: "notAnswerable", tone: "accent", reason: "notAnswerable", freeRunNote: false };
  if (outcome === "needs_better_input") return { kind: "problem", label: "needsBetterInput", tone: "warn", reason: "needsBetterInput", freeRunNote: false };
  const known = reason !== null && isKnownReason(reason) ? reason : "unknown";
  const rejected = outcome === "rejected";
  if (known !== "unknown" && BUSY_TODAY.includes(known)) return { kind: "problem", label: "busyToday", tone: "accent", reason: known, freeRunNote: rejected };
  // Only a rejected run says it did not use up a run; for `failed` the screen says nothing about counting (D5).
  return { kind: "problem", label: rejected ? "notAccepted" : "failed", tone: rejected ? "bad" : "neutral", reason: known, freeRunNote: rejected };
}
