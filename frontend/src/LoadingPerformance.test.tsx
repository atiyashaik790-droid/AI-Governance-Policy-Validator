import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./main";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.useRealTimers();
  window.history.replaceState({}, "", "/");
});
it("records the bootstrap waterfall under identical deterministic delays", async () => {
  vi.useFakeTimers();
  window.history.replaceState({}, "", "/settings");
  const started = Date.now();
  const calls: { path: string; at: number }[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
    const path = String(url);
    calls.push({ path, at: Date.now() - started });
    if (path.endsWith("/api/sso/status")) {
      await new Promise((resolve) => setTimeout(resolve, 80));
      return new Response(JSON.stringify({ configured: true }));
    }
    if (path.endsWith("/api/sso/me")) {
      await new Promise((resolve) => setTimeout(resolve, 120));
      return new Response(
        JSON.stringify({
          user: "profile-user",
          role: "Auditor",
          tenant: "synthetic",
          csrf_token: "synthetic",
        }),
      );
    }
    return new Response(JSON.stringify({}));
  });
  render(<App />);
  const immediateLoginPanel = Boolean(
    screen.queryByRole("heading", { name: "Welcome to Governance Studio" }),
  );
  expect(immediateLoginPanel).toBe(true);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(80);
  });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(40);
  });
  const restoredAt120 = Boolean(
    screen.queryByText("profile-user · Auditor · synthetic"),
  );
  expect(restoredAt120).toBe(true);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(80);
  });
  expect(
    screen.getByText("profile-user · Auditor · synthetic"),
  ).toBeInTheDocument();
});
