import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./main";

const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
afterEach(() => { cleanup(); vi.restoreAllMocks(); window.history.replaceState({}, "", "/"); });
function setup(versioned = true, fail = false, page = "/reports") {
  window.history.replaceState({}, "", page);
  const fetch = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = new URL(String(input));
    if (url.pathname === "/api/sso/status") return json({ configured: true });
    if (url.pathname === "/api/sso/me") return json({ user: "synthetic", role: "Admin", tenant: "one", csrf_token: "synthetic" });
    if (url.pathname === "/api/settings") return json({ role: "Admin", provider_mode: "live", pii_mode: "regex" });
    if (url.pathname === "/api/v2/workspace/policy-state") return json({ mode: versioned ? "MULTI" : "LEGACY", multi_policy_available: versioned, set_revision: 1, active_policy_count: 0 });
    if (/\/audit\/(events|executions)$/.test(url.pathname)) {
      if (fail && url.searchParams.has("start_date")) return json({ detail: "History unavailable" }, 503);
      const offset = Number(url.searchParams.get("offset"));
      const filtered = url.searchParams.has("start_date") || url.searchParams.has("end_date");
      const rows = filtered || page === "/history" ? Array.from({ length: page === "/history" ? 1 : offset ? 1 : 20 }, (_, index) => ({ id: `filtered-${offset + index}`, created: "2026-11-01T00:00:00+00:00", action: "policy.published", actor: "synthetic", actor_role: "Admin", status: "ALLOW" })) : [];
      return json(versioned ? { items: rows, total: filtered ? 21 : 0, offset, limit: 20 } : rows);
    }
    return json([]);
  });
  render(<App />);
  const historyCalls = () => fetch.mock.calls.map(([input]) => new URL(String(input))).filter(url => /\/audit\/(events|executions)$/.test(url.pathname));
  return { fetch, historyCalls };
}

it("shows the role recorded by the audit API", async () => {
  setup(false);
  await screen.findByRole("heading", { name: "History date filter" });
  setDates();
  fireEvent.click(screen.getByRole("button", { name: "Apply Filter" }));
  await waitFor(() => {
    const row = screen.getAllByRole("row").find(item => item.textContent?.includes("synthetic"));
    expect(row).toBeDefined();
    expect(within(row!).getByText("Admin")).toBeInTheDocument();
  });
});

it("keeps validation records and metadata without loading decision feedback", async () => {
  const { fetch } = setup(false, false, "/history");
  expect(await screen.findByRole("heading", { name: "Validation history" })).toBeInTheDocument();
  const inspect = await screen.findByRole("button", { name: "Inspect metadata" });
  expect(screen.queryByRole("heading", { name: "Decision feedback" })).not.toBeInTheDocument();
  fireEvent.click(inspect);
  expect(screen.getByRole("heading", { name: "Record metadata" })).toBeInTheDocument();
  expect(fetch.mock.calls.some(([input]) => new URL(String(input)).pathname === "/api/feedback/summary")).toBe(false);
});
function setDates(start = "2026-11-01", end = "2026-11-01") {
  fireEvent.change(screen.getByLabelText("Start date"), { target: { value: start } });
  fireEvent.change(screen.getByLabelText("End date"), { target: { value: end } });
}

it.each([false, true])("applies server filters, preserves them on every tab, and clears them (v2=%s)", async versioned => {
  const { historyCalls } = setup(versioned);
  await screen.findByText("No events in this history yet.");
  const count = historyCalls().length;
  setDates();
  expect(historyCalls()).toHaveLength(count); // Draft selections do not issue requests.
  fireEvent.click(screen.getByRole("button", { name: "Apply Filter" }));
  await waitFor(() => expect(historyCalls().at(-1)!.searchParams.has("start_date")).toBe(true));
  let url = historyCalls().at(-1)!;
  expect(url.searchParams.get("start_date")).toBe("2026-11-01");
  expect(url.searchParams.get("end_date")).toBe("2026-11-01");
  expect(url.searchParams.get("category")).toBe("policy");
  setDates("2026-11-02", "2026-11-02"); // Unapplied edits must not change tab queries.
  for (const [tab, endpoint, category] of [["Governance execution history", "executions", "governance"], ["Administrative history", "events", "administration"], ["Policy history", "events", "policy"]]) {
    fireEvent.click(screen.getByRole("button", { name: tab }));
    await waitFor(() => expect(historyCalls().at(-1)!.searchParams.get("category")).toBe(category));
    url = historyCalls().at(-1)!;
    expect(url.pathname).toBe(`/api${versioned ? "/v2" : ""}/audit/${endpoint}`);
    expect(url.searchParams.get("start_date")).toBe("2026-11-01");
    expect(url.searchParams.get("end_date")).toBe("2026-11-01");
    expect(url.searchParams.get("offset")).toBe("0");
  }
  fireEvent.click(screen.getByRole("button", { name: "Clear Filter" }));
  await screen.findByText("No events in this history yet.");
  expect(historyCalls().at(-1)!.searchParams.has("start_date")).toBe(false);
  expect(historyCalls().at(-1)!.searchParams.has("end_date")).toBe(false);
  expect(screen.getByLabelText("Start date")).toHaveValue("");
});

