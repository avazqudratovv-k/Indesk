import type { CustomPlanOffer } from "@/lib/types";

export type CustomQuote = {
  runs: number;
  perRun: number;
  // Runs times the per-run price, before the minimum.
  base: number;
  minimum: number;
  total: number;
  // True when the minimum raised the price.
  isMinimum: boolean;
  // Total divided by runs.
  averagePerRun: number;
};

// Snaps a slider value to the offer's step and keeps it in range. Anything that is not a number falls back to the minimum.
export function clampRuns(value: number, runs: CustomPlanOffer["runs"]): number {
  if (!Number.isFinite(value)) return runs.min;
  const snapped = Math.round(value / runs.step) * runs.step;
  return Math.min(runs.max, Math.max(runs.min, snapped));
}

// Custom plan price in won: runs x the per-run price, never below the minimum.
// Pure and display-only. The real price is decided on the server (DATA.md: POST /api/plans/custom/quote).
export function quoteCustomPlan(runsValue: number, offer: CustomPlanOffer): CustomQuote {
  const runs = clampRuns(runsValue, offer.runs);
  const base = Math.round(runs * offer.per_run);
  const total = Math.max(offer.minimum, base);
  return {
    runs,
    perRun: offer.per_run,
    base,
    minimum: offer.minimum,
    total,
    isMinimum: base < offer.minimum,
    averagePerRun: total / runs,
  };
}
