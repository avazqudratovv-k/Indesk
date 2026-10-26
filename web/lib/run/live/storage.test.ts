import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { clearRunId, readRunId, writeRunId } from "./storage";

const id = "123e4567-e89b-12d3-a456-426614174000";

class MemoryStorage {
  map = new Map<string, string>();
  getItem(key: string) { return this.map.get(key) ?? null; }
  setItem(key: string, value: string) { this.map.set(key, value); }
  removeItem(key: string) { this.map.delete(key); }
}

describe("run id storage", () => {
  let store: MemoryStorage;
  beforeEach(() => {
    store = new MemoryStorage();
    Object.defineProperty(globalThis, "localStorage", { value: store, configurable: true });
  });
  afterEach(() => {
    Reflect.deleteProperty(globalThis, "localStorage");
  });

  it("is keyed by user", () => {
    writeRunId("user-1", id);
    expect(readRunId("user-1")).toBe(id);
    expect(readRunId("user-2")).toBeNull();
  });

  it("stores only the id, nothing else", () => {
    writeRunId("user-1", id);
    expect([...store.map.values()]).toEqual([id]);
  });

  it("refuses to store or read anything that is not a run id", () => {
    writeRunId("user-1", "some question text");
    expect(store.map.size).toBe(0);
    store.setItem("indesk:run:user-1", "<script>");
    expect(readRunId("user-1")).toBeNull();
  });

  it("clears on logout", () => {
    writeRunId("user-1", id);
    clearRunId("user-1");
    expect(readRunId("user-1")).toBeNull();
  });

  it("works when storage throws", () => {
    Object.defineProperty(globalThis, "localStorage", {
      value: { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); }, removeItem() { throw new Error("blocked"); } },
      configurable: true,
    });
    expect(() => writeRunId("u", id)).not.toThrow();
    expect(readRunId("u")).toBeNull();
    expect(() => clearRunId("u")).not.toThrow();
  });
});
