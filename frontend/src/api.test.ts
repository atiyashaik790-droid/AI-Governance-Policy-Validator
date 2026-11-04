import { afterEach, describe, expect, it, vi } from "vitest";
import { request } from "./api";

afterEach(() => {
  vi.restoreAllMocks();
  sessionStorage.clear();
});
describe("reliable API transport", () => {
  it("handles HTML proxy errors safely", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("<html>private upstream failure</html>", { status: 502 }),
    );
    await expect(request("/api/settings")).rejects.toThrow(
      "unreadable response (502)",
    );
  });
  it("reports validation locations", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: [{ loc: ["body", "rating"], type: "int_type" }],
        }),
        { status: 422 },
      ),
    );
    await expect(request("/api/feedback", "POST", {})).rejects.toThrow(
      "body.rating: int_type",
    );
  });
  it("clears revoked sessions and dispatches sign-in event", async () => {
    sessionStorage.setItem("governance-token", "synthetic");
    const listener = vi.fn();
    window.addEventListener("governance-session-ended", listener);
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Session expired" }), {
        status: 401,
      }),
    );
    try {
      await expect(request("/api/settings")).rejects.toThrow("Session expired");
      expect(listener).toHaveBeenCalledOnce();
      expect(sessionStorage.getItem("governance-token")).toBeNull();
    } finally {
      window.removeEventListener("governance-session-ended", listener);
    }
  });
  it("times out mutations without retrying", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(
      (_url, options) =>
        new Promise((_resolve, reject) => {
          options?.signal?.addEventListener("abort", () =>
            reject(new DOMException("Aborted", "AbortError")),
          );
        }),
    );
    await expect(
      request(
        "/api/governance/generate",
        "POST",
        { text: "safe" },
        { timeoutMs: 5 },
      ),
    ).rejects.toThrow("timed out");
    expect(fetch).toHaveBeenCalledOnce();
  });
  it("accepts caller cancellation", async () => {
    const controller = new AbortController();
    vi.spyOn(globalThis, "fetch").mockImplementation(
      (_url, options) =>
        new Promise((_resolve, reject) => {
          options?.signal?.addEventListener("abort", () =>
            reject(new DOMException("Aborted", "AbortError")),
          );
        }),
    );
    const pending = request("/api/settings", "GET", undefined, {
      signal: controller.signal,
    });
    controller.abort();
    await expect(pending).rejects.toThrow("cancelled");
  });
  it("handles a network outage without retry", async () => {
    const fetch = vi
      .spyOn(globalThis, "fetch")
      .mockRejectedValue(new TypeError("synthetic"));
    await expect(request("/api/policies", "POST", {})).rejects.toThrow(
      "Network unavailable",
    );
    expect(fetch).toHaveBeenCalledOnce();
  });
});
