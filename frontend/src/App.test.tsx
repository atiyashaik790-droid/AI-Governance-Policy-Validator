import { afterEach, describe, it, expect, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { App } from "./main";
import { request } from "./api";
// Reset session state and mocks between frontend integration tests.
afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.restoreAllMocks();
});
describe("real API boundary", () => {
  // Attach the token to network requests without trusting any browser role.
  it("sends authenticated request bodies", async () => {
    sessionStorage.setItem("governance-token", "test-token");
    const fetch = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ decision: "ALLOW" })));
    await request("/api/governance/generate", "POST", { text: "safe" });
    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/governance/generate",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer test-token",
        }),
        body: '{"text":"safe"}',
      }),
    );
  });
  // Render server authorization failures as meaningful errors.
  it("propagates backend rejection", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      async () =>
        new Response(
          JSON.stringify({ detail: "Role does not permit this operation" }),
          { status: 403 },
        ),
    );
    await expect(request("/api/policies")).rejects.toThrow(
      "Role does not permit",
    );
  });
  // A user enters a credential; the backend must validate it before navigation.
  it("requires successful backend authentication", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      async () =>
        new Response(JSON.stringify({ detail: "Invalid token" }), {
          status: 401,
        }),
    );
    render(<App />);
    fireEvent.change(screen.getByLabelText("Access token"), {
      target: { value: "invalid" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Connect workspace/ }));
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("Invalid token"),
    );
    expect(sessionStorage.getItem("governance-token")).toBeNull();
  });
});

describe("governed playground integration", () => {
  // Drive the rendered form through an actual API client boundary and show approved content.
  it("displays an inspected response with the fixture label", async () => {
    sessionStorage.setItem("governance-token", "test-token");
    window.history.pushState({}, "", "/playground");
    const stage = {
      decision: "ALLOW",
      score: 100,
      breakdown: {
        secret_detection: "SATISFIED",
        pii_detection: "SATISFIED",
        moderation: "SATISFIED",
        blocked_keywords: "SATISFIED",
      },
      contributions: {
        secret_detection: 30,
        pii_detection: 25,
        moderation: 25,
        blocked_keywords: 20,
      },
      findings: [],
      safe_text: "Safe answer",
      revalidated: false,
    };
    vi.spyOn(globalThis, "fetch").mockImplementation(
      async () =>
        new Response(
          JSON.stringify({
            input: stage,
            output: stage,
            decision: "ALLOW",
            safe_response: "Governance makes information useful.",
            model_invoked: true,
            provider_mode: "fixture",
            policy_id: "policy-1234",
            policy_version: 1,
            duration_ms: 12,
            request_id: "request-1234",
          }),
        ),
    );
    render(<App />);
    fireEvent.click(
      screen.getByRole("button", { name: /Run governed request/ }),
    );
    await waitFor(() =>
      expect(
        screen.getByText("Governance makes information useful."),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText("LOCAL TEST FIXTURE")).toBeInTheDocument();
    expect(screen.getByText("Final decision: ALLOW")).toBeInTheDocument();
    window.history.pushState({}, "", "/");
  });
  // Output rejection must show withholding instead of any model content.
  it("withholds rejected output", async () => {
    sessionStorage.setItem("governance-token", "test-token");
    window.history.pushState({}, "", "/playground");
    const stage = {
      decision: "BLOCK",
      score: 70,
      breakdown: { secret_detection: "FAILED" },
      contributions: { secret_detection: 0 },
      findings: [{ category: "secret_detection", count: 1 }],
      safe_text: null,
      revalidated: false,
    };
    vi.spyOn(globalThis, "fetch").mockImplementation(
      async () =>
        new Response(
          JSON.stringify({
            input: { ...stage, decision: "ALLOW" },
            output: stage,
            decision: "BLOCK",
            safe_response: null,
            model_invoked: true,
            provider_mode: "fixture",
            policy_id: "policy-1234",
            policy_version: 1,
            duration_ms: 12,
            request_id: "request-1234",
          }),
        ),
    );
    render(<App />);
    fireEvent.click(
      screen.getByRole("button", { name: /Run governed request/ }),
    );
    await waitFor(() =>
      expect(
        screen.getByText(
          "Response withheld. No unvalidated model content was released.",
        ),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText("Final decision: BLOCK")).toBeInTheDocument();
    window.history.pushState({}, "", "/");
  });
});

describe("same-origin deployment API", () => {
  it("uses a single leading slash when VITE_API_URL is /", async () => {
    vi.resetModules();
    vi.stubEnv("VITE_API_URL", "/");
    const fetch = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ status: "ok" })));
    try {
      const hosted = await import("./api");
      await hosted.request("/api/settings");
      expect(fetch).toHaveBeenCalledWith("/api/settings", expect.anything());
    } finally {
      vi.unstubAllEnvs();
      vi.resetModules();
    }
  });
});

