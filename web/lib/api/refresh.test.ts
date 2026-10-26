import { describe, expect, it, vi } from "vitest";
import { createRefresher, type ChannelLike, type LockManagerLike, type RefreshResult } from "./refresh";

// A Web Locks stand-in: exclusive, first come first served, shared by "tabs" that get the same instance.
function fakeLocks(): LockManagerLike & { maxHeld: () => number } {
  let tail: Promise<unknown> = Promise.resolve();
  let held = 0;
  let max = 0;
  return {
    request(_name, callback) {
      const run = tail.then(async () => {
        held += 1;
        max = Math.max(max, held);
        try {
          return await callback();
        } finally {
          held -= 1;
        }
      });
      tail = run.catch(() => {});
      return run as Promise<never>;
    },
    maxHeld: () => max,
  };
}

function fakeBus() {
  const listeners: ((at: number) => void)[] = [];
  const channelFor = (): ChannelLike => {
    let mine: ((at: number) => void) | undefined;
    return {
      post: (at) => listeners.filter((l) => l !== mine).forEach((l) => l(at)),
      onMessage: (listener) => {
        mine = listener;
        listeners.push(listener);
      },
    };
  };
  return { channelFor };
}

function clock() {
  let t = 1000;
  return { now: () => t, tick: (n = 10) => (t += n) };
}

describe("single-flight refresh in one tab", () => {
  it("many concurrent 401s cause exactly one refresh", async () => {
    const c = clock();
    const call = vi.fn(async (): Promise<RefreshResult> => {
      await Promise.resolve();
      return "ok";
    });
    const refresh = createRefresher({ call, stillSignedIn: async () => false, now: c.now });
    const started = c.now();
    c.tick();
    const results = await Promise.all(Array.from({ length: 25 }, () => refresh(started)));
    expect(call).toHaveBeenCalledTimes(1);
    expect(results.every((r) => r === "ok")).toBe(true);
  });

  it("a request that started before a finished refresh does not refresh again", async () => {
    const c = clock();
    const call = vi.fn(async (): Promise<RefreshResult> => "ok");
    const refresh = createRefresher({ call, stillSignedIn: async () => false, now: c.now });
    const early = c.now();
    c.tick();
    await refresh(early);
    c.tick();
    expect(await refresh(early)).toBe("ok");
    expect(call).toHaveBeenCalledTimes(1);
  });

  it("a request sent after the refresh may refresh again", async () => {
    const c = clock();
    const call = vi.fn(async (): Promise<RefreshResult> => "ok");
    const refresh = createRefresher({ call, stillSignedIn: async () => false, now: c.now });
    await refresh(c.now());
    c.tick(5000);
    await refresh(c.now());
    expect(call).toHaveBeenCalledTimes(2);
  });

  it("a denied refresh checks /me once and reports denied when that fails too", async () => {
    const stillSignedIn = vi.fn(async () => false);
    const refresh = createRefresher({ call: async () => "denied", stillSignedIn });
    expect(await refresh(Date.now())).toBe("denied");
    expect(stillSignedIn).toHaveBeenCalledTimes(1);
  });

  it("a denied refresh is forgiven when another tab already won", async () => {
    const refresh = createRefresher({ call: async () => "denied", stillSignedIn: async () => true });
    expect(await refresh(Date.now())).toBe("ok");
  });

  it("a network failure is reported as failed, not denied, and does not call /me", async () => {
    const stillSignedIn = vi.fn(async () => true);
    const refresh = createRefresher({ call: async () => "failed", stillSignedIn });
    expect(await refresh(Date.now())).toBe("failed");
    expect(stillSignedIn).not.toHaveBeenCalled();
  });

  it("a finished refresh does not block the next one", async () => {
    const c = clock();
    const call = vi.fn(async (): Promise<RefreshResult> => "denied");
    const refresh = createRefresher({ call, stillSignedIn: async () => false, now: c.now });
    await refresh(c.now());
    await refresh(c.now());
    expect(call).toHaveBeenCalledTimes(2);
  });
});

describe("cross-tab lock", () => {
  it("two tabs hit by a 401 at once refresh one after the other, and the second skips", async () => {
    const locks = fakeLocks();
    const bus = fakeBus();
    const c = clock();
    let inFlight = 0;
    let overlap = 0;
    const call = vi.fn(async (): Promise<RefreshResult> => {
      inFlight += 1;
      overlap = Math.max(overlap, inFlight);
      await new Promise((resolve) => setTimeout(resolve, 5));
      inFlight -= 1;
      c.tick();
      return "ok";
    });
    const tab = () => createRefresher({ call, stillSignedIn: async () => false, locks, channel: bus.channelFor(), now: c.now });
    const a = tab();
    const b = tab();
    const started = c.now();
    c.tick();
    const [ra, rb] = await Promise.all([a(started), b(started)]);
    expect([ra, rb]).toEqual(["ok", "ok"]);
    expect(call).toHaveBeenCalledTimes(1); // the second tab saw the broadcast and skipped
    expect(overlap).toBe(1);
    expect(locks.maxHeld()).toBe(1);
  });

  it("without navigator.locks each tab still refreshes at most once per burst", async () => {
    const call = vi.fn(async (): Promise<RefreshResult> => "ok");
    const refresh = createRefresher({ call, stillSignedIn: async () => false });
    const started = Date.now() - 1;
    await Promise.all([refresh(started), refresh(started), refresh(started)]);
    expect(call).toHaveBeenCalledTimes(1);
  });
});
