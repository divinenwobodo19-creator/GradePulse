import { NextResponse, type NextRequest } from "next/server";
import { contentSecurityPolicy } from "@/lib/csp";

// A fresh nonce for every page request. Next.js reads the policy from the
// request headers and puts the nonce on the inline scripts it renders.
export function proxy(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const policy = contentSecurityPolicy(nonce, process.env.NODE_ENV === "development");
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", policy);
  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", policy);
  return response;
}

export const config = {
  matcher: [
    {
      // Pages only: not the API proxy, build files, or prefetches.
      source: "/((?!api|_next/static|_next/image|favicon.ico|media|screens).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
