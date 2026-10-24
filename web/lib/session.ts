import type { User } from "@/lib/types";

// Mock session for the UI-first phase (ROADMAP 1.7). Replaced by real auth in 4.1.
export type Session = { signedIn: true; user: User } | { signedIn: false; user: null };

export const devSessionCookie = "dev_session";
export type DevSessionValue = "in" | "out";

export const signedOutSession: Session = { signedIn: false, user: null };

export function isDevSessionValue(value: string | undefined): value is DevSessionValue {
  return value === "in" || value === "out";
}

// The dev switch exists only outside production builds.
export const devSwitchEnabled = process.env.NODE_ENV !== "production";
