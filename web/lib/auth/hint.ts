// A boolean "this browser signed in" hint. It is NOT a token and grants nothing: it only decides whether a
// signed-out-looking page load is worth one refresh call. Set on login, cleared on logout or a denied refresh.
const key = "indesk_signed_in_hint";

export function readHint(): boolean {
  try {
    return window.localStorage.getItem(key) === "1";
  } catch {
    return true; // storage blocked: keep working by trying the refresh
  }
}

export function setHint(): void {
  try {
    window.localStorage.setItem(key, "1");
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
