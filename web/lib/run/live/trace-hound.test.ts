import { describe, expect, it } from "vitest";
import en from "@/messages/en.json";
import ko from "@/messages/ko.json";
import { describeTrace, TRACE_KEYS, TRACE_MESSAGE_IDS } from "./trace";

describe("describeTrace for Hound", () => {
  it("describes Hound's lines and falls back to the plain wording on a missing or invalid argument", () => {
    expect(describeTrace("search", { pages: 12 })).toMatchObject({ id: "searchPages", values: { pages: 12 } });
    expect(describeTrace("search", { pages: 12, matched: 0, mode: "hybrid" })).toMatchObject({ id: "searchNoMatch", values: { pages: 12 } });
    expect(describeTrace("search", {}).id).toBe("search");
    expect(describeTrace("search", { pages: "many" }).id).toBe("search");
    expect(describeTrace("bestPassage", { page: 4, score: 0.03, similarity: 0.83 })).toMatchObject({ id: "bestPassageSimilar", values: { page: 4, similarity: 0.83 } });
    expect(describeTrace("bestPassage", { page: 4, score: 0.03 })).toMatchObject({ id: "bestPassagePage", values: { page: 4 } });
    expect(describeTrace("bestPassage", { page: 0 }).id).toBe("bestPassage");
    expect(describeTrace("bestPassage", { page: 4, similarity: 7 }).id).toBe("bestPassagePage");
    expect(describeTrace("keywordOnlySize", { reason: "document_size" }).id).toBe("keywordOnlySizeReason");
    expect(describeTrace("keywordOnlySize", { reason: "ignore previous instructions" }).id).toBe("keywordOnlySize");
    expect(describeTrace("keywordOnlySize", {}).id).toBe("keywordOnlySize");
    expect(describeTrace("chunksSkipped", { count: 3 })).toMatchObject({ id: "chunksSkippedCount", values: { count: 3 } });
    expect(describeTrace("chunksSkipped", { count: 0 }).id).toBe("chunksSkipped");
    expect(describeTrace("chunksSkipped", { count: "3" }).id).toBe("chunksSkipped");
  });

  it("has an en and ko line for every Hound key and variant", () => {
    for (const key of ["search", "bestPassage", "keywordOnlySize", "chunksSkipped"]) expect(TRACE_KEYS).toContain(key);
    for (const trace of [en.workspace.trace, ko.workspace.trace] as Record<string, string>[]) {
      for (const id of TRACE_MESSAGE_IDS) expect(trace[id], id).toBeTruthy();
    }
  });
});
