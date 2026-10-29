import type { NextConfig } from "next";

const engine = process.env.ENGINE_URL || "http://127.0.0.1:8741";

const nextConfig: NextConfig = {
  // The dev server binds 0.0.0.0, so a browser on 127.0.0.1 is a different
  // host. Next blocks that host from dev assets, which stops hydration.
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  async rewrites() {
    return [
      {
        source: "/engine/:path*",
        destination: `${engine}/:path*`,
      },
    ];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
