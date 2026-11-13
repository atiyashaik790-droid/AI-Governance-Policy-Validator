import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./main";

afterEach(() => { cleanup(); vi.restoreAllMocks(); window.history.replaceState({}, "", "/"); });

function mock() {
  const calls: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const path = new URL(String(input)).pathname;
    calls.push(path);
    const json = (value: unknown) => new Response(JSON.stringify(value));
    if (path === "/api/sso/status") return json({ configured: true });
    if (path === "/api/sso/me") return json({ user: "synthetic", role: "Admin", tenant: "one", csrf_token: "csrf" });
    if (path === "/api/v2/workspace/policy-state") return json({ mode: "MULTI", multi_policy_available: true, set_revision: 2, active_policy_count: 1 });
    if (path === "/api/policies") return json([{ id: "one", name: "Synthetic policy", revision: 3 }]);
    if (path.startsWith("/api/v2/simulation/")) return json({ simulation: true, model_invoked: false, decision: "BLOCK", inspection_status: "COMPLETE", policy_count: 1, policies: [{ policy_id: "one", policy_name: "Synthetic policy", version: 3, version_label: "Draft revision 3", decision: "BLOCK", local: { findings: [{ category: "blocked_keywords", count: 1 }] } }] });
    return json([]);
  });
  return calls;
}

it("hides category navigation and redirects direct category visits", async () => {
  mock(); window.history.replaceState({}, "", "/categories"); render(<App />);
  await screen.findByTitle("Sign out");
  await waitFor(() => expect(window.location.pathname).toBe("/"));
  expect(screen.queryByRole("link", { name: "Category management" })).not.toBeInTheDocument();
  expect(screen.queryByText("Governance category management")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Policy management" })).toBeInTheDocument();
});

it("simulates a selected policy and active MULTI workspace repeatedly", async () => {
  const calls = mock(); window.history.replaceState({}, "", "/simulator"); render(<App />);
  const button = await screen.findByRole("button", { name: "Simulate policy" });
  expect(button).toBeDisabled();
  fireEvent.change(await screen.findByLabelText("Policy draft"), { target: { value: "one" } });
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
  expect(await screen.findByText("Simulation only · no AI generation")).toBeInTheDocument();
  expect(screen.getByText(/Synthetic policy · Draft revision 3/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Simulation mode"), { target: { value: "workspace" } });
  fireEvent.click(button);
  await waitFor(() => expect(calls.filter(path => path === "/api/v2/simulation/workspace")).toHaveLength(1));
  expect(calls.filter(path => path === "/api/v2/simulation/policies/one")).toHaveLength(1);
});

it("shows Policy Validation Studio on the existing route without a page-wide banner", async () => {
  mock(); window.history.replaceState({}, "", "/simulator"); render(<App />);
  expect(await screen.findByRole("heading", { name: "Policy Validation Studio", level: 1 })).toBeInTheDocument();
  expect(screen.getByText("Validate governance policies before publishing or activating them.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Policy Validation Studio" })).toHaveAttribute("href", "/simulator");
  expect(screen.queryByText(/Policy simulator/i)).not.toBeInTheDocument();
  await screen.findByRole("option", { name: "Synthetic policy" });
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(document.querySelector(".page-heading + .notice")).toBeNull();
});

it("reports policy-list and simulation failures next to the action without fabricating results", async () => {
  let policiesFail = true;
  const posts: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const path = new URL(String(input)).pathname;
    const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
    if (path === "/api/sso/status") return json({ configured: true });
    if (path === "/api/sso/me") return json({ user: "synthetic", role: "Admin", tenant: "one", csrf_token: "csrf" });
    if (path === "/api/v2/workspace/policy-state") return json({ mode: "MULTI", multi_policy_available: true, set_revision: 2, active_policy_count: 1 });
    if (path === "/api/policies") { if (policiesFail) throw new TypeError("Failed to fetch"); return json([{ id: "one", name: "Synthetic policy", revision: 3 }]); }
    if (path.startsWith("/api/v2/simulation/")) { posts.push(path); return json({ detail: "Simulation backend unavailable" }, 503); }
    return json([]);
  });
  window.history.replaceState({}, "", "/simulator"); render(<App />);
  const failure = await screen.findByText(/Policies couldn't be loaded/);
  expect(failure).toHaveTextContent("Network unavailable");
  policiesFail = false;
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  await screen.findByRole("option", { name: "Synthetic policy" });
  expect(screen.queryByText(/Policies couldn't be loaded/)).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Policy draft"), { target: { value: "one" } });
  fireEvent.click(screen.getByRole("button", { name: "Simulate policy" }));
  expect(await screen.findByText(/Validation failed: Simulation backend unavailable/)).toBeInTheDocument();
  expect(screen.queryByText("Simulation only · no AI generation")).not.toBeInTheDocument();
  expect(posts).toEqual(["/api/v2/simulation/policies/one"]);
});
