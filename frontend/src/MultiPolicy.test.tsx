import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./main";

afterEach(() => { cleanup(); vi.restoreAllMocks(); window.history.replaceState({}, "", "/"); });
function mockWorkspace({ role = "Admin", mode = "MULTI", conflict = false, available = true } = {}) {
  let revision = 7;
  let active = false;
  const calls: { path: string; method: string; body: Record<string, unknown>; headers: Record<string, string> }[] = [];
  vi.spyOn(window, "confirm").mockReturnValue(true);
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url, options = {}) => {
    const path = new URL(String(url)).pathname;
    const method = options.method || "GET";
    const body = options.body ? JSON.parse(String(options.body)) : {};
    calls.push({ path, method, body, headers: options.headers as Record<string, string> });
    const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
    if (path === "/api/sso/status") return json({ configured: true });
    if (path === "/api/sso/me") return json({ user: "synthetic", role, tenant: "one", csrf_token: "csrf" });
    if (path === "/api/settings") return json({ provider_mode: "fixture", pii_mode: "regex", role });
    if (path === "/api/v2/workspace/policy-state") return json({ mode, multi_policy_available: available, set_revision: available ? revision : null, active_policy_count: active ? 1 : 0 });
    if (path === "/api/policies") return json([{ id: "policy-one", name: "Pinned policy", status: "PUBLISHED", enabled: 1, has_published_versions: true, revision: 1, row_version: 1 }]);
    if (path === "/api/policies/policy-one/versions") return json([{ id: "old-pin", number: 1 }, { id: "new-pin", number: 2 }]);
    if (path === "/api/v2/workspace/policy-assignments") return json({ items: active ? [{ policy_id: "policy-one", version_id: "old-pin", version: 1, active }] : [], total: active ? 1 : 0, set_revision: revision });
    if (path === "/api/v2/workspace/policy-assignments/policy-one") {
      if (conflict) { revision++; return json({ detail: "POLICY_SET_PRECONDITION_FAILED" }, 412); }
      active = body.active === true; revision++;
      return json({ set_revision: revision });
    }
    if (path.includes("/governance/")) {
      const policies = Array.from({ length: 6 }, (_, i) => ({ policy_id: `policy-${i}`, policy_name: `Published policy ${i + 1}`, version: 1, decision: "ALLOW", inspection_status: "COMPLETE" }));
      const stage = { decision: "ALLOW", policies, policy_count: 6, inspection_status: "COMPLETE", revalidated: false };
      return json({ decision: "ALLOW", input: stage, output: stage, safe_response: "Sanitized fixture response", model_invoked: true, provider_mode: "fixture", request_id: "request-one" });
    }
    if (path === "/api/v2/audit/executions") return json({ items: [{ request_id: "request-one", timestamp: "2026-11-05", execution_mode: "MULTI", policy_evaluation_count: 6, decision: "BLOCK" }], total: 1 });
    if (path === "/api/v2/audit/executions/request-one") return json({ request_id: "request-one", execution_mode: "MULTI", policy_evidence: [{ policy_id: "p", decision: "BLOCK", inspections: { local: { findings: [{ category: "secret_detection", count: 1 }] } } }] });
    if (path === "/api/feedback/summary") return json({ count: 0, average: null });
    return json([]);
  });
  return calls;
}

