"use client";

import { SessionContext } from "@/hooks/use-session";
import type { Session } from "@/lib/session";

export default function SessionProvider({ session, children }: { session: Session; children: React.ReactNode }) {
  return <SessionContext.Provider value={session}>{children}</SessionContext.Provider>;
}
