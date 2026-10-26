import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { isBuilt, navItems, visibleNavItems, type NavItem } from "./nav-items";

const keys = (items: NavItem[]) => items.map((item) => item.key);

describe("nav items", () => {
  it("hides People and My reports until they are built, signed in or not", () => {
    expect(keys(visibleNavItems(true))).toEqual(["home", "workspace", "plans"]);
    expect(keys(visibleNavItems(false))).toEqual(["home", "workspace", "plans"]);
  });

  it("un-hiding is the flag alone", () => {
    const on = navItems.map((item) => ({ ...item, built: true }));
    expect(keys(visibleNavItems(true, on))).toEqual(["home", "workspace", "people", "myReports", "plans"]);
    expect(keys(visibleNavItems(false, on))).toEqual(["home", "workspace", "plans"]);
  });

  it("marks /people and /my as not built, everything else as built", () => {
    expect(isBuilt("/people")).toBe(false);
    expect(isBuilt("/my")).toBe(false);
    for (const href of ["/", "/workspace", "/plans"]) expect(isBuilt(href)).toBe(true);
  });
});

describe("the mobile tab bar and the unbuilt pages", () => {
  const read = (file: string) => readFileSync(join(__dirname, file), "utf8");

  it("takes its tabs from the same flags", () => {
    expect(read("TabBar.tsx")).toContain("visibleNavItems(");
  });

  it("makes /people and /my answer 404 while their flag is off", () => {
    expect(read("../../app/people/page.tsx")).toContain('if (!isBuilt("/people")) notFound();');
    expect(read("../../app/my/page.tsx")).toContain('if (!isBuilt("/my")) notFound();');
  });
});
