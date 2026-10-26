// Where to go after logging in. Only a same-origin relative path is accepted; anything else is dropped.
const maxLength = 512;

export function safeNext(value: string | string[] | null | undefined): string | undefined {
  if (typeof value !== "string" || value.length === 0 || value.length > maxLength) return undefined;
  if (!value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) return undefined;
  if (/[\u0000-\u001f\u007f\\]/.test(value)) return undefined;
  let decoded: string;
  try {
    decoded = decodeURIComponent(value);
  } catch {
    return undefined;
  }
  // A percent-encoded slash or backslash must not turn into "//" or "/\" after decoding.
  if (decoded.startsWith("//") || decoded.startsWith("/\\") || /[\u0000-\u001f\u007f\\]/.test(decoded)) return undefined;
  // Never loop back to the auth pages.
  if (/^\/(login|signup)(\/|\?|#|$)/.test(value)) return undefined;
  return value;
}

export function loginHref(next: string | undefined): string {
  const safe = safeNext(next);
  return safe ? `/login?next=${encodeURIComponent(safe)}` : "/login";
}
