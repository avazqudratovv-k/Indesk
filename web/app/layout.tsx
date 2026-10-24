import type { Metadata } from "next";
import { getLocale } from "next-intl/server";
import { NextIntlClientProvider } from "next-intl";
import DevSessionSwitch from "@/components/layout/DevSessionSwitch";
import SessionProvider from "@/components/layout/SessionProvider";
import Shell from "@/components/layout/Shell";
import { getSession } from "@/lib/session-server";
import { themeInitScript } from "@/lib/theme";
import "../styles/globals.css";

export const metadata: Metadata = {
  title: "Indesk",
  description: "Answers from your files, with proof.",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  const session = await getSession();
  return (
    <html lang={locale} data-theme="light" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Onest:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&family=Noto+Sans+KR:wght@300;400;500;700&family=Noto+Sans+JP:wght@300;400;500;700&display=swap"
        />
      </head>
      <body>
        <NextIntlClientProvider>
          <SessionProvider session={session}>
            <Shell>{children}</Shell>
            <DevSessionSwitch />
          </SessionProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
