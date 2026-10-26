import { describe, expect, it } from "vitest";
import { checkFile, SLOT_MAX } from "./validate";

const csv = (name: string) => new File(["a,b\n1,2"], name, { type: "text/csv" });
const base = { slot: "files" as const, takenNames: new Set<string>(), count: 0, partnerKind: null, csvOnly: true };

describe("Ask takes exactly one CSV", () => {
  it("allows one file in the Ask slot", () => {
    expect(SLOT_MAX.files).toBe(1);
    expect(checkFile(csv("a.csv"), base)).toBeNull();
  });

  it("turns a second file away with slotFull and does not replace the first", () => {
    expect(checkFile(csv("b.csv"), { ...base, count: 1, takenNames: new Set(["a.csv"]) })).toBe("slotFull");
  });

  it("checks a drop of two files as a whole: the first is accepted, the second is not", () => {
    const taken = new Set<string>();
    expect(checkFile(csv("a.csv"), { ...base, takenNames: taken, count: 0 })).toBeNull();
    taken.add("a.csv");
    expect(checkFile(csv("b.csv"), { ...base, takenNames: taken, count: 1 })).toBe("slotFull");
  });
});
