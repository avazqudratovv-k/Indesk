"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useSessionActions } from "@/hooks/use-session";
import { isAuthPath, postNotice } from "@/lib/auth/notice";
import { runLogout } from "@/lib/auth/logout-flow";

export type LogoutState = "idle" | "busy" | "failed";

// Log out with the session's own endSession and the Home redirect. A failure shows for 4 s, then the button is back.
export function useLogout(): { state: LogoutState; logout: () => Promise<void> } {
  const { endSession } = useSessionActions();
  const router = useRouter();
  const [state, setState] = useState<LogoutState>("idle");
  const failTimer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(failTimer.current), []);

  const logout = useCallback(async () => {
    if (state === "busy") return;
    setState("busy");
    // The notice is written only once the server has confirmed the logout (endSession rejects otherwise).
    const result = await runLogout(
      async () => {
        await endSession();
        if (!isAuthPath(window.location.pathname)) postNotice({ kind: "loggedOut" });
      },
      () => router.push("/"),
    );
    if (result === "done") {
      setState("idle");
      return;
    }
    setState("failed");
    window.clearTimeout(failTimer.current);
    failTimer.current = window.setTimeout(() => setState("idle"), 4000);
  }, [state, endSession, router]);

  return { state, logout };
}
