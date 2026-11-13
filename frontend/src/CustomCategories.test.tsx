import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./main";

afterEach(() => { cleanup(); vi.restoreAllMocks(); window.history.replaceState({}, "", "/"); });
function workspace(role = "Admin") {
  const writes: { body: Record<string, unknown>; headers: HeadersInit | undefined }[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url, options = {}) => {
    const path = new URL(String(url)).pathname;
    const json = (body: unknown) => new Response(JSON.stringify(body));
    if (path === "/api/sso/me") return json({ role, user: "fixture", tenant: "one", csrf_token: "csrf" });
    if (path === "/api/sso/status") return json({ configured: true });
    if (path === "/api/settings") return json({ role, provider_mode: "fixture", pii_mode: "regex" });
    if (path === "/api/v2/workspace/policy-state") return json({ mode: "LEGACY", multi_policy_available: false, active_policy_count: 0, set_revision: null });
    if (path === "/api/capabilities") return json({ available_pii_entities: [], pii_status: "ready" });
    if (path === "/api/policies" && options.method === "POST") {
      writes.push({ body: JSON.parse(String(options.body)), headers: options.headers });
      return json({ id: "new-policy" });
    }
    return json([]);
  });
  window.history.replaceState({}, "", "/policies/new"); render(<App />);
  return writes;
}

it("adds, edits, disables and removes custom categories alongside built-in controls, then saves through the authenticated API", async () => {
  const writes = workspace();
  const add = await screen.findByRole("button", { name: "Add custom category" });
  fireEvent.click(add);
  const section = within(screen.getByRole("region", { name: "Custom rule categories" }));
  fireEvent.change(section.getByLabelText("Category name"), { target: { value: "Finance" } });
  fireEvent.change(section.getByLabelText("Category description"), { target: { value: "Invoice identifiers" } });
  fireEvent.change(section.getByLabelText("Category action"), { target: { value: "REDACT" } });
  fireEvent.change(section.getByLabelText("Detection method"), { target: { value: "regex" } });
  fireEvent.change(section.getByLabelText("Patterns (one per line)"), { target: { value: "INV-\\d{3}" } });
  fireEvent.click(section.getByRole("checkbox"));
  fireEvent.click(add);
  fireEvent.click(section.getAllByRole("button", { name: "Remove category" })[1]);
  fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
  await waitFor(() => expect(writes).toHaveLength(1));
  expect(writes[0].body.custom_categories).toEqual([expect.objectContaining({ name: "Finance", description: "Invoice identifiers", enabled: false, action: "REDACT", detection: "regex", values: ["INV-\\d{3}"] })]);
  expect(Object.keys(writes[0].body.rules as object)).toHaveLength(4);
  expect(writes[0].headers).toMatchObject({ "X-CSRF-Token": "csrf" });
});

it.each(["Policy Owner", "Developer", "Reviewer", "Auditor"])("does not offer custom configuration to %s", async role => {
  workspace(role);
  await screen.findByText("Only Admin users can configure custom categories.");
  expect(screen.queryByRole("button", { name: "Add custom category" })).not.toBeInTheDocument();
});
