import { describe, expect, it } from "vitest";
import { confidenceOf, METHOD_CODES, methodId, parseRowsLocation, REASON_CODES, reasonId, toolLabelId } from "./codes";

describe("closed codes", () => {
  it("passes every known code through", () => {
    for (const code of REASON_CODES) expect(reasonId(code)).toBe(code);
    for (const code of METHOD_CODES) expect(methodId(code)).toBe(code);
    for (const code of ["high", "medium", "low"]) expect(confidenceOf(code)).toBe(code);
  });

  it("maps an unknown or wrong-typed code to the neutral one, never to the raw value", () => {
    for (const bad of ["future_reason", "", "ROWS_MISMATCH", null, undefined, 3, {}, "__proto__"]) {
      expect(reasonId(bad)).toBe("unknown");
      expect(methodId(bad)).toBe("unknown");
      expect(confidenceOf(bad)).toBeNull();
    }
  });

  it("names only the one tool it knows", () => {
    expect(toolLabelId("run_python")).toBe("pandas");
    expect(toolLabelId("rm -rf")).toBeNull();
    expect(toolLabelId(undefined)).toBeNull();
  });

  it("parses the server's row range and nothing else", () => {
    expect(parseRowsLocation("rows 1–4079")).toEqual({ from: 1, to: 4079 });
    expect(parseRowsLocation("rows 1-10")).toEqual({ from: 1, to: 10 });
    for (const bad of ["page 12", "rows a–b", "rows 1–", "", null, "rows 1–2 and more"]) expect(parseRowsLocation(bad)).toBeNull();
  });
});
