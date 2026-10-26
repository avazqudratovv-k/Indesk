import { describe, expect, it } from "vitest";
import { loginHref, safeNext } from "./safe-next";

describe("safeNext", () => {
  it.each(["/", "/my", "/workspace", "/reports/rep_01", "/plans?x=1#top", "/a/b-c_d"])("accepts %s", (value) => {
    expect(safeNext(value)).toBe(value);
  });

  it.each([
    undefined,
    null,
    "",
    "my",
    "//evil.com",
    "/\\evil.com",
    "\\\\evil.com",
    "https://evil.com",
    "http://localhost:3000/my",
    "javascript:alert(1)",
    "data:text/html,x",
    "/%2F%2Fevil.com",
    "/%5Cevil.com",
    "/ok\nSet-Cookie: a=b",
    "/ok\r\n",
    "/\u0000",
    "/a\\b",
    "/login",
    "/signup?next=/my",
    "/%E0%A4%A",
    "/" + "a".repeat(600),
    ["/my", "/plans"],
  ])("rejects %j", (value) => {
    expect(safeNext(value as string)).toBeUndefined();
  });

  it("builds a login link that carries only a safe path", () => {
    expect(loginHref("/my")).toBe("/login?next=%2Fmy");
    expect(loginHref("//evil.com")).toBe("/login");
    expect(loginHref(undefined)).toBe("/login");
  });
});
