// One list drives the desktop links; the mobile tab bar picks its own subset (DECISIONS #62).
export type NavKey = "home" | "workspace" | "people" | "myReports" | "plans";

export type NavItem = { key: NavKey; href: string; signedInOnly: boolean };

export const navItems: NavItem[] = [
  { key: "home", href: "/", signedInOnly: false },
  { key: "workspace", href: "/workspace", signedInOnly: false },
  { key: "people", href: "/people", signedInOnly: true },
  { key: "myReports", href: "/my", signedInOnly: true },
  { key: "plans", href: "/plans", signedInOnly: false },
];

export function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  if (href === "/my") return pathname === "/my" || pathname.startsWith("/my/") || pathname.startsWith("/reports/");
  return pathname === href || pathname.startsWith(`${href}/`);
}
