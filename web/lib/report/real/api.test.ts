import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api/errors";
import { langNote, loadReport, loadReportLang } from "./api";
import { fixtures } from "./fixtures";

const ok = (body: unknown) => (async () => body) as never;
const fail = (status: number, code: ConstructorParameters<typeof ApiError>[1]) => (async () => { throw new ApiError(status, code); }) as never;

describe("loadReport", () => {
  it("is ready with a valid body", async () => {
    const result = await loadReport("11111111-1111-4111-8111-111111111111", undefined, ok(fixtures.answered));
    expect(result.status).toBe("ready");
  });

  it("asks for the id it was given, escaped", async () => {
    let path = "";
    await loadReport("a/b", undefined, (async (p: string) => { path = p; return fixtures.answered; }) as never);
    expect(path).toBe("/api/reports/a%2Fb");
  });

  it("gives one notFound state for 404", async () => {
    expect((await loadReport("x", undefined, fail(404, "NOT_FOUND"))).status).toBe("notFound");
  });

  it("gives unauthorized for a 401 that survived the refresh", async () => {
    expect((await loadReport("x", undefined, fail(401, "UNAUTHENTICATED"))).status).toBe("unauthorized");
  });

  it("gives error for a network failure, a 500 and a body of the wrong shape", async () => {
    expect((await loadReport("x", undefined, fail(0, "NETWORK"))).status).toBe("error");
    expect((await loadReport("x", undefined, fail(500, "INTERNAL"))).status).toBe("error");
    expect((await loadReport("x", undefined, ok({ nope: true }))).status).toBe("error");
    expect((await loadReport("x", undefined, (async () => { throw new Error("boom"); }) as never)).status).toBe("error");
  });
});

describe("loadReportLang", () => {
  it("reads Korean as ko and every other known language as en (Cat writes English then)", async () => {
    expect(await loadReportLang("r", undefined, ok({ lang: "ko" }))).toBe("ko");
    for (const lang of ["en", "ja", "ru", "uz"]) expect(await loadReportLang("r", undefined, ok({ lang }))).toBe("en");
  });

  it("is null when the run cannot be read or the language is unknown", async () => {
    expect(await loadReportLang("r", undefined, fail(404, "NOT_FOUND"))).toBeNull();
    expect(await loadReportLang("r", undefined, ok({ lang: "xx" }))).toBeNull();
    expect(await loadReportLang("r", undefined, ok(null))).toBeNull();
    expect(await loadReportLang("r", undefined, ok({}))).toBeNull();
  });
});

describe("langNote", () => {
  it("shows only when the language is known and differs from the site language", () => {
    expect(langNote("en", "ko")).toBe("en");
    expect(langNote("ko", "en")).toBe("ko");
    expect(langNote("en", "en")).toBeNull();
    expect(langNote(null, "ko")).toBeNull();
  });
});
