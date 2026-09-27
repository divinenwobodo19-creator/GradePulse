import type { NextConfig } from "next";

const apiProxyTarget = (process.env.API_URL || "http://localhost:8000").replace(
  /\/+$/,
  ""
);
const configuredApiUrl = process.env.NEXT_PUBLIC_API_URL?.trim();
const connectSources = ["'self'", ...(configuredApiUrl ? [configuredApiUrl] : [])];
const scriptSources = [
  "'self'",
  "'unsafe-inline'",
  ...(process.env.NODE_ENV === "development" ? ["'unsafe-eval'"] : []),
];
const contentSecurityPolicy = [
  "default-src 'self'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  "object-src 'none'",
  `connect-src ${connectSources.join(" ")}`,
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `style-src 'self' 'unsafe-inline'`,
  `script-src ${scriptSources.join(" ")}`,
].join("; ");

// Dev-only: warns if API_URL resolves to the demo mock, which also serves /health.
if (process.env.NODE_ENV === "development" && !process.env.SKIP_API_ENGINE_CHECK) {
  void fetch(`${apiProxyTarget}/health`)
    .then((response) => response.json() as Promise<{ engine?: string }>)
    .then((body) => {
      if (body?.engine && body.engine !== "GradePulse") {
        console.warn(
          [
            "",
            `[gradepulse] API_URL=${apiProxyTarget} reports engine="${body.engine}", not "GradePulse".`,
            "           The frontend is proxying to the demo mock, so everything you see is fake.",
            "           The real backend's canonical port is 8000. Start it there, or point",
            "           API_URL at wherever you are running it.",
            "",
          ].join("\n")
        );
      }
    })
    .catch(() => {
      console.warn(
        `[gradepulse] Could not reach ${apiProxyTarget}/health. Start the backend or set API_URL.`
      );
    });
}

const nextConfig: NextConfig = {
  poweredByHeader: false,
  reactStrictMode: true,  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
          {
            key: "Strict-Transport-Security",
            value: "max-age=31536000; includeSubDomains",
          },
          { key: "Content-Security-Policy", value: contentSecurityPolicy },
        ],
      },
    ];
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiProxyTarget}/:path*`,
      },
    ];
  },
};

export default nextConfig;
