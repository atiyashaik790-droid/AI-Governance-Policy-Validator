import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { UsageConsumption } from "./UsageConsumption";
import { WorkspaceSessions } from "./WorkspaceSessions";
import { App } from "./main";

const usage = { date: "2026-11-06", reserved_today: 81, daily_limit: 100, warning: true, warning_percent: 80,
  statuses: { SUCCEEDED: 120, FAILED: 7, EXPIRED: 3, INSPECTED: 2 }, tokens: { prompt_tokens: 500, completion_tokens: null }, user_per_minute: 10, tenant_per_minute: 50, concurrency_limit: 4 };
const session = { id: "synthetic-session", actor: "synthetic@example.test", expires: "2026-11-07T12:30:00+00:00", revoked: false, expired: false };
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
afterEach(() => { cleanup(); vi.restoreAllMocks(); window.history.replaceState({}, "", "/"); });

it("distinguishes daily reservations, retained statuses and unavailable recorded tokens", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async () => json(usage));
  render(<UsageConsumption />);
  await screen.findByText("81 / 100");
  expect(screen.getByRole("progressbar", { name: "Daily request reservations" })).toHaveAttribute("value", "81");
  expect(screen.getByRole("alert")).toHaveTextContent("warning threshold");
  expect(screen.getByText(/Warning threshold: 80%/)).toBeInTheDocument();
  expect(screen.getByText("Successful inferences").nextElementSibling).toHaveTextContent("120");
  expect(screen.getByText("500")).toBeInTheDocument();
  expect(screen.getByText("Not recorded")).toBeInTheDocument();
  expect(screen.getByText(/cover all retained history/)).toBeInTheDocument();
  expect(screen.getAllByRole("meter")).toHaveLength(4);
  expect(screen.getByText("Per-tenant requests / minute").nextElementSibling).toHaveTextContent("50");
});

it("handles empty usage without inventing token records or dividing by zero", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async () => json({ ...usage, reserved_today: 0, daily_limit: 0, warning: false, statuses: {}, tokens: { prompt_tokens: null, completion_tokens: 0 } }));
  render(<UsageConsumption />);
  await screen.findByText("No inference history recorded.");
  expect(screen.getByRole("progressbar")).toHaveAttribute("value", "0");
  expect(screen.queryByRole("alert")).toBeNull();
});

it("shows usage loading and retries a failed request", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockImplementationOnce(async () => json({ detail: "Usage temporarily unavailable" }, 503)).mockImplementation(async () => json(usage));
  render(<UsageConsumption />);
  expect(screen.getByLabelText("Loading data")).toBeInTheDocument();
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  await screen.findByText("81 / 100");
  expect(fetch).toHaveBeenCalledTimes(2);
});

it("renders truthful page summaries and missing session identity fields", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async () => json([session, { ...session, id: "expired", actor: "", expired: true }, { ...session, id: "revoked", revoked: true, expired: true }]));
  render(<WorkspaceSessions />);
  const table = await screen.findByRole("table");
  expect(screen.getByText(/Summary counts cover this page only/)).toBeInTheDocument();
  for (const state of ["Active", "Expired", "Revoked"]) expect(screen.getByText(`${state} · this page`).nextElementSibling).toHaveTextContent("1");
  expect(within(table).getAllByText("Not recorded").length).toBeGreaterThanOrEqual(6);
  expect(within(table).getAllByText(new Date(session.expires).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }))).toHaveLength(3);
  expect(screen.getAllByRole("button", { name: /Revoke session for/ }).filter(button => button.hasAttribute("disabled"))).toHaveLength(2);
});

it("requires confirmation and only revokes a synthetic session through mocked fetch", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, options) => options?.method === "POST" ? json({ status: "revoked" }) : json([session]));
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
  render(<WorkspaceSessions />);
  const button = await screen.findByRole("button", { name: /Revoke session for/ });
  fireEvent.click(button);
  expect(fetch.mock.calls.filter(([, options]) => options?.method === "POST")).toHaveLength(0);
  confirm.mockReturnValue(true);
  fireEvent.click(button);
  await screen.findByText("Session revoked.");
  expect(fetch.mock.calls.filter(([, options]) => options?.method === "POST")).toHaveLength(1);
  expect(fetch.mock.calls.some(([url]) => String(url).endsWith("/api/sso/sessions/synthetic-session/revoke"))).toBe(true);
});

