import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    const isVercelProduction = process.env.VERCEL === '1';
    if (isVercelProduction) {
      return [];
    }

    return [
      {
        // match all API routes and forward them to the FastAPI backend
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  }
};

export default nextConfig;
