import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

const nextConfig: NextConfig = {
  // A stray package-lock.json exists in the home folder; pin the root to this app.
  turbopack: { root: import.meta.dirname },
};

export default withNextIntl(nextConfig);
