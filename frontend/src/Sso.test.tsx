import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
let App: typeof import("./main").App;
let api: typeof import("./api");
beforeAll(async () => {
  vi.resetModules();
  vi.stubEnv("VITE_DEMO_LOGIN", "false");
  api = await import("./api");
  App = (await import("./main")).App;
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  sessionStorage.clear();
  api.setCsrfToken("");
  window.history.replaceState({}, "", "/");
});
const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), { status });
describe("Microsoft browser authentication", () => {
  it("shows accessible SSO login without manual token entry", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (url) =>
      String(url).endsWith("/status")
        ? json({ configured: true })
        : json({ detail: "Sign in" }, 401),
    );
    render(<App />);
    expect(
      await screen.findByRole("button", { name: "Sign in" }),
    ).toBeEnabled();
    expect(screen.queryByLabelText("Access token")).not.toBeInTheDocument();
  });
  it("restores a cookie session and displays approved membership", async () => {
    window.history.replaceState({}, "", "/settings");
    vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
      if (String(url).endsWith("/status")) return json({ configured: true });
      if (String(url).endsWith("/me"))
        return json({
          user: "Authorized user",
          role: "Auditor",
          tenant: "approved-workspace",
          csrf_token: "synthetic-csrf",
        });
      return json({});
    });
    render(<App />);
    expect(
      await screen.findByText("Authorized user · Auditor · approved-workspace"),
    ).toBeInTheDocument();
    expect(window.location.pathname).toBe("/settings");
  });
  it("shows access denial without reflecting provider error details", async () => {
    window.history.replaceState({}, "", "/?auth_error=access_denied");
    vi.spyOn(globalThis, "fetch").mockImplementation(async (url) =>
      String(url).endsWith("/status")
        ? json({ configured: true })
        : json({ detail: "Sign in" }, 401),
    );
    render(<App />);
    expect(
      await screen.findByText(/Ask your workspace administrator/),
    ).toBeInTheDocument();
    expect(window.location.search).toBe("");
  });
  it("disables login when server configuration is incomplete", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (url) =>
      String(url).endsWith("/status")
        ? json({ configured: false })
        : json({ detail: "Sign in" }, 401),
    );
    render(<App />);
    expect(
      await screen.findByRole("button", { name: "Sign in" }),
    ).toBeDisabled();
  });
  it("sends cookies and CSRF with no browser bearer token", async () => {
    sessionStorage.setItem("governance-token", "must-not-be-sent");
    api.setCsrfToken("synthetic-csrf");
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(json({}));
    await api.request("/api/policies", "POST", { name: "synthetic" });
    const options = fetch.mock.calls[0][1]!;
    expect(options.credentials).toBe("include");
    expect(options.headers).toMatchObject({ "X-CSRF-Token": "synthetic-csrf" });
    expect(options.headers).not.toHaveProperty("Authorization");
  });
  it("returns expired sessions to sign-in", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
      if (String(url).endsWith("/status")) return json({ configured: true });
      if (String(url).endsWith("/me"))
        return json({
          user: "User",
          role: "Auditor",
          tenant: "one",
          csrf_token: "synthetic",
        });
      return json({});
    });
    window.history.replaceState({}, "", "/settings");
    render(<App />);
    await screen.findByText("User · Auditor · one");
    fireEvent(window, new Event("governance-session-ended"));
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Sign in" }),
      ).toBeInTheDocument(),
    );
    expect(
      screen.getByText("Your session has ended. Please sign in again."),
    ).toBeInTheDocument();
  });
  it("preserves the requested route in login initiation", () => {
    window.history.replaceState({}, "", "/policies/example");
    expect(api.loginUrl()).toContain("return_to=%2Fpolicies%2Fexample");
  });
});

describe("SSO-only interactive login", () => {
  it.each([true, false])(
    "never offers token login when configured=%s",
    async (configured) => {
      sessionStorage.setItem("governance-token", "obsolete-session");
      vi.spyOn(globalThis, "fetch").mockImplementation(async (url) =>
        String(url).endsWith("/status")
          ? json({ configured, demo_login_enabled: true })
          : json({ detail: "Sign in" }, 401),
      );
      render(<App />);
      const button = await screen.findByRole("button", {
        name: "Sign in",
      });
      if (configured) expect(button).toBeEnabled();
      else expect(button).toBeDisabled();
      expect(screen.queryByLabelText("Access token")).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Use demonstration access" }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /Connect workspace/ }),
      ).not.toBeInTheDocument();
      expect(sessionStorage.getItem("governance-token")).toBeNull();
    },
  );
});

