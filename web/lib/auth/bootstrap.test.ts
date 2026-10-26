import { describe, expect, it, vi } from "vitest";
import type { User } from "@/lib/types";
import { resolveUnknownSession } from "./bootstrap";

const user = { id: "u1", display_name: "A" } as User;

describe("resolveUnknownSession", () => {
  it("without the hint it sends nothing and is signed out", async () => {
    const refresh = vi.fn();
    const me = vi.fn();
    const out = await resolveUnknownSession({ hint: () => false, refresh, me });
    expect(out.session.status).toBe("signedOut");
    expect(refresh).not.toHaveBeenCalled();
    expect(me).not.toHaveBeenCalled();
  });

  it("with the hint it refreshes once, then reads /me", async () => {
    const refresh = vi.fn(async () => "ok" as const);
    const me = vi.fn(async () => user);
    const out = await resolveUnknownSession({ hint: () => true, refresh, me });
    expect(out.session).toMatchObject({ status: "signedIn", user });
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(me).toHaveBeenCalledTimes(1);
  });

  it("a denied refresh is signed out and clears the hint", async () => {
    const out = await resolveUnknownSession({ hint: () => true, refresh: async () => "denied", me: vi.fn() });
    expect(out).toMatchObject({ clearHint: true, session: { status: "signedOut" } });
  });

  it("a network failure is signed out for now but keeps the hint", async () => {
    const out = await resolveUnknownSession({ hint: () => true, refresh: async () => "failed", me: vi.fn() });
    expect(out).toMatchObject({ clearHint: false, session: { status: "signedOut" } });
  });
});
