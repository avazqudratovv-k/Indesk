// The letter in the avatar: the first character of the display name. NFC first, so a Hangul syllable typed as separate
// jamo is still one letter; "?" for a name that is empty after trimming.
export function displayInitial(name: string): string {
  const first = Array.from(name.trim().normalize("NFC"))[0];
  return first ? first.toLocaleUpperCase() : "?";
}

const knownPlans = ["free", "pro", "payg", "custom"] as const;
export type PlanKey = (typeof knownPlans)[number] | "other";

// Which `my.plan.*` text names a plan; a plan the web does not know reads as "other", never as the raw server string.
export function planKey(plan: string): PlanKey {
  return (knownPlans as readonly string[]).includes(plan) ? (plan as PlanKey) : "other";
}