describe("truthful generation diagnostics", () => {
  it.each([
    ["FAILED", true, false, "Generation failed"],
    ["NOT_INVOKED", false, false, "Model not invoked"],
    ["SUCCEEDED", true, true, "Generation succeeded"],
  ])(
    "renders %s without implying successful release",
    async (status, invoked, inspected, heading) => {
      sessionStorage.setItem("governance-token", "synthetic-token");
      window.history.replaceState({}, "", "/playground");
      const stage = {
        decision: "BLOCK",
        score: 70,
        breakdown: { secret_detection: "FAILED" },
        contributions: { secret_detection: 0 },
        findings: [],
        safe_text: null,
        revalidated: false,
      };
      vi.spyOn(globalThis, "fetch").mockImplementation(
        async () =>
          new Response(
            JSON.stringify({
              input: { ...stage, decision: "ALLOW" },
              output: inspected ? stage : null,
              decision: "BLOCK",
              safe_response: null,
              model_invoked: invoked,
              generation_status: status,
              provider_mode: "live",
              policy_id: "synthetic-policy",
              policy_name: "Active immutable policy",
              policy_version: 2,
              duration_ms: 10,
              request_id: "synthetic-request",
              ...(status === "FAILED"
                ? {
                    provider_error: "Generation unavailable; response withheld",
                    provider_diagnostics: { code: "GENERATION_READ_TIMEOUT" },
                  }
                : {}),
            }),
          ),
      );
      render(<App />);
      fireEvent.click(
        screen.getByRole("button", { name: /Run governed request/ }),
      );
      await screen.findByRole("heading", { name: heading });
      expect(screen.getByText(/Active immutable policy/)).toBeInTheDocument();
      expect(
        screen.getByText(
          "Response withheld. No unvalidated model content was released.",
        ),
      ).toBeInTheDocument();
      if (status === "FAILED")
        expect(screen.getByText(/GENERATION_READ_TIMEOUT/)).toBeInTheDocument();
      window.history.replaceState({}, "", "/");
    },
  );
});

describe("separate audit histories", () => {
  it("loads policy and governance histories independently and clears old metadata", async () => {
    sessionStorage.setItem("governance-token", "test-token");
    window.history.pushState({}, "", "/reports");
    const fetch = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) => {
        const url = String(input);
        let result: unknown = [];
        if (url.includes("/api/settings")) result = { role: "Admin" };
        if (url.includes("/api/audit/events")) {
          const category = new URL(url).searchParams.get("category");
          result = [
            {
              id: "audit-record",
              created: "2026-11-01T00:00:00",
              action:
                category === "policy"
                  ? "policy.created"
                  : category === "governance"
                    ? "governance.generate.ALLOW"
                    : "session.created",
            },
          ];
        }
        return new Response(JSON.stringify(result));
      });
    render(<App />);
    await screen.findByText("policy.created");
    expect(
      screen.queryByText("governance.generate.ALLOW"),
    ).not.toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Governance execution history" }),
    );
    await screen.findByText("governance.generate.ALLOW");
    expect(screen.queryByText("policy.created")).not.toBeInTheDocument();
    expect(
      fetch.mock.calls.some(([url]) =>
        String(url).includes("offset=0&limit=20&category=governance"),
      ),
    ).toBe(true);
    fireEvent.click(
      screen.getByRole("button", { name: "Administrative history" }),
    );
    await screen.findByText("session.created");
    expect(
      screen.queryByText("governance.generate.ALLOW"),
    ).not.toBeInTheDocument();
    window.history.replaceState({}, "", "/");
  });
});

