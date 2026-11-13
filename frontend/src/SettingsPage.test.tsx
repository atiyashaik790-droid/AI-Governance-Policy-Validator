import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./main";

const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
afterEach(() => { cleanup(); vi.restoreAllMocks(); window.history.replaceState({}, "", "/"); });
function setup(sso: boolean, role = "Admin", sessionsStatus = 200) {
  window.history.replaceState({}, "", "/settings");
  const calls = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const path = new URL(String(input)).pathname;
    if (path === "/api/sso/status") return json({ configured: true });
    if (path === "/api/sso/me") return json({ user: "actual.operator@example.test", role, tenant: "demo-workspace", csrf_token: "synthetic", expires_at: sso ? "2026-11-12T22:00:00Z" : undefined });
    if (path === "/api/settings") return json({ role, tenant: "demo-workspace", database: "sqlite", database_status: "CONNECTED", pii_mode: "presidio", provider_mode: "fixture", sso_enabled: sso, build_version: "demo-build", release: { build_version: "demo-build", git_commit: "abc123" }, api_contract: "1.2", required_migration: "010", database_migration: "009", demo_session_minutes: 60, integrations: {
      azure_generation: { status: "CONFIGURED_NOT_VERIFIED", last_verification_at: null, error_code: null, freshness_hours: 24, verification_enabled: false },
      moderation: { status: "NOT_CONFIGURED", last_verification_at: null, error_code: null, freshness_hours: 24, verification_enabled: false },
      adls: { status: "VERIFIED", last_verification_at: "2026-11-10T00:00:00Z", error_code: null, freshness_hours: 24, verification_enabled: false },
    } });
    if (path === "/api/capabilities") return json({ pii_status: "AVAILABLE", pii_mode: "presidio" });
    if (path === "/api/v2/workspace/policy-state") return json({ mode: "LEGACY", multi_policy_available: false });
    if (path.endsWith("/sessions")) return sessionsStatus === 200 ? json([]) : json({ detail: "Sessions unavailable" }, sessionsStatus);
    return json([]);
  });
  render(<App />);
  return calls;
}

it("shows accurate local demo sections and structured release diagnostics", async () => {
  const calls = setup(false);
  expect(await screen.findByRole("heading", { name: "System Health" })).toBeInTheDocument();
  expect(screen.getByText("Connected · SQLITE")).toBeInTheDocument();
  expect(screen.getByText("Local Fixture Mode")).toBeInTheDocument();
  expect(await screen.findByText("Presidio")).toBeInTheDocument();
  expect(screen.getByText("Local demo authentication")).toBeInTheDocument();
  expect(screen.getByText("actual.operator@example.test")).toBeInTheDocument();
  expect(screen.getByText("Not provided by this session API")).toBeInTheDocument();
  expect(await screen.findByText("No workspace sessions on this page.")).toBeInTheDocument();
  expect(calls.mock.calls.some(([input]) => new URL(String(input)).pathname === "/api/auth/sessions")).toBe(true);
  expect(screen.getByText("Verification result: Configured, not verified")).toBeInTheDocument();
  expect(screen.queryByText(/ADLS upload/i)).not.toBeInTheDocument();
  const summary = screen.getByText("Advanced Diagnostics");
  expect(summary.closest("details")).not.toHaveAttribute("open");
  fireEvent.click(summary);
  expect(summary.closest("details")).toHaveAttribute("open");
  expect(screen.getByText("demo-build · abc123")).toBeInTheDocument();
  expect(screen.queryByText("[object Object]")).not.toBeInTheDocument();
  expect(calls.mock.calls.every(([, options]) => options?.method !== "POST")).toBe(true);
});

it("shows Entra session errors and limits session management to Admin", async () => {
  const calls = setup(true, "Admin", 503);
  expect(await screen.findByText("Microsoft Entra ID SSO")).toBeInTheDocument();
  expect(await screen.findByRole("alert")).toHaveTextContent("Sessions unavailable");
  expect(calls.mock.calls.some(([input]) => new URL(String(input)).pathname === "/api/sso/sessions")).toBe(true);
  expect(calls.mock.calls.every(([, options]) => options?.method !== "POST")).toBe(true);
});

it("does not fetch workspace sessions for a non-admin viewer", async () => {
  const calls = setup(true, "Auditor");
  expect(await screen.findByText("Session management is available to workspace administrators.")).toBeInTheDocument();
  await waitFor(() => expect(calls.mock.calls.some(([input]) => new URL(String(input)).pathname === "/api/settings")).toBe(true));
  expect(calls.mock.calls.some(([input]) => new URL(String(input)).pathname.endsWith("/sessions"))).toBe(false);
  expect(screen.queryByRole("button", { name: /Verify Azure OpenAI/ })).not.toBeInTheDocument();
});
