import { ApiError, errorFromResponse, networkError } from "./errors";
import { browserChannel, browserLocks, createRefresher, type RefreshResult, type Refresher } from "./refresh";

// Bodies must be re-sendable: a string (JSON) or FormData built from Files. A stream cannot be sent twice.
export type ApiRequest = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  json?: unknown;
  form?: FormData;
  signal?: AbortSignal;
  // false for the auth endpoints themselves: a 401 there is an answer, not an expired session.
  refreshOn401?: boolean;
};

export type ClientDeps = {
  fetch: typeof fetch;
  refresh: Refresher;
  onAuthLost: () => void;
  now?: () => number;
  timeoutMs?: number;
};

export type ApiClient = {
  request<T = undefined>(path: string, init?: ApiRequest): Promise<T>;
  // The raw POST /api/auth/refresh. Only the refresher calls this; everything else uses `refresh`.
  refreshCall(): Promise<RefreshResult>;
  // The coordinated refresh (one at a time per tab and across tabs). `startedAt` is when the failing request began.
  refresh: Refresher;
};

const defaultTimeoutMs = 15_000;

export function createApiClient(deps: ClientDeps): ApiClient {
  const now = deps.now ?? Date.now;

  async function send(path: string, init: ApiRequest): Promise<Response> {
    const headers: Record<string, string> = {};
    let body: string | FormData | undefined;
    if (init.form) body = init.form; // the browser sets the multipart boundary itself
    else if (init.json !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(init.json);
    }
    const timeout = AbortSignal.timeout(deps.timeoutMs ?? defaultTimeoutMs);
    const signal = init.signal ? AbortSignal.any([init.signal, timeout]) : timeout;
    try {
      return await deps.fetch(path, { method: init.method ?? "GET", headers, body, signal, credentials: "same-origin", cache: "no-store" });
    } catch {
      throw networkError();
    }
  }

  async function request<T>(path: string, init: ApiRequest = {}): Promise<T> {
    const startedAt = now();
    let response = await send(path, init);
    // Only a 401 is retried, once, after a refresh. Nothing else is ever re-sent.
    if (response.status === 401 && init.refreshOn401 !== false) {
      const result = await deps.refresh(startedAt);
      if (result === "denied") {
        deps.onAuthLost();
        throw new ApiError(401, "UNAUTHENTICATED");
      }
      if (result === "failed") throw networkError();
      response = await send(path, init);
      if (response.status === 401) {
        deps.onAuthLost();
        throw new ApiError(401, "UNAUTHENTICATED");
      }
    }
    if (!response.ok) throw await errorFromResponse(response);
    if (response.status === 204) return undefined as T;
    try {
      return (await response.json()) as T;
    } catch {
      throw new ApiError(response.status, "UNKNOWN");
    }
  }

  async function refreshCall(): Promise<RefreshResult> {
    try {
      const response = await send("/api/auth/refresh", { method: "POST" });
      if (response.ok) return "ok";
      return response.status === 401 ? "denied" : "failed";
    } catch {
      return "failed";
    }
  }

  return { request, refreshCall, refresh: deps.refresh };
}

// The app-wide client. onAuthLost is set by the session provider.
let authLostHandler: () => void = () => {};
export function setAuthLostHandler(handler: () => void): void {
  authLostHandler = handler;
}

function createDefaultClient(): ApiClient {
  const refresh = createRefresher({
    call: () => client.refreshCall(),
    stillSignedIn: async () => {
      try {
        await client.request("/api/me", { refreshOn401: false });
        return true;
      } catch {
        return false;
      }
    },
    locks: browserLocks(),
    channel: browserChannel("indesk-auth"),
  });
  const client = createApiClient({ fetch: (...args) => globalThis.fetch(...args), refresh, onAuthLost: () => authLostHandler() });
  return client;
}

let defaultClient: ApiClient | undefined;
export function apiClient(): ApiClient {
  defaultClient ??= createDefaultClient();
  return defaultClient;
}
