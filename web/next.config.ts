import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // A stray package-lock.json exists in the home folder; pin the root to this app.
  turbopack: { root: import.meta.dirname },
};

export default nextConfig;
