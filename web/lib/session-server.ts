import { cookies } from "next/headers";
import { getMockUser, MOCK_USER_ID } from "@/mocks";
import { devSessionCookie, devSwitchEnabled, signedOutSession, type Session } from "./session";

// Server components read the same cookie the client switch writes. In production it is ignored: signed out.
export async function getSession(): Promise<Session> {
  if (!devSwitchEnabled) return signedOutSession;
  const value = (await cookies()).get(devSessionCookie)?.value;
  const user = value === "in" ? getMockUser(MOCK_USER_ID) : undefined;
  return user ? { signedIn: true, user } : signedOutSession;
}
