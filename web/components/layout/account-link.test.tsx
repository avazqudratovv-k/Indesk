import { renderToStaticMarkup } from "react-dom/server";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it, vi } from "vitest";
import en from "@/messages/en.json";
import ko from "@/messages/ko.json";
import AccountLink from "./AccountLink";

const path = vi.hoisted(() => ({ current: "/workspace" }));
vi.mock("next/navigation", () => ({ usePathname: () => path.current }));

function render(locale: "en" | "ko", name: string) {
  return renderToStaticMarkup(
    <NextIntlClientProvider locale={locale} messages={locale === "en" ? en : ko}>
      <AccountLink name={name} />
    </NextIntlClientProvider>,
  );
}

describe("the navbar name link", () => {
  it("links to /my with the name as text and an accessible name that says it opens My page", () => {
    path.current = "/workspace";
    const html = render("en", "Kim");
    expect(html).toContain('href="/my"');
    expect(html).toContain(">Kim<");
    expect(html).toContain('aria-label="Kim, opens My page"');
    expect(html).not.toContain("aria-current");
  });

  it("reads in Korean", () => {
    path.current = "/workspace";
    expect(render("ko", "김민수")).toContain('aria-label="김민수, 내 페이지 열기"');
  });

  it("is the current page on /my and nowhere else, including report pages", () => {
    path.current = "/my";
    expect(render("en", "Kim")).toContain('aria-current="page"');
    path.current = "/reports/abc";
    expect(render("en", "Kim")).not.toContain("aria-current");
  });
});
