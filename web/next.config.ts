import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

// The browser only talks to its own origin. In development the dev server forwards /api to the backend.
// In production nginx routes /api to the API; set API_INTERNAL_URL at build time only if Next should do it instead.
const apiTarget = process.env.API_INTERNAL_URL ?? (process.env.NODE_ENV === "production" ? undefined : "http://127.0.0.1:8000");

const nextConfig: NextConfig = {
  // Next compresses responses (gzip) when the browser allows it, and that includes what its /api rewrite proxies:
  // the run event stream then arrives in big chunks instead of line by line (4.1 finding, measured by
  // scripts/check-sse-proxy.mjs). Compression of pages is nginx's job in production (deploy checklist).
  compress: false,
  // A stray package-lock.json exists in the home folder; pin the root to this app.
  turbopack: { root: import.meta.dirname },
  async rewrites() {
    return apiTarget ? [{ source: "/api/:path*", destination: `${apiTarget}/api/:path*` }] : [];
  },
};

export default withNextIntl(nextConfig);
