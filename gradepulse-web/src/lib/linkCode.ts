/**
 * Invite and password-reset links carry a one-time code after "#"
 * (/signup#invite=CODE, /reset-password#code=CODE). Older links used the
 * query string, so both are read. The code is then removed from the address
 * bar, so it does not stay in the browser history or get copied on.
 */
export function takeLinkCode(name: string): string {
  if (typeof window === "undefined") return "";
  const url = new URL(window.location.href);
  const fromHash = new URLSearchParams(url.hash.replace(/^#/, "")).get(name);
  const fromQuery = url.searchParams.get(name);
  const code = (fromHash ?? fromQuery ?? "").trim();
  if (fromHash !== null || fromQuery !== null) {
    url.searchParams.delete(name);
    window.history.replaceState(window.history.state, "", url.pathname + url.search);
  }
  return code;
}
