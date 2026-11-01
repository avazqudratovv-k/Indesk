import { describe, expect, it, vi } from "vitest";
import en from "@/messages/en.json";
import ko from "@/messages/ko.json";
import { ApiError, apiErrorKey, errorFromResponse, knownCodes } from "@/lib/api/errors";
import { createApiClient } from "@/lib/api/client";
import { consumeNotice, noticeMessage, writeNotice, type NoticeStorage } from "./notice";
import { mailLang, takeResetToken, TOKEN_MAX_CHARS, validateForgot, validateReset } from "./recovery";

function place(hash: string) {
  const replaceState = vi.fn();
  return { location: { hash, pathname: "/reset-password", search: "?x=1" }, history: { replaceState } };
}

describe("takeResetToken", () => {
  it("reads the token and removes the fragment from the address bar at once", () => {
    const { location, history } = place("#token=abc_DEF-123");
    expect(takeResetToken(location, history)).toBe("abc_DEF-123");
    expect(history.replaceState).toHaveBeenCalledTimes(1);
    expect(history.replaceState).toHaveBeenCalledWith(null, "", "/reset-password?x=1");
  });

  it("clears the fragment even when it holds no usable token", () => {
    for (const hash of ["#other=1", "#token=", `#token=${"x".repeat(TOKEN_MAX_CHARS + 1)}`, "#"]) {
      const { location, history } = place(hash);
      expect(takeResetToken(location, history), hash).toBeNull();
      expect(history.replaceState, hash).toHaveBeenCalledTimes(1);
    }
  });

  it("with no fragment there is no token and nothing to clear", () => {
    const { location, history } = place("");
    expect(takeResetToken(location, history)).toBeNull();
    expect(history.replaceState).not.toHaveBeenCalled();
  });

  it("never puts the token in the address it writes", () => {
    const { location, history } = place("#token=SECRETVALUE");
    takeResetToken(location, history);
    expect(JSON.stringify(history.replaceState.mock.calls)).not.toContain("SECRETVALUE");
  });
});

describe("the password rules", () => {
  it("follows sign-up: 10 to 128 characters", () => {
    expect(validateReset("x".repeat(9), "x".repeat(9)).password).toBe("passwordTooShort");
    expect(validateReset("x".repeat(10), "x".repeat(10))).toEqual({});
    expect(validateReset("x".repeat(128), "x".repeat(128))).toEqual({});
    expect(validateReset("x".repeat(129), "x".repeat(129)).password).toBe("passwordTooLong");
    expect(validateReset("", "").password).toBe("passwordRequired");
  });

  it("needs the same password twice", () => {
    expect(validateReset("x".repeat(10), "").confirm).toBe("confirmRequired");
    expect(validateReset("x".repeat(10), "y".repeat(10)).confirm).toBe("confirmMismatch");
  });

  it("checks the email on the forgot form", () => {
    expect(validateForgot("")).toBe("emailRequired");
    expect(validateForgot("nope")).toBe("emailInvalid");
    expect(validateForgot("ada@example.com")).toBeNull();
  });
});

describe("the requests", () => {
  function clientWith(respond: () => Response) {
    const fetch = vi.fn(async () => respond());
    const client = createApiClient({ fetch: fetch as unknown as typeof globalThis.fetch, refresh: async () => "ok", onAuthLost: () => {} });
    return { client, fetch };
  }

  it("treats every empty 202 the same, whatever the account", async () => {
    const answers = [];
    for (let n = 0; n < 3; n++) {
      const { client } = clientWith(() => new Response(null, { status: 202 }));
      answers.push(await client.request("/api/auth/password/forgot", { method: "POST", json: { email: `u${n}@example.com`, lang: "en" }, refreshOn401: false }));
    }
    expect(answers).toEqual([undefined, undefined, undefined]);
  });

  it("sends lang en or ko only", () => {
    expect(mailLang("ko")).toBe("ko");
    for (const other of ["en", "ja", "", "zz"]) expect(mailLang(other)).toBe("en");
  });

  it("maps the new and the shared errors to codes", async () => {
    const body = (code: string) => JSON.stringify({ error: { code } });
    const reset = await errorFromResponse(new Response(body("RESET_TOKEN_INVALID"), { status: 400 }));
    expect(reset.code).toBe("RESET_TOKEN_INVALID");
    expect(apiErrorKey(reset)).toBe("RESET_TOKEN_INVALID");
    const limited = await errorFromResponse(new Response(body("RATE_LIMITED"), { status: 429, headers: { "Retry-After": "600" } }));
    expect(apiErrorKey(limited)).toBe("RATE_LIMITED_WAIT");
    expect((await errorFromResponse(new Response(body("NOT_READY"), { status: 503 }))).code).toBe("NOT_READY");
    expect((await errorFromResponse(new Response(body("VALIDATION_ERROR"), { status: 422 }))).code).toBe("VALIDATION_ERROR");
    expect(knownCodes).toContain("RESET_TOKEN_INVALID");
  });
});

describe("the password-changed notice", () => {
  it("is written, read once and has a message", () => {
    const data: Record<string, string> = {};
    const storage: NoticeStorage = {
      getItem: (k) => data[k] ?? null,
      setItem: (k, v) => {
        data[k] = v;
      },
      removeItem: (k) => {
        delete data[k];
      },
    };
    writeNotice(storage, { kind: "passwordChanged" });
    const notice = consumeNotice(storage);
    expect(notice).toEqual({ kind: "passwordChanged" });
    expect(noticeMessage(notice!)).toEqual({ key: "passwordChanged" });
    expect(consumeNotice(storage)).toBeNull();
  });
});

function flatten(value: unknown, prefix = ""): string[] {
  if (typeof value === "string") return [prefix];
  if (value && typeof value === "object") return Object.entries(value).flatMap(([k, v]) => flatten(v, prefix ? `${prefix}.${k}` : k));
  return [];
}

describe("the strings", () => {
  const newKeys = [
    ...flatten(en.recovery, "recovery"),
    "auth.forgotLink",
    "notice.passwordChanged",
    "apiErrors.RESET_TOKEN_INVALID",
  ];

  it("exist in English and Korean for every new key", () => {
    const get = (messages: unknown, path: string) => path.split(".").reduce<unknown>((o, k) => (o as Record<string, unknown> | undefined)?.[k], messages);
    expect(newKeys.length).toBeGreaterThan(15);
    for (const key of newKeys) {
      expect(typeof get(en, key), `en ${key}`).toBe("string");
      expect(get(en, key), `en ${key}`).not.toBe("");
      expect(typeof get(ko, key), `ko ${key}`).toBe("string");
      expect(get(ko, key), `ko ${key}`).not.toBe("");
    }
    expect(flatten(ko.recovery, "recovery").sort()).toEqual(flatten(en.recovery, "recovery").sort());
  });

  it("says the same neutral line for the forgot answer and never claims delivery", () => {
    expect(en.recovery.forgot.sent).toBe("If an account exists for this address, we sent a link.");
    expect(ko.recovery.forgot.sent).not.toMatch(/도착|전달되었/);
  });
});

it("ApiError carries only a code", () => {
  expect(new ApiError(400, "RESET_TOKEN_INVALID").message).toBe("RESET_TOKEN_INVALID");
});