it("requires an explicit version, sends a strong workspace precondition, and deactivates independently", async () => {
  const calls = mockWorkspace();
  window.history.replaceState({}, "", "/policies"); render(<App />);
  fireEvent.click(await screen.findByText("More"));
  fireEvent.click(await screen.findByRole("button", { name: "Choose published version" }));
  const select = await screen.findByLabelText("Published version for Pinned policy");
  expect(screen.getByRole("option", { name: "Version 1" })).toBeInTheDocument();
  expect(screen.queryByText(/Version ID:/)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Activate selected version" })).toBeDisabled();
  fireEvent.change(select, { target: { value: "old-pin" } });
  fireEvent.click(screen.getByRole("button", { name: "Activate selected version" }));
  await screen.findByText("Active · pinned published version 1");
  const writes = calls.filter(c => c.method === "PUT");
  expect(writes[0].body).toEqual({ active: true, version_id: "old-pin" });
  expect(writes[0].headers).toMatchObject({ "If-Match": '"7"', "X-CSRF-Token": "csrf" });
  fireEvent.click(screen.getByRole("button", { name: "Deactivate policy" }));
  await screen.findByText("Policy deactivated.");
  expect(calls.filter(c => c.method === "PUT")[1].body).toEqual({ active: false });
});

it("shows the compact operational status and hides workspace mode on the policy page", async () => {
  mockWorkspace(); window.history.replaceState({}, "", "/policies"); render(<App />);
  await screen.findByRole("link", { name: "Pinned policy" });
  expect(screen.queryByRole("region", { name: "Workspace policy mode" })).not.toBeInTheDocument();
  expect(screen.getByText("INACTIVE")).toHaveClass("inactive");
  expect(screen.getByRole("columnheader", { name: "Version" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Disable" })).toBeInTheDocument();
});

it("surfaces stale ETags and refreshes without replaying the mutation", async () => {
  const calls = mockWorkspace({ conflict: true });
  window.history.replaceState({}, "", "/policies"); render(<App />);
  fireEvent.click(await screen.findByText("More"));
  fireEvent.click(await screen.findByRole("button", { name: "Choose published version" }));
  fireEvent.change(await screen.findByLabelText("Published version for Pinned policy"), { target: { value: "old-pin" } });
  fireEvent.click(screen.getByRole("button", { name: "Activate selected version" }));
  await screen.findByText(/Workspace changed. Refresh the workspace/);
  expect(calls.filter(c => c.method === "PUT")).toHaveLength(1);
});

it.each(["Policy Owner", "Developer", "Reviewer", "Auditor"])("hides activation and mode mutation for %s", async role => {
  mockWorkspace({ role }); window.history.replaceState({}, "", "/policies"); render(<App />);
  await screen.findByRole("link", { name: "Pinned policy" });
  expect(screen.queryByRole("button", { name: "Choose published version" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Enable MULTI mode" })).not.toBeInTheDocument();
});

it("uses one v2 request, renders all per-policy input/output results and keeps the precondition", async () => {
  const calls = mockWorkspace(); window.history.replaceState({}, "", "/playground"); render(<App />);
  const run = await screen.findByRole("button", { name: /Run governed request/ });
  await waitFor(() => expect(run).toBeEnabled());
  expect(screen.getByText(/Approved prompts receive the same sample response/)).toBeInTheDocument();
  fireEvent.click(run); fireEvent.click(run);
  await screen.findByText("Sanitized fixture response");
  expect(screen.getAllByText(/6 policies evaluated/)).toHaveLength(2);
  expect(screen.getAllByText("Published policy 1")).toHaveLength(2);
  expect(screen.queryByText("policy-0")).not.toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "Workspace policy mode" })).not.toBeInTheDocument();
  expect(screen.getByText("Provider: Local deterministic fixture")).toBeInTheDocument();
  const sent = calls.filter(c => c.method === "POST" && c.path.includes("/governance/"));
  expect(sent).toHaveLength(1); expect(sent[0].path).toBe("/api/v2/governance/generate");
  expect(sent[0].headers["If-Match"]).toBe('"7"');
});

it("retains schema-005 legacy routing without the technical mode panel", async () => {
  const calls = mockWorkspace({ mode: "LEGACY", available: false }); window.history.replaceState({}, "", "/playground"); render(<App />);
  expect(screen.queryByRole("region", { name: "Workspace policy mode" })).not.toBeInTheDocument();
  const run = await screen.findByRole("button", { name: /Run governed request/ });
  await waitFor(() => expect(run).toBeEnabled()); fireEvent.click(run);
  await screen.findByText("Sanitized fixture response");
  expect(calls.find(c => c.method === "POST" && c.path.includes("/governance/"))?.path).toBe("/api/governance/generate");
});

it("uses versioned history even after returning to LEGACY and displays sanitized evidence", async () => {
  const calls = mockWorkspace({ mode: "LEGACY" }); window.history.replaceState({}, "", "/history"); render(<App />);
  await screen.findByText("MULTI · 6 policy evaluations");
  fireEvent.click(screen.getByRole("button", { name: "Inspect metadata" }));
  await waitFor(() => expect(within(screen.getByText("Record metadata").closest("section")!).getByText(/secret_detection/)).toBeInTheDocument());
  expect(calls.some(c => c.path === "/api/v2/audit/executions/request-one")).toBe(true);
  expect(screen.queryByText("SyntheticSecretOriginal", { exact: false })).not.toBeInTheDocument();
});


it("preserves LEGACY activation controls for Policy Owners", async () => {
  mockWorkspace({ role: "Policy Owner", mode: "LEGACY" });
  window.history.replaceState({}, "", "/policies"); render(<App />);
  expect(await screen.findByRole("button", { name: "activate" })).toBeEnabled();
  expect(screen.queryByRole("button", { name: "Enable MULTI mode" })).not.toBeInTheDocument();
});
