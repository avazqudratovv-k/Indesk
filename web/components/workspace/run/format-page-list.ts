// "1 and 2", "1, 2 and 3" in the active language. English uses the British list style (no comma before "and").
export function formatPageList(pages: number[], locale: string): string {
  if (pages.length === 0) return "";
  const tag = locale === "en" ? "en-GB" : locale;
  return new Intl.ListFormat(tag, { style: "long", type: "conjunction" }).format(pages.map(String));
}
