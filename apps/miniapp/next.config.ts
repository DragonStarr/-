import type { NextConfig } from "next";

const backend = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8020";

const nextConfig: NextConfig = {
  devIndicators: false,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backend}/api/:path*`
      },
      {
        source: "/health",
        destination: `${backend}/health`
      },
      {
        source: "/metrics",
        destination: `${backend}/metrics`
      }
    ];
  }
};

export default nextConfig;
