import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { isBuilt, navItems, visibleNavItems, type NavItem } from "./nav-items";

const keys = (items: NavItem[]) => items.map((item) => item.key);

describe("nav items", () => {
  it("shows My reports to a signed-in person only, and keeps People hidden until it is built", () => {
    expect(keys(visibleNavItems(true))).toEqual(["home", "workspace", "myReports", "plans"]);
    expect(keys(visibleNavItems(false))).toEqual(["home", "workspace", "plans"]);
  });

  it("un-hiding is the flag alone", () => {
    const on = navItems.map((item) => ({ ...item, built: true }));
    expect(keys(visibleNavItems(true, on))).toEqual(["home", "workspace", "people", "myReports", "plans"]);
    expect(keys(visibleNavItems(false, on))).toEqual(["home", "workspace", "plans"]);
  });

  it("marks /people as not built, everything else (including /my) as built", () => {
    expect(isBuilt("/people")).toBe(false);
    for (const href of ["/", "/workspace", "/my", "/plans"]) expect(isBuilt(href)).toBe(true);
  });
});

describe("the mobile tab bar and the unbuilt pages", () => {
  const read = (file: string) => readFileSync(join(__dirname, file), "utf8");

  it("takes its tabs from the same flags", () => {
    expect(read("TabBar.tsx")).toContain("visibleNavItems(");
  });

  it("makes /people answer 404 while its flag is off", () => {
    expect(read("../../app/people/page.tsx")).toContain('if (!isBuilt("/people")) notFound();');
  });

  it("serves /my behind RequireAuth, with no 404 guard", () => {
    const page = read("../../app/my/page.tsx");
    expect(page).toContain("<RequireAuth>");
    expect(page).not.toContain("notFound");
  });
});

describe("the shared report page", () => {
  it("is not built: /s answers 404", () => {
    expect(isBuilt("/s")).toBe(false);
    expect(readFileSync(join(__dirname, "../../app/s/[token]/page.tsx"), "utf8")).toContain('if (!isBuilt("/s")) notFound();');
  });
});