it("keeps filters on subsequent server pages and resets pagination on Apply", async () => {
  const { historyCalls } = setup();
  await screen.findByRole("heading", { name: "History date filter" });
  setDates(); fireEvent.click(screen.getByRole("button", { name: "Apply Filter" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Next" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  await waitFor(() => expect(historyCalls().at(-1)!.searchParams.get("offset")).toBe("20"));
  expect(historyCalls().at(-1)!.searchParams.get("end_date")).toBe("2026-11-01");
  setDates("2026-11-02", "2026-11-02");
  fireEvent.click(screen.getByRole("button", { name: "Apply Filter" }));
  await waitFor(() => expect(historyCalls().at(-1)!.searchParams.get("offset")).toBe("0"));
  expect(historyCalls().at(-1)!.searchParams.get("start_date")).toBe("2026-11-02");
});

it("rejects reversed and overlong ranges before any history request", async () => {
  const { historyCalls } = setup();
  await screen.findByText("No events in this history yet.");
  const count = historyCalls().length;
  for (const [start, end] of [["2026-11-02", "2026-11-01"], ["2020-01-01", "2026-11-01"]]) {
    setDates(start, end); fireEvent.click(screen.getByRole("button", { name: "Apply Filter" }));
    expect(screen.getByRole("alert")).toHaveTextContent("start on or before the end");
    expect(historyCalls()).toHaveLength(count);
  }
});

it("shows a filtered error and retains the applied range for Retry", async () => {
  const { historyCalls } = setup(true, true);
  await screen.findByText("No events in this history yet.");
  setDates(); fireEvent.click(screen.getByRole("button", { name: "Apply Filter" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("History unavailable");
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  await waitFor(() => expect(historyCalls().filter(url => url.searchParams.has("start_date"))).toHaveLength(2));
});

it("removes export attempts without fetching them and preserves diagnostics", async () => {
  const { fetch } = setup();
  await screen.findByRole("heading", { name: "History date filter" });
  expect(screen.queryByText(/LIVE PROVIDER MODE/)).toBeNull();
  expect(document.querySelector(".environment-banner")).toBeNull();
  expect(screen.queryByRole("button", { name: "Export JSON" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Export CSV" })).toBeNull();
  expect(screen.queryByRole("heading", { name: "Export attempts" })).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Show all prior export attempts, including legacy snapshots")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Previous exports" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Next exports" })).not.toBeInTheDocument();
  expect(fetch.mock.calls.some(([input]) => new URL(String(input)).pathname.includes("/reports/exports"))).toBe(false);
  expect(fetch.mock.calls.some(([, options]) => options?.method === "POST")).toBe(false);
  fireEvent.click(screen.getByRole("link", { name: "Settings" }));
  await screen.findByRole("heading", { name: "Workspace Sessions", level: 1 });
  expect(screen.queryByRole("button", { name: "Refresh diagnostics" })).not.toBeInTheDocument();
});

it("shows filtered loading and the explicit date-range empty state", async () => {
  const { fetch } = setup();
  await screen.findByText("No events in this history yet.");
  const original = fetch.getMockImplementation()!;
  let resolve!: (response: Response) => void;
  fetch.mockImplementation((url, options) => String(url).includes("start_date=") ? new Promise(done => { resolve = done; }) : original(url, options));
  setDates(); fireEvent.click(screen.getByRole("button", { name: "Apply Filter" }));
  expect(screen.getByLabelText("Loading data")).toBeInTheDocument();
  resolve(json({ items: [], total: 0, offset: 0, limit: 20 }));
  await screen.findByText("No records found for the selected date range");
});
