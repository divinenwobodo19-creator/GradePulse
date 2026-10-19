import { describe, expect, it } from "vitest";
import robots from "../robots";
import sitemap from "../sitemap";

describe("search engine files", () => {
  it("keeps the signed-in app out of search engines and points to the sitemap", () => {
    const rules = robots().rules as { allow: string; disallow: string[] };
    expect(rules.allow).toBe("/");
    for (const page of ["/dashboard", "/students", "/reports", "/billing", "/api/"]) {
      expect(rules.disallow).toContain(page);
    }
    expect(robots().sitemap).toBe("https://gradepulse.com.ng/sitemap.xml");
  });

  it("lists the public pages on the live domain", () => {
    const urls = sitemap().map((entry) => entry.url);
    expect(urls).toContain("https://gradepulse.com.ng/");
    expect(urls).toContain("https://gradepulse.com.ng/waec-grade-calculator");
    expect(urls.every((u) => !u.includes("/dashboard"))).toBe(true);
  });
});
