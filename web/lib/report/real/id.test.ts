import { describe, expect, it } from "vitest";
import { isRealReportId } from "./id";

describe("isRealReportId", () => {
  it("treats a UUID as a real report and a mock id as not", () => {
    expect(isRealReportId("11111111-1111-4111-8111-111111111111")).toBe(true);
    expect(isRealReportId("AAAAAAAA-1111-4111-8111-111111111111")).toBe(true);
    for (const mock of ["rep_01", "rep_04", "", "../etc", "11111111-1111-4111-8111-11111111111", "11111111-1111-4111-8111-1111111111111"]) expect(isRealReportId(mock)).toBe(false);
  });
});
