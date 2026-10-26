import { describe, expect, it } from "vitest";
import en from "@/messages/en.json";
import ko from "@/messages/ko.json";
import { ApiError, apiErrorKey, errorFromResponse, knownCodes, parseRetryAfter, retryMinutes } from "./errors";

function res(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(typeof body === "string" ? body : JSON.stringify(body), { status, headers });
}

describe("errorFromResponse", () => {
  it.each([
    [401, "INVALID_CREDENTIALS"],
    [403, "ORIGIN_NOT_ALLOWED"],
    [409, "EMAIL_TAKEN"],
    [415, "UNSUPPORTED_TYPE"],
    [422, "VALIDATION_ERROR"],
    [429, "RATE_LIMITED"],
    [503, "NOT_READY"],
  ])("reads the code of a %i", async (status, code) => {
    const error = await errorFromResponse(res(status, { error: { code } }));
    expect(error.status).toBe(status);
    expect(error.code).toBe(code);
  });

  it("falls back to the status for an unknown code, without keeping any server text", async () => {
    const error = await errorFromResponse(res(409, { error: { code: "SOMETHING_NEW", message: "secret model text" } }));
    expect(error.code).toBe("UNKNOWN");
    expect(JSON.stringify(error)).not.toContain("secret");
    expect(error.message).not.toContain("secret");
  });

  it("uses the status when the body is not JSON", async () => {
    expect((await errorFromResponse(res(502, "<html>bad gateway</html>"))).code).toBe("INTERNAL");
    expect((await errorFromResponse(res(429, "slow down"))).code).toBe("RATE_LIMITED");
    expect((await errorFromResponse(res(503, ""))).code).toBe("NOT_READY");
  });

  it("reads Retry-After from a 429", async () => {
    const error = await errorFromResponse(res(429, { error: { code: "RATE_LIMITED" } }, { "Retry-After": "125" }));
    expect(error.retryAfter).toBe(125);
    expect(apiErrorKey(error)).toBe("RATE_LIMITED_WAIT");
    expect(retryMinutes(error)).toBe(3);
  });
});

describe("P10 codes", () => {
  it.each([
    [422, "TOO_MANY_FILES"],
    [409, "UPLOAD_IN_USE"],
    [403, "QUOTA_EXHAUSTED"],
    [429, "DAILY_CAP_USER"],
    [429, "DAILY_CAP_GLOBAL"],
    [409, "RUN_ACTIVE"],
  ])("reads %i %s as its own code", async (status, code) => {
    expect((await errorFromResponse(res(status, { error: { code } }))).code).toBe(code);
  });

  const id = "11111111-1111-4111-8111-111111111111";

  it("keeps run_id on RUN_ACTIVE", async () => {
    const error = await errorFromResponse(res(409, { error: { code: "RUN_ACTIVE", run_id: id } }));
    expect(error.runId).toBe(id);
  });

  it("drops a run_id that is not an id, or that comes with another code", async () => {
    expect((await errorFromResponse(res(409, { error: { code: "RUN_ACTIVE", run_id: "../x" } }))).runId).toBeUndefined();
    expect((await errorFromResponse(res(409, { error: { code: "RUN_ACTIVE", run_id: 5 } }))).runId).toBeUndefined();
    expect((await errorFromResponse(res(409, { error: { code: "UPLOAD_IN_USE", run_id: id } }))).runId).toBeUndefined();
    expect((await errorFromResponse(res(409, { error: { code: "RUN_ACTIVE" } }))).runId).toBeUndefined();
  });
});

describe("parseRetryAfter", () => {
  it("accepts whole seconds only, clamped", () => {
    expect(parseRetryAfter("30")).toBe(30);
    expect(parseRetryAfter("999999999")).toBe(86400);
    for (const bad of [null, "", "0", "-5", "abc", "Wed, 21 Oct 2026 07:28:00 GMT", "1.5"]) expect(parseRetryAfter(bad)).toBeUndefined();
  });
});

describe("apiErrorKey", () => {
  it("uses the plain rate-limit text when there is no Retry-After", () => {
    expect(apiErrorKey(new ApiError(429, "RATE_LIMITED"))).toBe("RATE_LIMITED");
  });
});

describe("messages", () => {
  it("has a generic message for every code plus the wait variant, in en and ko, with no raw placeholders", () => {
    for (const messages of [en.apiErrors, ko.apiErrors] as Record<string, string>[]) {
      for (const code of [...knownCodes, "RATE_LIMITED_WAIT"]) {
        expect(messages[code], code).toBeTruthy();
      }
    }
  });
});
