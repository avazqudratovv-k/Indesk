import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

// The browser only talks to its own origin. In development the dev server forwards /api to the backend.
// In production this same rewrite does it: the browser only talks to the web container, which forwards /api to the
// api container. The rewrite target is fixed at BUILD time, so API_INTERNAL_URL must be set when `next build` runs
// (web/Dockerfile passes it as a build argument).
const apiTarget = process.env.API_INTERNAL_URL ?? (process.env.NODE_ENV === "production" ? undefined : "http://127.0.0.1:8000");

const nextConfig: NextConfig = {
  // Next compresses responses (gzip) when the browser allows it, and that includes what its /api rewrite proxies:
  // the run event stream then arrives in big chunks instead of line by line (4.1 finding, measured by
  // scripts/check-sse-proxy.mjs). Compression of pages is nginx's job in production (deploy checklist).
  compress: false,
  // The production image runs the self-contained server that `next build` writes to .next/standalone.
  output: "standalone",
  // A stray package-lock.json exists in the home folder; pin the root to this app (also keeps server.js at the top
  // of .next/standalone instead of nested under the folder path).
  turbopack: { root: import.meta.dirname },
  outputFileTracingRoot: import.meta.dirname,
  // The rewrite proxy gives up on an upstream that is silent for 30 s by default. The run stream pings every 15 s and
  // lasts up to sse_max_seconds (330 s), so allow a little more than that.
  experimental: { proxyTimeout: 360_000 },
  async rewrites() {
    return apiTarget ? [{ source: "/api/:path*", destination: `${apiTarget}/api/:path*` }] : [];
  },
};

export default withNextIntl(nextConfig);
