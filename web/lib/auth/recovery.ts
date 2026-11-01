import { limits, validateAuth } from "@/components/auth/validate";

// Pure helpers for the forgot and reset pages. The reset token lives only in the URL fragment: it is read once,
// removed from the address bar at once, and held in memory by the page. It is never logged or stored.
export const TOKEN_MAX_CHARS = 256;

type HashLocation = Pick<Location, "hash" | "pathname" | "search">;
type ReplaceHistory = Pick<History, "replaceState">;

// Returns the token from `#token=...` (or null) and ALWAYS clears the fragment when there was one.
export function takeResetToken(location: HashLocation, history: ReplaceHistory): string | null {
  if (location.hash === "") return null;
  const token = new URLSearchParams(location.hash.slice(1)).get("token");
  history.replaceState(null, "", location.pathname + location.search);
  return token !== null && token.length >= 1 && token.length <= TOKEN_MAX_CHARS ? token : null;
}

// The same fragment rule serves the verify page: `#token=...` is read once and removed from the address bar.
export { takeResetToken as takeFragmentToken };

export type RecoveryErrorKey = "emailRequired" | "emailInvalid" | "emailTooLong" | "passwordRequired" | "passwordTooShort" | "passwordTooLong" | "confirmRequired" | "confirmMismatch";

export function validateForgot(email: string): RecoveryErrorKey | null {
  // Login mode only ever sets the three email keys.
  return (validateAuth("login", { name: "", email, password: "x" }).email as RecoveryErrorKey | undefined) ?? null;
}

export type ResetErrors = { password?: RecoveryErrorKey; confirm?: RecoveryErrorKey };

// Same length rule as sign-up: 10 to 128 characters.
export function validateReset(password: string, confirm: string): ResetErrors {
  const errors: ResetErrors = {};
  if (password.length === 0) errors.password = "passwordRequired";
  else if (password.length < limits.passwordMin) errors.password = "passwordTooShort";
  else if (password.length > limits.passwordMax) errors.password = "passwordTooLong";
  if (confirm.length === 0) errors.confirm = "confirmRequired";
  else if (!errors.password && confirm !== password) errors.confirm = "confirmMismatch";
  return errors;
}

export function mailLang(locale: string): "en" | "ko" {
  return locale === "ko" ? "ko" : "en";
}
