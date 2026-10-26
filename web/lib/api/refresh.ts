// One refresh at a time per tab (a shared promise) and one at a time across tabs (Web Locks).
// The server rotates refresh tokens strictly, so two refreshes with the same token kill the session.
export type RefreshResult = "ok" | "denied" | "failed";

export type LockManagerLike = {
  request<T>(name: string, callback: () => Promise<T>): Promise<T>;
};

export type ChannelLike = {
  post(refreshedAt: number): void;
  onMessage(listener: (refreshedAt: number) => void): void;
};

export type RefresherDeps = {
  // POST /api/auth/refresh: "denied" = the server refused (401), "failed" = network or server error.
  call: () => Promise<RefreshResult>;
  // GET /api/me, used once after a denied refresh because another tab may have just won.
  stillSignedIn: () => Promise<boolean>;
  locks?: LockManagerLike;
  channel?: ChannelLike;
  now?: () => number;
};

export type Refresher = (requestStartedAt: number) => Promise<RefreshResult>;

const lockName = "indesk-refresh";

// `requestStartedAt` is when the failing request was sent. If any tab finished a refresh after that,
// the request simply used an old cookie: skip the refresh and let the caller retry.
export function createRefresher(deps: RefresherDeps): Refresher {
  const now = deps.now ?? Date.now;
  let lastRefreshAt = 0;
  let inflight: Promise<RefreshResult> | null = null;

  deps.channel?.onMessage((at) => {
    lastRefreshAt = Math.max(lastRefreshAt, at);
  });

  async function exec(startedAt: number): Promise<RefreshResult> {
    if (lastRefreshAt >= startedAt) return "ok";
    const result = await deps.call();
    if (result === "ok") {
      lastRefreshAt = now();
      deps.channel?.post(lastRefreshAt);
      return "ok";
    }
    if (result === "denied" && (await deps.stillSignedIn())) return "ok";
    return result;
  }

  return (requestStartedAt) => {
    if (lastRefreshAt >= requestStartedAt) return Promise.resolve("ok");
    if (inflight) return inflight;
    const run = deps.locks ? deps.locks.request(lockName, () => exec(requestStartedAt)) : exec(requestStartedAt);
    const shared = run.finally(() => {
      inflight = null;
    });
    inflight = shared;
    return shared;
  };
}

// Real browser wiring. Each piece is optional: no navigator.locks means per-tab single-flight only.
export function browserLocks(): LockManagerLike | undefined {
  if (typeof navigator === "undefined" || !navigator.locks) return undefined;
  const locks = navigator.locks;
  return { request: (name, callback) => locks.request(name, callback) };
}

export function browserChannel(name: string): ChannelLike | undefined {
  if (typeof BroadcastChannel === "undefined") return undefined;
  const channel = new BroadcastChannel(name);
  return {
    post: (refreshedAt) => channel.postMessage({ refreshedAt }),
    onMessage: (listener) => {
      channel.addEventListener("message", (event: MessageEvent) => {
        const at = (event.data as { refreshedAt?: unknown } | null)?.refreshedAt;
        if (typeof at === "number") listener(at);
      });
    },
  };
}
