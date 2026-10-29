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
