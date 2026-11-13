import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./main";

afterEach(() => { cleanup(); vi.restoreAllMocks(); window.history.replaceState({}, "", "/"); });

type StoredMessage = { id: string; role: "user" | "assistant"; content: string; decision: string };
function setup(decision = "ALLOW") {
  const conversations: { id: string; title: string; created_at: string; updated_at: string; messages: StoredMessage[] }[] = [];
  const calls: { path: string; method: string; body: Record<string, unknown> }[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url, options = {}) => {
    const path = new URL(String(url)).pathname;
    const method = options.method || "GET";
    const body = options.body ? JSON.parse(String(options.body)) : {};
    calls.push({ path, method, body });
    const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
    if (path === "/api/sso/status") return json({ configured: true });
    if (path === "/api/sso/me") return json({ user: "actual.account@example.test", role: "User", tenant: "one", csrf_token: "csrf" });
    if (path === "/api/v2/workspace/policy-state") return json({ mode: "MULTI", multi_policy_available: true, set_revision: 7, active_policy_count: 2 });
    if (path === "/api/chat/conversations" && method === "POST") {
      const row = { id: `conversation-${conversations.length + 1}`, title: "New conversation",
        created_at: "2026-11-13T12:00:00+00:00", updated_at: "2026-11-13T12:00:00+00:00", messages: [] };
      conversations.unshift(row); return json(row, 201);
    }
    if (path === "/api/chat/conversations") return json(conversations.map(({ messages: _messages, ...row }) => row));
    if (path.startsWith("/api/chat/conversations/")) {
      const row = conversations.find(item => item.id === path.split("/").at(-1));
      return row ? json(row) : json({ detail: "Conversation not found" }, 404);
    }
    if (path === "/api/v2/governance/generate") {
      const row = conversations.find(item => item.id === body.conversation_id)!;
      const safe = decision === "ALLOW" ? String(body.text) : decision === "REDACT" ? "[REDACTED]" : "Request submitted";
      const answer = ["ALLOW", "REDACT"].includes(decision) ? "Safe AI answer" :
        decision === "BLOCK" ? "Sorry, I can't process that request because it contains restricted information." :
          "This request requires review and cannot proceed yet.";
      row.messages.push({ id: `message-${row.messages.length + 1}`, role: "user", content: safe, decision });
      row.messages.push({ id: `message-${row.messages.length + 1}`, role: "assistant", content: answer, decision });
      if (row.title === "New conversation") row.title = safe === "Request submitted" ? "Restricted request" : safe;
      row.updated_at = "2026-11-13T12:01:00+00:00";
      return json({ decision, request_id: "private-request-id", safe_response: "Unapproved text must not render",
        decision_notice: { title: "Request passed governance" } });
    }
    return json([]);
  });
  window.history.replaceState({}, "", "/chat");
  render(<App />);
  return { calls, conversations };
}

it.each(["ALLOW", "REDACT", "BLOCK", "HUMAN_REVIEW"])("shows a simple %s conversation without technical cards or IDs", async decision => {
  const { calls } = setup(decision);
  const prompt = await screen.findByLabelText("Message");
  await screen.findByText("No conversations yet.");
  fireEvent.change(prompt, { target: { value: "Sensitive test prompt" } });
  fireEvent.click(screen.getByRole("button", { name: "Send message" }));
  const expected = ["ALLOW", "REDACT"].includes(decision) ? "Safe AI answer" :
    decision === "BLOCK" ? /restricted information/ : /requires review/;
  await screen.findByText(expected);
  expect(calls.some(call => call.path === "/api/v2/governance/generate" && call.body.conversation_id)).toBe(true);
  expect(screen.queryByText(/Request reference/)).not.toBeInTheDocument();
  expect(screen.queryByText(/Request passed governance/)).not.toBeInTheDocument();
  expect(screen.queryByText(/Sensitive information removed/)).not.toBeInTheDocument();
  expect(screen.queryByText("private-request-id")).not.toBeInTheDocument();
  expect(screen.queryByText("Unapproved text must not render")).not.toBeInTheDocument();
  if (decision !== "ALLOW") expect(screen.queryByText("Sensitive test prompt")).not.toBeInTheDocument();
});

it("starts and reopens conversations, restoring server history after remount", async () => {
  const { conversations } = setup();
  await screen.findByText("No conversations yet.");
  fireEvent.click(screen.getByRole("button", { name: "New chat" }));
  await waitFor(() => expect(conversations).toHaveLength(1));
  const prompt = screen.getByLabelText("Message");
  fireEvent.change(prompt, { target: { value: "First question" } });
  fireEvent.click(screen.getByRole("button", { name: "Send message" }));
  await screen.findByText("Safe AI answer");
  fireEvent.click(screen.getByRole("button", { name: "New chat" }));
  await waitFor(() => expect(conversations).toHaveLength(2));
  expect(screen.queryByText("Safe AI answer")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /First question/ }));
  await screen.findByText("First question");
  expect(screen.getByText("Safe AI answer")).toBeInTheDocument();
  cleanup();
  render(<App />);
  await screen.findByRole("heading", { name: "Your AI assistant" });
  await screen.findByRole("button", { name: /First question/ });
  fireEvent.click(screen.getByRole("button", { name: /First question/ }));
  await screen.findByText("First question");
  expect(screen.getByText("Safe AI answer")).toBeInTheDocument();
});
