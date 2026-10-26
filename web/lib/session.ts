import type { User } from "@/lib/types";

// `unknown`: the server could not tell (for example the access cookie expired); the client resolves it.
// `signedIn` stays a plain boolean so screens that only need "is someone signed in" keep working.
export type Session =
  | { status: "unknown"; signedIn: false; user: null }
  | { status: "signedOut"; signedIn: false; user: null }
  | { status: "signedIn"; signedIn: true; user: User };

export const unknownSession: Session = { status: "unknown", signedIn: false, user: null };
export const signedOutSession: Session = { status: "signedOut", signedIn: false, user: null };

export function signedInSession(user: User): Session {
  return { status: "signedIn", signedIn: true, user };
}
