// Content Security Policy for every page, built per request by src/proxy.ts.
//
// Scripts run only from this site, from Cloudflare's analytics beacon (which
// Cloudflare adds to every page it serves), or inline with this request's
// nonce, which Next.js puts on its own inline scripts. An injected
// <script> has no nonce, so the browser refuses it ('unsafe-inline' is
// gone). Styles keep 'unsafe-inline': React style attributes need it.
const CLOUDFLARE_ANALYTICS_SCRIPT = "https://static.cloudflareinsights.com";
const CLOUDFLARE_ANALYTICS_REPORT = "https://cloudflareinsights.com";

export function contentSecurityPolicy(nonce: string, isDev: boolean): string {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL?.trim();
  const connect = ["'self'", CLOUDFLARE_ANALYTICS_REPORT, ...(apiUrl ? [apiUrl] : [])];
  const scripts = ["'self'", `'nonce-${nonce}'`, CLOUDFLARE_ANALYTICS_SCRIPT, ...(isDev ? ["'unsafe-eval'"] : [])];
  return [
    "default-src 'self'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "object-src 'none'",
    `connect-src ${connect.join(" ")}`,
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    "style-src 'self' 'unsafe-inline'",
    `script-src ${scripts.join(" ")}`,
  ].join("; ");
}
