"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { SessionContext, type SessionApi } from "@/hooks/use-session";
import { apiClient, setAuthLostHandler } from "@/lib/api/client";
import { fetchMe, logout } from "@/lib/auth/api";
import { resolveUnknownSession } from "@/lib/auth/bootstrap";
import { clearHint, readHint, setHint } from "@/lib/auth/hint";
import { clearRunId } from "@/lib/run/live/storage";
import { signedInSession, signedOutSession, type Session } from "@/lib/session";
import type { User } from "@/lib/types";

const channelName = "indesk-session";

// Holds who is signed in. The server gives the first answer; `unknown` is settled here in the browser.
export default function SessionProvider({ session: initial, children }: { session: Session; children: React.ReactNode }) {
  const [session, setSession] = useState<Session>(initial);
  // Created inside the effect below (React may run effects twice in development, and a closed channel throws).
  const channel = useRef<BroadcastChannel | null>(null);

  function tell(message: "signedIn" | "signedOut") {
    try {
      channel.current?.postMessage(message);
    } catch {
      // Other tabs only miss a hint; they find out on their next request.
    }
  }

  const signedOut = useCallback(() => {
    clearHint();
    setSession(signedOutSession);
  }, []);

  // A call that could not be saved by a refresh means the session is gone.
  useEffect(() => {
    setAuthLostHandler(signedOut);
    return () => setAuthLostHandler(() => {});
  }, [signedOut]);

  useEffect(() => {
    if (initial.status === "signedIn") setHint();
    if (initial.status !== "unknown") return;
    let live = true;
    resolveUnknownSession({
      hint: readHint,
      // The page's own load time: a refresh that finished after it started has already replaced the cookies.
      refresh: () => apiClient().refresh(performance.timeOrigin),
      me: fetchMe,
    }).then((result) => {
      if (!live) return;
      if (result.clearHint) clearHint();
      if (result.session.status === "signedIn") setHint();
      setSession(result.session);
    });
    return () => {
      live = false;
    };
  }, [initial.status]);

  // Another tab logged in or out.
  useEffect(() => {
    if (typeof BroadcastChannel === "undefined") return;
    const own = new BroadcastChannel(channelName);
    channel.current = own;
    own.onmessage = (event: MessageEvent) => {
      if (event.data === "signedOut") setSession(signedOutSession);
      else if (event.data === "signedIn") fetchMe().then((user) => setSession(signedInSession(user)), () => {});
    };
    return () => {
      own.close();
      channel.current = null;
    };
  }, []);

  const startSession = useCallback((user: User) => {
    setHint();
    setSession(signedInSession(user));
    tell("signedIn");
  }, []);

  const userId = session.user?.id ?? null;
  const endSession = useCallback(async () => {
    await logout();
    // The remembered run id belongs to this account only; it goes with the session.
    if (userId) clearRunId(userId);
    signedOut();
    tell("signedOut");
  }, [signedOut, userId]);

  const value = useMemo<SessionApi>(() => ({ session, startSession, endSession }), [session, startSession, endSession]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}
