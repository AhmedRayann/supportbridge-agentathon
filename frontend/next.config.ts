import type { NextConfig } from "next";

// Read only on the server. No provider settings belong in this configuration.
const backendUrl = process.env.BACKEND_URL ??
  (process.env.NODE_ENV === "development" ? "http://127.0.0.1:8000" : undefined);

if (backendUrl) {
  const url = new URL(backendUrl);
  if (
    !["http:", "https:"].includes(url.protocol) ||
    url.username || url.password || url.search || url.hash || url.pathname !== "/"
  ) {
    throw new Error("BACKEND_URL must be an HTTP(S) origin without credentials or a path.");
  }
}

const nextConfig: NextConfig = {
  async rewrites() {
    // Services routes production requests directly to Python. This proxy is for
    // local development and the documented two-project Vercel fallback.
    return backendUrl ? [{
      source: "/svc/api/:path*",
      destination: `${backendUrl.replace(/\/$/, "")}/svc/api/:path*`,
    }] : [];
  },
};

export default nextConfig;
