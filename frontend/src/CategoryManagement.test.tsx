import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { CategoryManagement } from "./CategoryManagement";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const response = (body: unknown) => new Response(JSON.stringify(body));

it("creates a category and assigns it to a draft policy", async () => {
  const writes: { url: string; method: string; body: unknown }[] = [];
  let items: unknown[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, options) => {
    const url = new URL(String(input));
    const method = options?.method || "GET";
    if (url.pathname === "/api/policies") return response([{ id: "policy-1", name: "Draft policy", status: "DRAFT" }]);
    if (url.pathname === "/api/categories" && method === "GET") return response({ items, total: items.length, offset: 0, limit: 20 });
    if (method !== "GET") writes.push({ url: url.pathname, method, body: options?.body ? JSON.parse(String(options.body)) : null });
    if (url.pathname === "/api/categories" && method === "POST") {
      const category = { id: "category-1", name: "Finance", description: "", builtin: false,
        enabled: true, action: "BLOCK", detection: "keyword", values: ["private finance"], revision: 1, policy_ids: [] };
      items = [category]; return response(category);
    }
    if (url.pathname.endsWith("/policies/policy-1") && method === "PUT") {
      const category = { ...(items[0] as object), policy_ids: ["policy-1"] };
      items = [category]; return response(category);
    }
    return response({});
  });
  render(<CategoryManagement role="Admin" />);
  await screen.findByText("No categories found.");
  fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Finance" } });
  fireEvent.change(screen.getByLabelText("Patterns, one per line"), { target: { value: "private finance" } });
  fireEvent.click(screen.getByRole("button", { name: "Create category" }));
  await screen.findByText("Category created.");
  fireEvent.change(screen.getByLabelText("Assign draft policy"), { target: { value: "policy-1" } });
  fireEvent.click(screen.getByRole("button", { name: "Assign policy" }));
  await screen.findByText(/Policy assigned/);
  expect(writes).toEqual([
    expect.objectContaining({ url: "/api/categories", method: "POST", body: expect.objectContaining({ name: "Finance", values: ["private finance"] }) }),
    expect.objectContaining({ url: "/api/categories/category-1/policies/policy-1", method: "PUT" }),
  ]);
});

it("keeps category mutations unavailable to a Reviewer", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async input => {
    const path = new URL(String(input)).pathname;
    return path === "/api/policies" ? response([]) : response({ items: [], total: 0, offset: 0, limit: 20 });
  });
  render(<CategoryManagement role="Reviewer" />);
  await waitFor(() => expect(screen.getByText("No categories found.")).toBeInTheDocument());
  expect(screen.queryByRole("button", { name: "Create category" })).toBeNull();
});
