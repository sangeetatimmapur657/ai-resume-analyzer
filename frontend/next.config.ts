import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Keep deployment traces inside this app when unrelated lockfiles exist above it.
  outputFileTracingRoot: __dirname,
};

export default nextConfig;
