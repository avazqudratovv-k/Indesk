import { readFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { clearSampleDismissed, loadSampleFile, readSampleDismissed, SAMPLE_FILE_BYTES, SAMPLE_FILE_HREF, SAMPLE_FILE_NAME, SAMPLE_ID, SampleLoadError, writeSampleDismissed } from "./sample";

class MemoryStorage {
  map = new Map<string, string>();
  getItem(key: string) { return this.map.get(key) ?? null; }
  setItem(key: string, value: string) { this.map.set(key, value); }
  removeItem(key: string) { this.map.delete(key); }
}

describe("sample file size", () => {
  it("equals the real byte size of the file in public/demo", () => {
    const bytes = readFileSync(join(import.meta.dirname, "../../public", SAMPLE_FILE_HREF)).length;
    expect(SAMPLE_FILE_BYTES).toBe(bytes);
  });
});

describe("loadSampleFile", () => {
  const csv = "station,line,boardings\nA,1,10\n";

  it("builds a CSV File with the real name and asks for the static asset only", async () => {
    const urls: string[] = [];
    const fake = (async (input: RequestInfo | URL) => {
      urls.push(String(input));
      return new Response(csv);
    }) as typeof fetch;
    const item = await loadSampleFile(fake);
    expect(urls).toEqual([SAMPLE_FILE_HREF]);
    expect(item.id).toBe(SAMPLE_ID);
    expect(item.kind).toBe("csv");
    expect(item.file.name).toBe(SAMPLE_FILE_NAME);
    expect(item.file.type).toBe("text/csv");
    expect(item.file.size).toBe(csv.length);
  });

  it("fails with SampleLoadError on a bad status, a network error or an empty file", async () => {
    await expect(loadSampleFile((async () => new Response("no", { status: 404 })) as typeof fetch)).rejects.toBeInstanceOf(SampleLoadError);
    await expect(loadSampleFile((async () => { throw new TypeError("offline"); }) as typeof fetch)).rejects.toBeInstanceOf(SampleLoadError);
    await expect(loadSampleFile((async () => new Response("")) as typeof fetch)).rejects.toBeInstanceOf(SampleLoadError);
  });
});

describe("sample dismissal storage", () => {
  let store: MemoryStorage;
  beforeEach(() => {
    store = new MemoryStorage();
    Object.defineProperty(globalThis, "localStorage", { value: store, configurable: true });
  });
  afterEach(() => {
    Reflect.deleteProperty(globalThis, "localStorage");
  });

  it("is off by default and keyed by user id", () => {
    expect(readSampleDismissed("user-1")).toBe(false);
    writeSampleDismissed("user-1");
    expect(readSampleDismissed("user-1")).toBe(true);
    expect(readSampleDismissed("user-2")).toBe(false);
    expect([...store.map.keys()]).toEqual(["indesk:sample-dismissed:user-1"]);
  });

  it("clear brings the sample back", () => {
    writeSampleDismissed("user-1");
    clearSampleDismissed("user-1");
    expect(readSampleDismissed("user-1")).toBe(false);
  });

  it("works when localStorage throws or is missing", () => {
    const broken = { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("full"); }, removeItem() { throw new Error("blocked"); } };
    Object.defineProperty(globalThis, "localStorage", { value: broken, configurable: true });
    expect(readSampleDismissed("user-1")).toBe(false);
    expect(() => writeSampleDismissed("user-1")).not.toThrow();
    expect(() => clearSampleDismissed("user-1")).not.toThrow();
    Reflect.deleteProperty(globalThis, "localStorage");
    expect(readSampleDismissed("user-1")).toBe(false);
    expect(() => writeSampleDismissed("user-1")).not.toThrow();
  });
});
