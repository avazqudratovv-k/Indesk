import { apiClient } from "@/lib/api/client";

// GET /api/usage. `free` is null unless the person is on the Free plan; it is also null whenever the numbers cannot be
// trusted (request failed, or the body is not the expected shape). The screen then shows no number at all: never a
// stale or a default count (the count is decided on the server, DECISIONS #246).
export type Usage = { plan: string; free: { total: number; left: number } | null };

type Request = <T>(path: string, init?: { signal?: AbortSignal }) => Promise<T>;
const defaultRequest: Request = <T,>(path: string, init?: { signal?: AbortSignal }) => apiClient().request<T>(path, init);

const whole = (value: unknown): value is number => typeof value === "number" && Number.isInteger(value) && value >= 0 && value <= 1_000_000;

export function parseUsage(raw: unknown): Usage | null {
  if (typeof raw !== "object" || raw === null) return null;
  const body = raw as Record<string, unknown>;
  if (typeof body.plan !== "string") return null;
  if (body.plan !== "free") return { plan: body.plan, free: null };
  if (!whole(body.free_runs_total) || !whole(body.free_runs_left) || body.free_runs_left > body.free_runs_total) return null;
  return { plan: "free", free: { total: body.free_runs_total, left: body.free_runs_left } };
}

// Never throws: null means "unknown".
export async function loadUsage(signal?: AbortSignal, request: Request = defaultRequest): Promise<Usage | null> {
  try {
    return parseUsage(await request<unknown>("/api/usage", { signal }));
  } catch {
    return null;
  }
}

// Which text the Free plan's pill shows. Only a usage answer with counts gives a number; anything else (not asked yet,
// failed, not the Free plan's shape) gives the plan name alone.
export type FreePill = { key: "usage.free"; values: { left: number; total: number } } | { key: "usage.freeNoCount" };

export function freePill(usage: Usage | null): FreePill {
  return usage?.free ? { key: "usage.free", values: { left: usage.free.left, total: usage.free.total } } : { key: "usage.freeNoCount" };
}
