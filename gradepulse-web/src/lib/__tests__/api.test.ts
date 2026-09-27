// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, UNAUTHORIZED_EVENT } from "../api";

const originalFetch = globalThis.fetch;

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

describe("api client", () => {
  beforeEach(() => {
    localStorage.clear();
    api.setToken(null);
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("sends the bearer token from storage on authenticated requests", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([]));
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    api.setToken("token-123");

    await api.getStudents("SCH-1", "CLASS-1");

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/students?school_id=SCH-1&class_id=CLASS-1");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer token-123");
  });

  it("serializes request bodies as JSON", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ processed: 1 }));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    await api.bulkUpdate([{ student_id: "S1", subject: "MATH", score: 0.8 }]);

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
    expect(JSON.parse(init.body as string)).toEqual({
      entries: [{ student_id: "S1", subject: "MATH", score: 0.8 }],
    });
  });

  it("broadcasts an unauthorized event and surfaces the API detail on 401", async () => {
    globalThis.fetch = vi
      .fn()
      .mockResolvedValue(jsonResponse({ detail: "Invalid credentials" }, { status: 401 })) as unknown as typeof fetch;
    const listener = vi.fn();
    window.addEventListener(UNAUTHORIZED_EVENT, listener);

    await expect(api.me()).rejects.toThrow("Invalid credentials");
    expect(listener).toHaveBeenCalledTimes(1);

    window.removeEventListener(UNAUTHORIZED_EVENT, listener);
  });

  it("falls back to a status message when the error body is not JSON", async () => {
    globalThis.fetch = vi
      .fn()
      .mockResolvedValue(
        new Response("<html>gateway</html>", { status: 502, statusText: "Bad Gateway" })
      ) as unknown as typeof fetch;

    await expect(api.health()).rejects.toThrow("Bad Gateway");
  });

  it("aborts and reports a timeout message when the request exceeds the limit", async () => {
    vi.useFakeTimers();
    globalThis.fetch = vi.fn().mockImplementation(
      (_url: string, init?: RequestInit) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () =>
            reject(new DOMException("Aborted", "AbortError"))
          );
        })
    ) as unknown as typeof fetch;

    const pending = api.summary();
    const assertion = expect(pending).rejects.toThrow(/timed out/i);
    await vi.advanceTimersByTimeAsync(15_001);
    await assertion;
  });

  it("propagates caller-driven aborts without converting them into timeouts", async () => {
    globalThis.fetch = vi.fn().mockImplementation(
      (_url: string, init?: RequestInit) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () =>
            reject(new DOMException("Aborted", "AbortError"))
          );
        })
    ) as unknown as typeof fetch;

    const controller = new AbortController();
    const pending = api.summary(controller.signal);
    controller.abort();

    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
  });

  it("sends top_n and returns the array the backend sends", async () => {
    const many = [
      { content_id: "C1", title: "A", topic: "MATH", difficulty: 1, content_type: "video" },
      { content_id: "C2", title: "B", topic: "MATH", difficulty: 3, content_type: "quiz" },
    ];
    globalThis.fetch = vi
      .fn()
      .mockResolvedValue(jsonResponse(many)) as unknown as typeof fetch;

    const result = await api.recommend("S001", 2);

    expect(result).toHaveLength(2);
    expect(result.map((r) => r.content_id)).toEqual(["C1", "C2"]);
    const body = JSON.parse(
      (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][1].body
    );
    expect(body).toMatchObject({ student_id: "S001", top_n: 2 });
  });

  it("returns an empty list when the engine has nothing to recommend", async () => {
    globalThis.fetch = vi
      .fn()
      .mockResolvedValue(jsonResponse([])) as unknown as typeof fetch;

    expect(await api.recommend("S001", 3)).toEqual([]);
  });

  it("clears the stored token on logout", () => {
    api.setToken("token-123");
    expect(localStorage.getItem("gradepulse_token")).toBe("token-123");

    api.logout();

    expect(localStorage.getItem("gradepulse_token")).toBeNull();
    expect(api.getToken()).toBeNull();
  });
});
