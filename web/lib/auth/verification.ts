import type { Session } from "@/lib/session";

// The banner is for a signed-in user whose address is not proven yet. Signed out, still loading and verified show nothing.
export function showVerifyBanner(session: Session): boolean {
  return session.status === "signedIn" && !session.user.email_verified;
}

export type VerifyPhase = "confirming" | "verified" | "invalid";

// What the /verify-email page shows once the token and the answer are known: no token or a bad token is "invalid".
export function verifyPhase(hasToken: boolean, answer: "pending" | "ok" | "invalid"): VerifyPhase {
  if (!hasToken || answer === "invalid") return "invalid";
  return answer === "ok" ? "verified" : "confirming";
}
