import { signedInSession, signedOutSession, type Session } from "@/lib/session";
import type { User } from "@/lib/types";

export type BootstrapDeps = {
  hint: () => boolean;
  refresh: () => Promise<"ok" | "denied" | "failed">;
  me: () => Promise<User>;
};

// Settles an `unknown` session in the browser. Without the hint nothing is sent. With it: one refresh, one /me.
// Only a denied refresh clears the hint; a network failure keeps it so the next load can try again.
export async function resolveUnknownSession(deps: BootstrapDeps): Promise<{ session: Session; clearHint: boolean }> {
  if (!deps.hint()) return { session: signedOutSession, clearHint: false };
  const refreshed = await deps.refresh();
  if (refreshed !== "ok") return { session: signedOutSession, clearHint: refreshed === "denied" };
  try {
    return { session: signedInSession(await deps.me()), clearHint: false };
  } catch {
    return { session: signedOutSession, clearHint: false };
  }
}
