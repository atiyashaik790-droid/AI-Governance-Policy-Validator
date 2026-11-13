import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ReviewContent } from "./ReviewContent";

const record = { id: "r1", row_version: 2, status: "PENDING", assigned_reviewer: "reviewer", execution: { actor: "alice", actor_role: "User", policies: [{ name: "Confidential policy", version: 3 }] }, protected_content: { availability: "AVAILABLE", can_reveal: true }, decision_history: [{ actor: "admin", action: "assigned", reason: "Assigned for review" }] };
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.useRealTimers(); });

it("shows professional metadata and never prefetches protected content", () => {
  const fetch = vi.spyOn(globalThis, "fetch");
  render(<ReviewContent record={record} refreshPath="/api/reviews/r1" onRefresh={vi.fn()} />);
  expect(screen.getByText("alice")).toBeInTheDocument();
  expect(screen.getByText("User")).toBeInTheDocument();
  expect(screen.getByText("Confidential policy · v3")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Reveal original prompt" })).toBeEnabled();
  expect(fetch).not.toHaveBeenCalled();
});

it("reveals exact whitespace as plain text only, sends version and hides on request", async () => {
  const prompt = '  original\n<img src=x onerror=alert(1)> 雪  ';
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ original_prompt: prompt, expires_at: Date.now() / 1000 + 900, clear_after_seconds: 300 })));
  const { container } = render(<ReviewContent record={record} refreshPath="/api/reviews/r1" onRefresh={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "Reveal original prompt" }));
  const text = await screen.findByLabelText("Original user prompt");
  expect(text.textContent).toBe(prompt);
  expect(container.querySelector("img")).toBeNull();
  expect(fetch.mock.calls[0][0]).toContain("/api/reviews/r1/content");
  expect(fetch.mock.calls[0][1]?.headers).toMatchObject({ "If-Match": '"2"' });
  fireEvent.click(screen.getByRole("button", { name: "Hide original prompt" }));
  expect(screen.queryByLabelText("Original user prompt")).toBeNull();
});

it.each(["EXPIRED", "PURGED", "NEVER_RETAINED", "UNAVAILABLE"])("never reveals %s content", state => {
  const fetch = vi.spyOn(globalThis, "fetch");
  render(<ReviewContent record={{ ...record, protected_content: { availability: state, can_reveal: false } }} refreshPath="/api/reviews/r1" onRefresh={vi.fn()} />);
  expect(screen.getByRole("button", { name: "Reveal original prompt" })).toBeDisabled();
  expect(fetch).not.toHaveBeenCalled();
});

it("clears on signout and never displays late response after unmount", async () => {
  let resolve!: (response: Response) => void;
  vi.spyOn(globalThis, "fetch").mockImplementation(() => new Promise(done => { resolve = done; }));
  const { unmount } = render(<ReviewContent record={record} refreshPath="/api/reviews/r1" onRefresh={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "Reveal original prompt" }));
  window.dispatchEvent(new Event("governance-session-ended"));
  resolve(new Response(JSON.stringify({ original_prompt: "LateSecret", expires_at: Date.now() / 1000 + 900, clear_after_seconds: 300 })));
  await waitFor(() => expect(screen.queryByText("LateSecret")).toBeNull());
  unmount();
});

it("distinguishes retrieval failure and shows no held text", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: "Review changed; refresh before revealing content" }), { status: 412 }));
  render(<ReviewContent record={record} refreshPath="/api/reviews/r1" onRefresh={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "Reveal original prompt" }));
  expect(await screen.findByText("Review changed; refresh before revealing content")).toBeInTheDocument();
  expect(screen.queryByLabelText("Original user prompt")).toBeNull();
});

it("clears revealed text when reassignment or resolution changes the case", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ original_prompt: "HeldSecret", expires_at: Date.now() / 1000 + 900, clear_after_seconds: 300 })));
  const props = { refreshPath: "/api/reviews/r1", onRefresh: vi.fn() };
  const { rerender } = render(<ReviewContent record={record} {...props} />);
  fireEvent.click(screen.getByRole("button", { name: "Reveal original prompt" }));
  await screen.findByLabelText("Original user prompt");
  rerender(<ReviewContent record={{ ...record, row_version: 3, assigned_reviewer: "other", protected_content: { availability: "AVAILABLE", can_reveal: false } }} {...props} />);
  expect(screen.queryByText("HeldSecret")).toBeNull();
  expect(screen.getByRole("button", { name: "Reveal original prompt" })).toBeDisabled();
});

it("automatically clears content at the server-provided reveal deadline", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ original_prompt: "ExpiringSecret", expires_at: Date.now() / 1000 + 900, clear_after_seconds: .05 })));
  render(<ReviewContent record={record} refreshPath="/api/reviews/r1" onRefresh={vi.fn()} />);
  fireEvent.click(screen.getByRole("button", { name: "Reveal original prompt" }));
  await screen.findByLabelText("Original user prompt");
  await waitFor(() => expect(screen.queryByText("ExpiringSecret")).toBeNull());
});