describe("remove policies while retaining history", () => {
  it("deletes a disabled inactive policy with its version and retains active-policy protection", async () => {
    sessionStorage.setItem("governance-token", "test-token");
    window.history.pushState({}, "", "/policies");
    vi.spyOn(window, "confirm").mockReturnValue(true);
    let removed = false;
    const fetch = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input, options) => {
        const url = String(input);
        if (options?.method === "DELETE") {
          removed = true;
          return new Response(
            JSON.stringify({ deleted: true, history_retained: true }),
          );
        }
        return new Response(
          JSON.stringify(
            url.includes("/api/settings")
              ? { role: "Admin" }
              : [
                  ...(!removed
                    ? [
                        {
                          id: "inactive",
                          name: "Disabled policy",
                          status: "PUBLISHED",
                          enabled: 0,
                          has_published_versions: true,
                          is_active: false,
                          row_version: 7,
                        },
                      ]
                    : []),
                  {
                    id: "active",
                    name: "Assigned policy",
                    status: "PUBLISHED",
                    enabled: 0,
                    has_published_versions: true,
                    is_active: true,
                    row_version: 4,
                  },
                ],
          ),
        );
      });
    render(<App />);
    await screen.findByRole("link", { name: "Disabled policy" });
    const deletes = screen.getAllByRole("button", {
      name: "Delete",
    });
    expect(deletes[0]).toBeEnabled();
    expect(deletes[1]).toBeDisabled();
    fireEvent.click(deletes[0]);
    await screen.findByText(
      "Policy removed from Policies. Audit history is retained.",
    );
    expect(
      screen.queryByRole("link", { name: "Disabled policy" }),
    ).not.toBeInTheDocument();
    expect(window.confirm).toHaveBeenCalledWith(
      expect.stringContaining(
        "Audit history and published versions will be kept",
      ),
    );
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/policies/inactive"),
      expect.objectContaining({
        method: "DELETE",
        headers: expect.objectContaining({ "If-Match": "7" }),
      }),
    );
    window.history.replaceState({}, "", "/");
  });

  it("shows retained published versions from policy history without restore controls", async () => {
    sessionStorage.setItem("governance-token", "test-token");
    window.history.pushState({}, "", "/reports");
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      let data: unknown = [];
      if (url.includes("/api/settings")) data = { role: "Admin" };
      else if (url.includes("/api/audit/events"))
        data = [
          {
            id: "audit",
            created: "2026-11-02",
            action: "policy.removed",
            resource: "removed-policy",
          },
        ];
      else if (url.includes("/api/policies/removed-policy/versions"))
        data = [
          {
            id: "version-one",
            number: 1,
            created: "2026-11-01",
            document: '{"name":"Retained policy"}',
          },
        ];
      else if (url.includes("/api/policies/removed-policy"))
        data = { name: "Retained policy", status: "DELETED" };
      return new Response(JSON.stringify(data));
    });
    render(<App />);
    fireEvent.click(
      await screen.findByRole("button", { name: "View retained versions" }),
    );
    await screen.findByRole("heading", {
      name: "Retained policy history: Retained policy",
    });
    expect(await screen.findByText(/Published version 1/)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Restore version/ }),
    ).not.toBeInTheDocument();
    window.history.replaceState({}, "", "/");
  });
});
