import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api/errors";
import example from "./__fixtures__/example.json";
import { langNote, loadExample, loadReport, reportLang } from "./api";
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

describe("reportLang", () => {
  it("reads Korean as ko and every other known language as en (Cat writes English then)", () => {
    expect(reportLang("ko")).toBe("ko");
    for (const lang of ["en", "ja", "ru", "uz"]) expect(reportLang(lang)).toBe("en");
  });

  it("is null when the field is missing or not a known code", () => {
    for (const bad of ["xx", "", undefined, null, 5, {}]) expect(reportLang(bad)).toBeNull();
  });
});

describe("report language from the payload", () => {
  it("comes with the report, with no second request", async () => {
    const paths: string[] = [];
    const request = (async (p: string) => { paths.push(p); return { ...fixtures.korean, report: { ...fixtures.korean.report, lang: "ko" } }; }) as never;
    const result = await loadReport("11111111-1111-4111-8111-111111111111", undefined, request);
    expect(result).toMatchObject({ status: "ready", lang: "ko" });
    expect(paths).toEqual(["/api/reports/11111111-1111-4111-8111-111111111111"]);
  });
});

describe("loadExample", () => {
  it("reads the example and requests nothing but /api/example", async () => {
    const paths: string[] = [];
    const result = await loadExample(undefined, (async (p: string) => { paths.push(p); return example; }) as never);
    expect(result).toMatchObject({ status: "ready", lang: "en" });
    expect(paths).toEqual(["/api/example"]);
  });

  it("is an error state, not a crash, for a bad body or a failed request", async () => {
    expect((await loadExample(undefined, ok({ nope: true }))).status).toBe("error");
    expect((await loadExample(undefined, fail(500, "INTERNAL"))).status).toBe("error");
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
