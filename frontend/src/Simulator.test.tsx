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
