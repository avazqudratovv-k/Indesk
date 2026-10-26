"use client";

import { useSession } from "@/hooks/use-session";

// Sign-up prompts are for people who are not signed in. Unknown counts as not signed in on public pages.
export default function HideWhenSignedIn({ children }: { children: React.ReactNode }) {
  return useSession().signedIn ? null : children;
}
