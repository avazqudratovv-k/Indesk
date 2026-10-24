"use client";

import { createContext, useContext } from "react";
import { signedOutSession, type Session } from "@/lib/session";

export const SessionContext = createContext<Session>(signedOutSession);

// Reads the mock session the root layout resolved from the dev_session cookie.
export function useSession(): Session {
  return useContext(SessionContext);
}
