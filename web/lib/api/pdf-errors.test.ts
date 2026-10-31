import { describe, expect, it } from "vitest";
import en from "@/messages/en.json";
import ko from "@/messages/ko.json";
import { errorFromResponse } from "./errors";

function res(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status });
}

describe("PDF upload codes", () => {
  const codes = ["PDF_ENCRYPTED", "PDF_NO_TEXT", "PDF_TOO_MANY_PAGES", "PDF_TOO_MUCH_TEXT", "PDF_UNREADABLE", "PARSER_BUSY", "FILE_TOO_LARGE"] as const;

  it.each(codes)("reads %s from the error body", async (code) => {
    expect((await errorFromResponse(res(422, { error: { code } }))).code).toBe(code);
  });

  it("has a message in en and ko for each, without showing the server's own text", async () => {
    for (const messages of [en.apiErrors, ko.apiErrors] as Record<string, string>[]) for (const code of codes) expect(messages[code], code).toBeTruthy();
    const error = await errorFromResponse(res(422, { error: { code: "PDF_NO_TEXT", message: "secret stack" } }));
    expect(error.message).toBe("PDF_NO_TEXT");
  });

  it("gives the page, character and size limits to the messages that name them", () => {
    for (const messages of [en.apiErrors, ko.apiErrors] as Record<string, string>[]) {
      expect(messages.PDF_TOO_MANY_PAGES).toContain("{pages, number}");
      expect(messages.PDF_TOO_MUCH_TEXT).toContain("{chars, number}");
      expect(messages.FILE_TOO_LARGE).toContain("{mb, number}");
    }
  });
});
