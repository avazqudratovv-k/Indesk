import { describe, expect, it } from "vitest";
import { parseUpload } from "./parse";

describe("parseUpload pages_without_text", () => {
  const upload = { id: "u1", expires_at: "2026-10-31T00:00:00Z", row_count: null };

  it("keeps a whole number, including 0", () => {
    expect(parseUpload({ ...upload, pages_without_text: 4 })?.pagesWithoutText).toBe(4);
    expect(parseUpload({ ...upload, pages_without_text: 0 })?.pagesWithoutText).toBe(0);
  });

  it("leaves the field out when it is absent (CSV) or not a whole number", () => {
    expect(parseUpload({ ...upload, row_count: 5 })).not.toHaveProperty("pagesWithoutText");
    for (const bad of [-1, 1.5, "3", null]) expect(parseUpload({ ...upload, pages_without_text: bad })).not.toHaveProperty("pagesWithoutText");
  });
});
