// "This browser signed in" hint. It is NOT a token and grants nothing: it only decides whether a signed-out-looking page
// load is worth one refresh call, and it holds the login time (ms) so the "session ended after 6 hours" notice is only
// shown when it is true. Set on login, cleared on logout or a denied refresh. An old value "1" has no time.
const key = "indesk_signed_in_hint";
const firstPlausibleTime = 1_000_000_000_000; // 2001; anything smaller is the old "1", not a time

export function readHint(): boolean {
  try {
    return window.localStorage.getItem(key) !== null;
  } catch {
    return true; // storage blocked: keep working by trying the refresh
  }
}

export function parseLoginAt(raw: string | null): number | null {
  if (raw === null) return null;
  const value = Number(raw);
  return Number.isFinite(value) && value >= firstPlausibleTime ? value : null;
}

export function readLoginAt(): number | null {
  try {
    return parseLoginAt(window.localStorage.getItem(key));
  } catch {
    return null;
  }
}

// With `loginAt` (a real login) the time is written. Without it (a page load that is already signed in) an existing
// value is kept, because a refresh does not extend the session.
export function setHint(loginAt?: number): void {
  try {
    if (loginAt !== undefined) window.localStorage.setItem(key, String(loginAt));
    else if (window.localStorage.getItem(key) === null) window.localStorage.setItem(key, "1");
  } catch {
    // Storage blocked: nothing to remember.
  }
}

export function clearHint(): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    // Storage blocked: nothing to clear.
  }
}
