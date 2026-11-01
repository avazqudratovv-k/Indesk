import { afterEach, describe, expect, it, vi } from "vitest";
import en from "@/messages/en.json";
import ko from "@/messages/ko.json";
import users from "@/mocks/users.json";
import { apiErrorKey, errorFromResponse, knownCodes } from "@/lib/api/errors";
import { signedInSession, signedOutSession, unknownSession } from "@/lib/session";
import type { User } from "@/lib/types";
import { confirmEmail, resendVerification, signup } from "./api";
import { isAuthPath } from "./notice";
import { mailLang, takeFragmentToken } from "./recovery";
import { showVerifyBanner, verifyPhase } from "./verification";

const user = (over: Partial<User> = {}): User => ({
  id: "u1",
  email: "kim@example.com",
  display_name: "Kim",
  handle: "kim",
  discoverable: false,
  plan: "free",
  lang: "en",
  theme: "light",
  default_view: "simple",
  notify: false,
  email_verified: false,
  created_at: "2026-10-01T00:00:00Z",
  deleted_at: null,
  ...over,
});

afterEach(() => vi.unstubAllGlobals());

describe("the fragment", () => {
  it("is cleared from the address bar as soon as the token is read", () => {
    const replaceState = vi.fn();
    const token = takeFragmentToken({ hash: "#token=VERIFY_abc-1", pathname: "/verify-email", search: "" }, { replaceState });
    expect(token).toBe("VERIFY_abc-1");
    expect(replaceState).toHaveBeenCalledTimes(1);
    expect(replaceState).toHaveBeenCalledWith(null, "", "/verify-email");
    expect(JSON.stringify(replaceState.mock.calls)).not.toContain("VERIFY_abc-1");
  });

  it("is cleared even when it holds no token, and a missing fragment gives none", () => {
    const replaceState = vi.fn();
    expect(takeFragmentToken({ hash: "#x=1", pathname: "/verify-email", search: "" }, { replaceState })).toBeNull();
    expect(replaceState).toHaveBeenCalledTimes(1);
    const untouched = vi.fn();
    expect(takeFragmentToken({ hash: "", pathname: "/verify-email", search: "" }, { replaceState: untouched })).toBeNull();
    expect(untouched).not.toHaveBeenCalled();
  });
});

describe("the three states of the verify page", () => {
  it("confirming while the answer is pending", () => {
    expect(verifyPhase(true, "pending")).toBe("confirming");
  });
  it("verified on a 204", () => {
    expect(verifyPhase(true, "ok")).toBe("verified");
  });
  it("invalid on a bad token and on a missing token", () => {
    expect(verifyPhase(true, "invalid")).toBe("invalid");
    expect(verifyPhase(false, "pending")).toBe("invalid");
    expect(verifyPhase(false, "ok")).toBe("invalid");
  });
  it("treats the page as an auth page (no 'session ended' notice there)", () => {
    expect(isAuthPath("/verify-email")).toBe(true);
  });
});

describe("the banner", () => {
  it("shows only for a signed-in user whose email is not verified", () => {
    expect(showVerifyBanner(signedInSession(user({ email_verified: false })))).toBe(true);
    expect(showVerifyBanner(signedInSession(user({ email_verified: true })))).toBe(false);
    expect(showVerifyBanner(signedOutSession)).toBe(false);
    expect(showVerifyBanner(unknownSession)).toBe(false);
  });

  it("goes away once the session user is replaced by a verified one", () => {
    expect(showVerifyBanner(signedInSession(user({ email_verified: true })))).toBe(false);
  });

  it("never shows for the mock users (they are all verified)", () => {
    expect(users.records.length).toBeGreaterThan(0);
    for (const record of users.records) expect(record.email_verified, record.id).toBe(true);
  });
});