describe("responsive fail-closed session bootstrap", () => {
  it("shows the login panel immediately but never loads workspace data before authentication", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(
      (_url, options) =>
        new Promise((_resolve, reject) => {
          options?.signal?.addEventListener(
            "abort",
            () => reject(new DOMException("Aborted", "AbortError")),
            { once: true },
          );
        }),
    );
    render(<App />);
    expect(
      screen.getByRole("heading", { name: "Welcome to Governance Studio" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Sign in" }),
    ).toBeDisabled();
    expect(
      screen.getByText("Checking sign-in…"),
    ).toBeInTheDocument();
    expect(fetch.mock.calls.map(([url]) => String(url))).toEqual([
      expect.stringContaining("/api/sso/status"),
      expect.stringContaining("/api/sso/me"),
    ]);
  });
  it("restores a verified session without waiting for public availability", async () => {
    window.history.replaceState({}, "", "/policies");
    const fetch = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (url, options) => {
        if (String(url).endsWith("/status"))
          return new Promise((_resolve, reject) => {
            options?.signal?.addEventListener(
              "abort",
              () => reject(new DOMException("Aborted", "AbortError")),
              { once: true },
            );
          });
        if (String(url).endsWith("/me"))
          return json({
            user: "Verified",
            role: "Admin",
            tenant: "one",
            csrf_token: "synthetic",
          });
        if (String(url).includes("/api/policies")) return json([]);
        return json({ provider_mode: "fixture" });
      });
    render(<App />);
    expect(
      await screen.findByText("Verified · Admin · one"),
    ).toBeInTheDocument();
    await screen.findByRole("heading", { name: "Policy management" });
    await waitFor(() =>
      expect(
        fetch.mock.calls.filter(([url]) =>
          String(url).endsWith("/api/settings"),
        ),
      ).toHaveLength(1),
    );
  });
  it("treats anonymous bootstrap denial as sign-in, not an expired-session alert", async () => {
    const ended = vi.fn();
    window.addEventListener("governance-session-ended", ended);
    vi.spyOn(globalThis, "fetch").mockImplementation(async (url) =>
      String(url).endsWith("/status")
        ? json({ configured: true })
        : json({ detail: "Sign in" }, 401),
    );
    try {
      render(<App />);
      await waitFor(() =>
        expect(
          screen.getByRole("button", { name: "Sign in" }),
        ).toBeEnabled(),
      );
      expect(ended).not.toHaveBeenCalled();
      expect(
        screen.queryByText("Your session has ended. Please sign in again."),
      ).not.toBeInTheDocument();
    } finally {
      window.removeEventListener("governance-session-ended", ended);
    }
  });
  it("bounds stalled restoration and permits an explicit retry without automatic retries", async () => {
    vi.useFakeTimers();
    let retry = false;
    const fetch = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (url, options) => {
        if (String(url).endsWith("/status")) return json({ configured: true });
        if (String(url).endsWith("/me")) {
          if (retry) return json({ detail: "Sign in" }, 401);
          return new Promise((_resolve, reject) =>
            options?.signal?.addEventListener(
              "abort",
              () => reject(new DOMException("Aborted", "AbortError")),
              { once: true },
            ),
          );
        }
        return json({});
      });
    try {
      render(<App />);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(10001);
      });
      expect(
        screen.getByText(/Your session could not be checked/),
      ).toBeInTheDocument();
      expect(
        fetch.mock.calls.filter(([url]) => String(url).endsWith("/me")),
      ).toHaveLength(1);
      retry = true;
      await act(async () => {
        fireEvent.click(
          screen.getByRole("button", { name: "Retry connection" }),
        );
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(
        screen.getByRole("button", { name: "Sign in" }),
      ).toBeEnabled();
      expect(
        fetch.mock.calls.filter(([url]) => String(url).endsWith("/me")),
      ).toHaveLength(2);
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("precise session ending and simplified login", () => {
  function mockIdentity() {
    window.history.replaceState({}, "", "/settings");
    return vi.spyOn(globalThis, "fetch").mockImplementation(async url => {
      if (String(url).endsWith("/status")) return json({ configured: true });
      if (String(url).endsWith("/me")) return json({ user: "Verified", role: "Auditor", tenant: "one", csrf_token: "synthetic", expires_at: "2035-01-02T14:30:00+00:00", server_now: "2035-01-02T12:30:00+00:00" });
      if (String(url).endsWith("/logout")) return json({ logout_url: window.location.href + "#signed-out" });
      return json({ role: "Auditor", provider_mode: "fixture" });
    });
  }

  it.each(["expired", "ended"])("shows only the server-confirmed %s reason after restore", async reason => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async url => String(url).endsWith("/status") ? json({ configured: true }) : new Response(JSON.stringify({ detail: "Sign in" }), { status: 401, headers: { "X-Session-Reason": reason } }));
    render(<App />);
    await screen.findByText(reason === "expired" ? "Your session has expired. Please sign in again." : "Your session has ended. Please sign in again.");
    const button = screen.getByRole("button", { name: "Sign in" });
    expect(button.textContent?.trim()).toBe("Sign in");
    expect(button.querySelector("svg, img")).toBeNull();
  });

  it("keeps first/anonymous visits clean even if an unrelated 401 event arrives", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async url => String(url).endsWith("/status") ? json({ configured: true }) : json({ detail: "Sign in" }, 401));
    render(<App />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled());
    fireEvent(window, new CustomEvent("governance-session-ended", { detail: { reason: "anonymous" } }));
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByText(/120|countdown|session expires/i)).toBeNull();
  });

  it.each(["expired", "ended"])("handles a protected API %s response without exposing server details", async reason => {
    const fetch = mockIdentity();
    render(<App />);
    await screen.findByText("Verified · Auditor · one");
    fetch.mockImplementation(async () => new Response(JSON.stringify({ detail: "Sign in" }), { status: 401, headers: { "X-Session-Reason": reason } }));
    await act(async () => { await api.request("/api/settings").catch(() => {}); });
    await screen.findByText(reason === "expired" ? "Your session has expired. Please sign in again." : "Your session has ended. Please sign in again.");
  });

  it("manual logout returns to clean login and ignores subsequent stale session events", async () => {
    mockIdentity();
    render(<App />);
    fireEvent.click(await screen.findByTitle("Sign out"));
    await waitFor(() => expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled());
    fireEvent(window, new CustomEvent("governance-session-ended", { detail: { reason: "ended" } }));
    expect(screen.queryByText("Your session has ended. Please sign in again.")).toBeNull();
    expect(screen.queryByText("Your session has expired. Please sign in again.")).toBeNull();
  });
});
