import { SESSION_MAX_SECONDS } from "@/lib/limits";

// One-shot notices after a sign-in change ("Welcome back", "You are logged out", "Your session ended"). A notice sits in
// sessionStorage under ONE key until the NoticeHost reads and deletes it, so a reload never shows it twice. Nothing here
// is a secret: it holds a kind, a display name or a flag, never a token.
export type Notice = { kind: "welcome"; name: string } | { kind: "loggedOut" } | { kind: "sessionEnded"; sixHours: boolean } | { kind: "passwordChanged" };

export type NoticeStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export const NOTICE_KEY = "indesk_notice";
export const NOTICE_EVENT = "indesk:notice";

const maxNameChars = 100;

export function writeNotice(storage: NoticeStorage, notice: Notice): void {
  try {
    storage.setItem(NOTICE_KEY, JSON.stringify(notice));
  } catch {
    // Storage blocked or full: the notice is a courtesy, so it is simply not shown.
  }
}

// Reads the pending notice and always removes it. Anything unknown or malformed reads as nothing.
export function consumeNotice(storage: NoticeStorage): Notice | null {
  let raw: string | null;
  try {
    raw = storage.getItem(NOTICE_KEY);
    if (raw !== null) storage.removeItem(NOTICE_KEY);
  } catch {
    return null;
  }
  if (raw === null) return null;
  try {
    return parseNotice(JSON.parse(raw));
  } catch {
    return null;
  }
}

function parseNotice(value: unknown): Notice | null {
  if (typeof value !== "object" || value === null) return null;
  const data = value as Record<string, unknown>;
  if (data.kind === "welcome") return { kind: "welcome", name: typeof data.name === "string" ? data.name.slice(0, maxNameChars) : "" };
  if (data.kind === "loggedOut") return { kind: "loggedOut" };
  if (data.kind === "passwordChanged") return { kind: "passwordChanged" };
  if (data.kind === "sessionEnded") return { kind: "sessionEnded", sixHours: data.sixHours === true };
  return null;
}

// A successful login or signup drops a pending "session ended" notice (any other kind is left alone).
export function clearSessionEnded(storage: NoticeStorage): void {
  try {
    const raw = storage.getItem(NOTICE_KEY);
    if (raw !== null && parseNotice(JSON.parse(raw))?.kind === "sessionEnded") storage.removeItem(NOTICE_KEY);
  } catch {
    // Storage blocked or not JSON: nothing pending that matters.
  }
}

// Browser side: write the notice, then tell a mounted NoticeHost (the Shell lives across client-side navigations).
export function postNotice(notice: Notice): void {
  if (typeof window === "undefined") return;
  try {
    writeNotice(window.sessionStorage, notice);
    window.dispatchEvent(new Event(NOTICE_EVENT));
  } catch {
    // sessionStorage can throw when blocked.
  }
}

export function dropPendingSessionEnded(): void {
  if (typeof window === "undefined") return;
  try {
    clearSessionEnded(window.sessionStorage);
  } catch {
    // Blocked storage: nothing to drop.
  }
}

export function isAuthPath(pathname: string | null): boolean {
  if (!pathname) return false;
  return ["/login", "/signup", "/forgot-password", "/reset-password", "/verify-email"].some((path) => pathname === path || pathname.startsWith(`${path}/`));
}

export type BeforeSignOut = "signedIn" | "unknownWithHint" | "unknown" | "signedOut";

// The no-loop rule: a "session ended" notice is written only when someone was signed in (or a cold load had a hint)
// and the page is not /login or /signup. Once signed out, `before` is "signedOut", so a repeated auth-lost writes nothing,
// and showing a notice never changes the session or the route.
export function shouldWriteSessionEnded(before: BeforeSignOut, pathname: string | null): boolean {
  if (isAuthPath(pathname)) return false;
  return before === "signedIn" || before === "unknownWithHint";
}

// "6 hours" only when the stored login is at least as old as the server's session limit. A missing or future login time
// (clock change, legacy hint) reads as unknown, so the generic line is used.
export function sessionEndedAfterLimit(loginAt: number | null, now: number): boolean {
  if (loginAt === null || loginAt > now) return false;
  return (now - loginAt) / 1000 >= SESSION_MAX_SECONDS;
}

export function sessionEndedNotice(loginAt: number | null, now: number): Notice {
  return { kind: "sessionEnded", sixHours: sessionEndedAfterLimit(loginAt, now) };
}

export type NoticeMessage = { key: "welcome" | "welcomeNoName" | "loggedOut" | "passwordChanged" | "sessionEndedHours" | "sessionEnded"; values?: { name?: string; hours?: number } };

export function noticeMessage(notice: Notice): NoticeMessage {
  if (notice.kind === "welcome") {
    const name = notice.name.trim();
    return name ? { key: "welcome", values: { name } } : { key: "welcomeNoName" };
  }
  if (notice.kind === "loggedOut") return { key: "loggedOut" };
  if (notice.kind === "passwordChanged") return { key: "passwordChanged" };
  return notice.sixHours ? { key: "sessionEndedHours", values: { hours: SESSION_MAX_SECONDS / 3600 } } : { key: "sessionEnded" };
}