it("preserves session pagination and refresh with page-scoped counts", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(async url => json(String(url).includes("offset=20") ? [] : Array.from({ length: 20 }, (_, index) => ({ ...session, id: `synthetic-${index}` }))));
  render(<WorkspaceSessions />);
  await screen.findByRole("table");
  fireEvent.click(screen.getByRole("button", { name: "Next sessions" }));
  await screen.findByText("No workspace sessions on this page.");
  expect(screen.getByText("Active · this page").nextElementSibling).toHaveTextContent("0");
  expect(screen.getByRole("button", { name: "Next sessions" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Refresh sessions" }));
  await waitFor(() => expect(fetch.mock.calls.filter(([url]) => String(url).includes("offset=20"))).toHaveLength(2));
  fireEvent.click(screen.getByRole("button", { name: "Previous sessions" }));
  await screen.findByRole("table");
});

it("handles session load failure and empty recovery", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementationOnce(async () => json({ detail: "Sessions unavailable" }, 503)).mockImplementation(async () => json([]));
  render(<WorkspaceSessions />);
  expect(screen.getByLabelText("Loading data")).toBeInTheDocument();
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  await screen.findByText("No workspace sessions on this page.");
});

it("uses the local demo session API when demo mode is selected", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(json([]));
  render(<WorkspaceSessions mode="demo" />);
  await screen.findByText("No workspace sessions on this page.");
  expect(fetch.mock.calls.some(([url]) => new URL(String(url)).pathname === "/api/auth/sessions")).toBe(true);
  expect(fetch.mock.calls.some(([url]) => new URL(String(url)).pathname === "/api/sso/sessions")).toBe(false);
});

it.each([["Admin", "LEGACY"], ["Auditor", "LEGACY"], ["Reviewer", "LEGACY"], ["Admin", "MULTI"]])("keeps usage out of Settings and redirects analytics to Overview for %s in %s", async (role, mode) => {
  window.history.replaceState({}, "", "/analytics");
  const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(async url => {
    const path = new URL(String(url)).pathname;
    if (path === "/api/sso/status") return json({ configured: true });
    if (path === "/api/sso/me") return json({ user: "synthetic", role, tenant: "one", csrf_token: "synthetic" });
    if (path === "/api/settings") return json({ role, provider_mode: "fixture", database: "synthetic" });
    if (path === "/api/v2/workspace/policy-state") return json({ mode, multi_policy_available: mode === "MULTI", set_revision: 1 });
    if (path === "/api/usage") return json(usage);
    if (["/api/analytics/overview", "/api/v2/analytics/overview"].includes(path)) return json({ request_count: 0, active_policy_count: 0, policy_evaluation_count: 0, total_validations: 0, active_policies: 0, total_policies: 0, pending_reviews: 0, decisions: {}, trends: [], violations: {}, contributions: {} });
    return json([]);
  });
  render(<App />);
  await screen.findByRole("heading", { name: "Your governance, at a glance" });
  await waitFor(() => expect(window.location.pathname).toBe("/"));
  expect(screen.queryByRole("link", { name: "Compliance analytics" })).not.toBeInTheDocument();
  for (const page of ["Policy management", "Policy Validation Studio", "AI playground", "Human review", "Audit & reports", "Settings"]) {
    expect(screen.getByRole("link", { name: page })).toBeInTheDocument();
  }
  expect(fetch.mock.calls.some(([url]) => String(url).endsWith("/api/usage"))).toBe(false);
  expect(screen.queryByRole("heading", { name: /Inference consumption/i })).toBeNull();
  await screen.findByRole("heading", { name: "Compliance score" });
  expect(screen.queryByRole("heading", { name: "AI Usage & Consumption" })).toBeNull();
});

it("surfaces synthetic revocation errors and leaves the session available", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
  vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, options) => options?.method === "POST" ? json({ detail: "Session action unavailable" }, 503) : json([session]));
  render(<WorkspaceSessions />);
  fireEvent.click(await screen.findByRole("button", { name: /Revoke session for/ }));
  expect(await screen.findByRole("status")).toHaveTextContent("Session action unavailable");
  expect(screen.getByRole("button", { name: /Revoke session for/ })).toBeEnabled();
});
