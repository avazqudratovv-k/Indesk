// The letter in the avatar: the first character of the display name, else of the email, else "?". NFC first, so a Hangul
// syllable typed as separate jamo is still one letter.
export function displayInitial(name: string, email = ""): string {
  for (const text of [name, email]) {
    const first = Array.from(text.trim().normalize("NFC"))[0];
    if (first) return first.toLocaleUpperCase();
  }
  return "?";
}

const knownPlans = ["free", "pro", "payg", "custom"] as const;
export type PlanKey = (typeof knownPlans)[number] | "other";

// Which `my.plan.*` text names a plan; a plan the web does not know reads as "other", never as the raw server string.
export function planKey(plan: string): PlanKey {
  return (knownPlans as readonly string[]).includes(plan) ? (plan as PlanKey) : "other";
}
