import type { MetadataRoute } from "next";

// The signed-in app is private: search engines get the public pages only.
const APP_PAGES = [
  "/dashboard", "/students", "/classes", "/scores", "/triage", "/progress",
  "/reports", "/billing", "/settings", "/login", "/reset-password", "/api/",
];

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/", disallow: APP_PAGES },
    sitemap: "https://gradepulse.com.ng/sitemap.xml",
  };
}
