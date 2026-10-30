// One list drives the desktop links; the mobile tab bar picks its own subset (DECISIONS #62).
export type NavKey = "home" | "workspace" | "people" | "myReports" | "plans";

// `built: false` hides the link (nav and tab bar) and makes the page answer 404 until the page exists (P11 B1).
// To bring a page back, flip its flag to true.
export type NavItem = { key: NavKey; href: string; signedInOnly: boolean; built: boolean };

export const navItems: NavItem[] = [
  { key: "home", href: "/", signedInOnly: false, built: true },
  { key: "workspace", href: "/workspace", signedInOnly: false, built: true },
  { key: "people", href: "/people", signedInOnly: true, built: false },
  { key: "myReports", href: "/my", signedInOnly: true, built: false },
  { key: "plans", href: "/plans", signedInOnly: false, built: true },
];

// The desktop links a visitor sees: built pages only, and signed-in pages only when signed in.
export function visibleNavItems(signedIn: boolean, items: NavItem[] = navItems): NavItem[] {
  return items.filter((item) => item.built && (signedIn || !item.signedInOnly));
}

// Pages that have no nav link but are not built either (the shared report view, ROADMAP later).
const hiddenPages = ["/s"];

// A page that is not built answers 404 (used by app/people, app/my and app/s).
export function isBuilt(href: string, items: NavItem[] = navItems): boolean {
  if (hiddenPages.includes(href)) return false;
  return items.find((item) => item.href === href)?.built ?? true;
}

export function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  if (href === "/my") return pathname === "/my" || pathname.startsWith("/my/") || pathname.startsWith("/reports/");
  return pathname === href || pathname.startsWith(`${href}/`);
}
