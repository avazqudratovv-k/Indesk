import { cookies } from "next/headers";
import { signedInSession, unknownSession, type Session } from "@/lib/session";
import type { User } from "@/lib/types";

const accessCookie = "indesk_access";

export function apiInternalUrl(): string {
  return process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";
}

// Asks the API who is signed in, forwarding only the access cookie. Server components cannot set cookies,
// so this never refreshes: any failure is `unknown` and the browser settles it (refresh, then /api/me).
export async function getServerSession(): Promise<Session> {
  const access = (await cookies()).get(accessCookie)?.value;
  if (!access) return unknownSession;
  try {
    const response = await fetch(`${apiInternalUrl()}/api/me`, {
      headers: { cookie: `${accessCookie}=${access}` },
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    if (!response.ok) return unknownSession;
    return signedInSession((await response.json()) as User);
  } catch {
    return unknownSession;
  }
}
