import { describe, expect, it, vi } from "vitest";
import { runLogout } from "./logout-flow";

describe("runLogout", () => {
  it("ends the session first and only then goes Home", async () => {
    const order: string[] = [];
    const result = await runLogout(
      async () => {
        order.push("end");
      },
      () => order.push("home"),
    );
    expect(result).toBe("done");
    expect(order).toEqual(["end", "home"]);
  });

  it("stays where it is when the server cannot be reached", async () => {
    const goHome = vi.fn();
    const result = await runLogout(async () => {
      throw new Error("offline");
    }, goHome);
    expect(result).toBe("failed");
    expect(goHome).not.toHaveBeenCalled();
  });
});
