import { describe, expect, it, vi } from "vitest";
import { createApiClient } from "./client";
import { ApiError } from "./errors";
import { createRefresher } from "./refresh";

type Handler = (url: string, init: RequestInit) => Response | Promise<Response>;

const json = (status: number, body: unknown = {}, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", ...headers } });

function setup(handler: Handler) {
  const calls: { url: string; init: RequestInit }[] = [];
  let signedIn = true; // the refresh cookie is still good until a test says otherwise
  let accessValid = false;
  const fetchStub = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = String(input);
    calls.push({ url, init });
    if (url === "/api/auth/refresh") {
      if (signedIn) {
        accessValid = true;
        return new Response(null, { status: 204 });
      }
      return json(401, { error: { code: "UNAUTHENTICATED" } });
    }
    if (url === "/api/me") return accessValid ? json(200, { id: "u" }) : json(401, { error: { code: "UNAUTHENTICATED" } });
    return accessValid ? handler(url, init) : json(401, { error: { code: "UNAUTHENTICATED" } });
  });
  const onAuthLost = vi.fn();
  let tick = 1;
  const now = () => (tick += 1);
  const client = createApiClient({
    fetch: fetchStub as unknown as typeof fetch,
    refresh: (started) => refresher(started),
    onAuthLost,
    now,
  });
  const refresher = createRefresher({
    call: () => client.refreshCall(),
    stillSignedIn: async () => false,
    now,
  });
  return { client, calls, onAuthLost, setRefreshAlive: (alive: boolean) => (signedIn = alive), urls: () => calls.map((c) => c.url) };
}

describe("401 handling", () => {
  it("refreshes once and retries the call once", async () => {
    const t = setup(() => json(200, { ok: true }));
    await expect(t.client.request("/api/things")).resolves.toEqual({ ok: true });
    expect(t.urls()).toEqual(["/api/things", "/api/auth/refresh", "/api/things"]);
  });

  it("many concurrent calls that all get a 401 cause exactly one refresh", async () => {
    const t = setup(() => json(200, { ok: true }));
    await Promise.all(Array.from({ length: 20 }, (_, i) => t.client.request(`/api/things/${i}`)));
    expect(t.urls().filter((u) => u === "/api/auth/refresh")).toHaveLength(1);
    expect(t.urls().filter((u) => u.startsWith("/api/things"))).toHaveLength(40); // 20 first tries + 20 retries
  });

  it("when the refresh is denied it signs out, does not retry and does not loop", async () => {
    const t = setup(() => json(200));
    t.setRefreshAlive(false);
    await expect(t.client.request("/api/things")).rejects.toMatchObject({ code: "UNAUTHENTICATED" });
    expect(t.onAuthLost).toHaveBeenCalledTimes(1);
    expect(t.urls().filter((u) => u === "/api/auth/refresh")).toHaveLength(1);
    expect(t.urls().filter((u) => u === "/api/things")).toHaveLength(1);
  });

  it("gives up after one retry if the retry is a 401 again", async () => {
    const t = setup(() => json(401, { error: { code: "UNAUTHENTICATED" } }));
    await expect(t.client.request("/api/things")).rejects.toBeInstanceOf(ApiError);
    expect(t.urls().filter((u) => u === "/api/things")).toHaveLength(2);
    expect(t.onAuthLost).toHaveBeenCalledTimes(1);
  });

  it("never refreshes for the auth endpoints themselves", async () => {
    const t = setup(() => json(200));
    await expect(t.client.request("/api/auth/login", { method: "POST", json: { a: 1 }, refreshOn401: false })).rejects.toMatchObject({ status: 401 });
    expect(t.urls()).toEqual(["/api/auth/login"]);
    expect(t.onAuthLost).not.toHaveBeenCalled();
  });

  it("does not retry anything but a 401 (a 500 is sent once)", async () => {
    const t = setup(() => json(500, { error: { code: "INTERNAL" } }));
    await t.client.request("/api/x").catch(() => {});
    expect(t.urls().filter((u) => u === "/api/x")).toHaveLength(2); // first try 401, retry after refresh gets the 500, no third try
    await expect(t.client.request("/api/x")).rejects.toMatchObject({ code: "INTERNAL" });
  });

  it("a network failure becomes a NETWORK error", async () => {
    const client = createApiClient({
      fetch: (async () => {
        throw new TypeError("failed to fetch");
      }) as unknown as typeof fetch,
      refresh: async () => "ok",
      onAuthLost: () => {},
    });
    await expect(client.request("/api/x")).rejects.toMatchObject({ code: "NETWORK", status: 0 });
  });
});

describe("request bodies", () => {
  it("re-sends a multipart body from the original File on the retry", async () => {
    const seen: (FormData | undefined)[] = [];
    const t = setup((_url, init) => {
      seen.push(init.body as FormData);
      return json(200, { id: "up_1" });
    });
    const form = new FormData();
    form.append("file", new File(["a,b\n1,2\n"], "data.csv", { type: "text/csv" }));
    form.append("consent", "true");
    await t.client.request("/api/uploads", { method: "POST", form });
    // First attempt got a 401 before reaching the handler; the retry carried the same FormData with a readable File.
    const sent = t.calls.filter((c) => c.url === "/api/uploads").map((c) => c.init.body as FormData);
    expect(sent).toHaveLength(2);
    expect(sent[0]).toBe(form);
    expect(sent[1]).toBe(form);
    expect(await (seen[0]!.get("file") as File).text()).toBe("a,b\n1,2\n");
    expect(seen[0]!.get("consent")).toBe("true");
    expect(t.calls[0].init.headers).not.toHaveProperty("Content-Type"); // the browser sets the boundary
  });

  it("re-sends a JSON body unchanged on the retry", async () => {
    const t = setup(() => json(200));
    await t.client.request("/api/runs", { method: "POST", json: { question: "q" } });
    const bodies = t.calls.filter((c) => c.url === "/api/runs").map((c) => c.init.body);
    expect(bodies).toEqual([JSON.stringify({ question: "q" }), JSON.stringify({ question: "q" })]);
  });
});
