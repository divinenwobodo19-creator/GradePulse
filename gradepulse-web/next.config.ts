import type { NextConfig } from "next";

const apiProxyTarget = (process.env.API_URL || "http://localhost:8000").replace(
  /\/+$/,
  ""
);
// The Content-Security-Policy is set per request, with a nonce, in
// src/proxy.ts (src/lib/csp.ts).

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

const OPERATOR_PATHS = [
  "/api/backup",
  "/api/backup/:path*",
  "/api/backups",
  "/api/backups/:path*",
  "/api/save",
  "/api/content",
  "/api/billing/pilot",
  "/api/auth/operator-reset",
];

const nextConfig: NextConfig = {
  poweredByHeader: false,
  reactStrictMode: true,  async headers() {
    return [
      // Photos, screenshots and the demo video change only with a new file name,
      // so Cloudflare can keep them for a day and browsers for an hour.
      {
        source: "/:dir(media|screens)/:file*",
        headers: [{ key: "Cache-Control", value: "public, max-age=3600, s-maxage=86400" }],
      },
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
        ],
      },
    ];
  },
  async rewrites() {
    return [
      // Operator tools (backups, restore, pilot terms, admin resets, the
      // shared content catalogue) are used on the server itself, against the
      // API's local port. The public /api path never forwards them, so a
      // leaked operator key alone cannot reach them from the internet.
      ...OPERATOR_PATHS.map((source) => ({ source, destination: "/operator-only" })),
      {
        source: "/api/:path*",
        destination: `${apiProxyTarget}/:path*`,
      },
    ];
  },
};

export default nextConfig;