describe("the error mapping", () => {
  const body = (code: string) => JSON.stringify({ error: { code } });

  it("reads both new codes", async () => {
    const invalid = await errorFromResponse(new Response(body("VERIFY_TOKEN_INVALID"), { status: 400 }));
    expect(invalid.code).toBe("VERIFY_TOKEN_INVALID");
    expect(apiErrorKey(invalid)).toBe("VERIFY_TOKEN_INVALID");
    const gate = await errorFromResponse(new Response(body("EMAIL_NOT_VERIFIED"), { status: 403 }));
    expect(gate.code).toBe("EMAIL_NOT_VERIFIED");
    expect(gate.status).toBe(403);
    expect(knownCodes).toContain("VERIFY_TOKEN_INVALID");
    expect(knownCodes).toContain("EMAIL_NOT_VERIFIED");
  });

  it("reads a 429 on resend with its Retry-After, and a 503 as not ready", async () => {
    const limited = await errorFromResponse(new Response(body("RATE_LIMITED"), { status: 429, headers: { "Retry-After": "1800" } }));
    expect(apiErrorKey(limited)).toBe("RATE_LIMITED_WAIT");
    expect((await errorFromResponse(new Response(body("NOT_READY"), { status: 503 }))).code).toBe("NOT_READY");
  });
});

describe("the requests", () => {
  function stubFetch(status: number, responseBody: string | null = null) {
    const fetch = vi.fn(async () => new Response(responseBody, { status }));
    vi.stubGlobal("fetch", fetch);
    return fetch;
  }
  const sent = (fetch: ReturnType<typeof stubFetch>) => {
    const call = fetch.mock.calls[0] as unknown as [string, RequestInit];
    return { url: call[0], init: call[1] };
  };

  it("sign-up sends the site language", async () => {
    const fetch = stubFetch(201, JSON.stringify(user()));
    await signup({ email: "kim@example.com", password: "a long password", displayName: "Kim", lang: mailLang("ko") });
    const { url, init } = sent(fetch);
    expect(url).toBe("/api/auth/signup");
    expect(JSON.parse(String(init.body))).toEqual({ email: "kim@example.com", password: "a long password", display_name: "Kim", lang: "ko" });
    expect(mailLang("en")).toBe("en");
    expect(mailLang("ja")).toBe("en");
  });

  it("confirm sends the token in the body, never in the address, and accepts the empty 204", async () => {
    const fetch = stubFetch(204);
    await expect(confirmEmail("SECRET")).resolves.toBeUndefined();
    const { url, init } = sent(fetch);
    expect(url).toBe("/api/auth/verify/confirm");
    expect(url).not.toContain("SECRET");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({ token: "SECRET" });
  });

  it("resend posts with no body", async () => {
    const fetch = stubFetch(204);
    await expect(resendVerification()).resolves.toBeUndefined();
    const { url, init } = sent(fetch);
    expect(url).toBe("/api/auth/verify/resend");
    expect(init.method).toBe("POST");
    expect(init.body).toBeUndefined();
  });

  it("a bad confirm token is an ApiError with the code only", async () => {
    stubFetch(400, JSON.stringify({ error: { code: "VERIFY_TOKEN_INVALID" } }));
    await expect(confirmEmail("x")).rejects.toMatchObject({ code: "VERIFY_TOKEN_INVALID", status: 400 });
  });
});

function flatten(value: unknown, prefix = ""): string[] {
  if (typeof value === "string") return [prefix];
  if (value && typeof value === "object") return Object.entries(value).flatMap(([k, v]) => flatten(v, prefix ? `${prefix}.${k}` : k));
  return [];
}

describe("the strings", () => {
  const keys = [...flatten(en.verify, "verify"), "apiErrors.VERIFY_TOKEN_INVALID", "apiErrors.EMAIL_NOT_VERIFIED"];
  const get = (messages: unknown, path: string) => path.split(".").reduce<unknown>((o, k) => (o as Record<string, unknown> | undefined)?.[k], messages);

  it("exist in English and Korean for every new key", () => {
    expect(keys.length).toBeGreaterThan(12);
    for (const key of keys) {
      for (const [name, messages] of [["en", en], ["ko", ko]] as const) {
        const value = get(messages, key);
        expect(typeof value, `${name} ${key}`).toBe("string");
        expect(value, `${name} ${key}`).not.toBe("");
      }
    }
    expect(flatten(ko.verify, "verify").sort()).toEqual(flatten(en.verify, "verify").sort());
  });

  it("says the run gate in plain words", () => {
    expect(en.apiErrors.EMAIL_NOT_VERIFIED).toBe("Confirm your email to run an analysis.");
    expect(en.verify.banner.text).toBe("Please confirm your email. We sent you a link.");
  });
});
