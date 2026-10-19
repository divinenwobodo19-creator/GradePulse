import type { MetadataRoute } from "next";

const SITE = "https://gradepulse.com.ng";

export default function sitemap(): MetadataRoute.Sitemap {
  const page = (path: string, priority: number, changeFrequency: "weekly" | "monthly" | "yearly") => ({
    url: `${SITE}${path}`, lastModified: new Date("2026-10-19"), changeFrequency, priority,
  });
  return [
    page("/", 1, "weekly"),
    page("/pricing", 0.8, "monthly"),
    page("/waec-grade-calculator", 0.8, "monthly"),
    page("/guides/spot-struggling-students", 0.6, "yearly"),
    page("/signup", 0.5, "yearly"),
    page("/privacy", 0.3, "yearly"),
  ];
}
