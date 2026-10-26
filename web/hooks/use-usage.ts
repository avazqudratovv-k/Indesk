"use client";

import { useEffect, useState } from "react";
import { loadUsage, type Usage } from "@/lib/usage/api";

// The signed-in person's usage from GET /api/usage. Asked when the user changes and whenever `refreshKey` changes (a run
// started or ended); never on a timer. While it loads, or when it fails, the value is null and no count is shown.
export function useUsage(userId: string | null, refreshKey: string): Usage | null {
  // The answer belongs to one (user, key) pair; any other pair reads as "unknown", so nothing is reset in the effect.
  const key = `${userId}:${refreshKey}`;
  const [answer, setAnswer] = useState<{ key: string; usage: Usage | null } | null>(null);

  useEffect(() => {
    if (!userId) return;
    const controller = new AbortController();
    void loadUsage(controller.signal).then((usage) => {
      if (!controller.signal.aborted) setAnswer({ key, usage });
    });
    return () => controller.abort();
  }, [userId, key]);

  return userId && answer?.key === key ? answer.usage : null;
}
