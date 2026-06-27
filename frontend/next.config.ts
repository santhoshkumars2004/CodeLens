import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // "standalone" mode outputs a minimal production build that can be
  // run with `node server.js` without needing the full node_modules folder.
  // This is what the Dockerfile uses to keep the image small.
  output: "standalone",

  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
