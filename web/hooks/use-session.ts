"use client";

import { createContext, useContext } from "react";
import { signedOutSession, type Session } from "@/lib/session";
import type { User } from "@/lib/types";

export type SessionApi = {
  session: Session;
  // Called after a successful login or signup response; the cookies are already set by the server.
  startSession: (user: User) => void;
  // Replaces the signed-in user with fresher data (for example after the email is verified). No notice, no login time change.
  updateUser: (user: User) => void;
  // Asks the server to end the session. Rejects (session unchanged) if the server could not be reached.
  endSession: () => Promise<void>;
};

export const SessionContext = createContext<SessionApi>({
  session: signedOutSession,
  startSession: () => {},
  updateUser: () => {},
  endSession: async () => {},
});

export function useSession(): Session {
  return useContext(SessionContext).session;
}

export function useSessionActions(): Omit<SessionApi, "session"> {
  const { startSession, updateUser, endSession } = useContext(SessionContext);
  return { startSession, updateUser, endSession };
}
