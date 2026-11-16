// @vitest-environment happy-dom
import { afterEach, describe, expect, it } from "vitest";
import { takeLinkCode } from "../linkCode";

describe("takeLinkCode", () => {
  afterEach(() => window.history.replaceState(null, "", "/"));

  it("reads the code after # and clears it from the address bar", () => {
    window.history.replaceState(null, "", "/signup#invite=AbC_123-x");
    expect(takeLinkCode("invite")).toBe("AbC_123-x");
    expect(window.location.hash).toBe("");
    expect(window.location.pathname).toBe("/signup");
  });

  it("still reads older links with the code in the query", () => {
    window.history.replaceState(null, "", "/reset-password?code=OLD123&x=1");
    expect(takeLinkCode("code")).toBe("OLD123");
    expect(window.location.search).toBe("?x=1");
  });

  it("returns nothing and leaves the address alone without a code", () => {
    window.history.replaceState(null, "", "/signup?plan=free");
    expect(takeLinkCode("invite")).toBe("");
    expect(window.location.search).toBe("?plan=free");
  });
});
