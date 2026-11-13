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
    if (path === "/api/chat/conversations") return json(conversations.map(({ id, title, created_at, updated_at }) => ({ id, title, created_at, updated_at })));
    if (path.startsWith("/api/chat/conversations/")) {
      const row = conversations.find(item => item.id === path.split("/").at(-1));
      return row ? json(row) : json({ detail: "Conversation not found" }, 404);
    }
    if (path === "/api/v2/governance/generate-document") {
      const row = conversations.find(item => item.id === body.conversation_id)!;
      const shown = ["ALLOW", "REDACT"].includes(decision) ? `${String(body.text)}\n\nAttachment: PDF document` : "Request submitted";
      row.messages.push({ id: `message-${row.messages.length + 1}`, role: "user", content: shown, decision });
      row.messages.push({ id: `message-${row.messages.length + 1}`, role: "assistant", content: "Safe document answer", decision });
      if (row.title === "New conversation") row.title = "Resume Summary";
      return json({ decision, request_id: "private-request-id", attachment: { type: "pdf" } });
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

it("shows the governed question with the attachment name, and only the type after reload", async () => {
  const { calls } = setup();
  await screen.findByText("No conversations yet.");
  fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Summarize this resume" } });
  fireEvent.change(screen.getByLabelText("Attach PDF, DOCX or TXT"),
    { target: { files: [new File(["%PDF synthetic"], "resume.pdf", { type: "application/pdf" })] } });
  fireEvent.click(screen.getByRole("button", { name: "Send message" }));
  await screen.findByText("Safe document answer");
  expect(screen.getByText("Summarize this resume")).toBeInTheDocument();
  expect(screen.getByText("Attachment: resume.pdf")).toBeInTheDocument();
  expect(await screen.findByRole("button", { name: /Resume Summary/ })).toBeInTheDocument();
  expect(calls.find(call => call.path === "/api/v2/governance/generate-document")?.body.filename).toBe("resume.pdf");
  expect(JSON.stringify(window.localStorage)).not.toContain("resume");
  cleanup();
  render(<App />);
  await screen.findByText("Safe document answer");
  expect(screen.getByText("Summarize this resume")).toBeInTheDocument();
  expect(screen.getByText("Attachment: PDF document")).toBeInTheDocument();
  expect(screen.queryByText(/resume\.pdf/)).not.toBeInTheDocument();
});

it.each([["BLOCK", /withheld by a governance policy/], ["HUMAN_REVIEW", /held for review/]])(
  "explains a withheld %s prompt without showing it or the placeholder", async (decision, reason) => {
    setup(decision);
    await screen.findByText("No conversations yet.");
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "api_key=sk-test-SECRET1234567890" } });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    await screen.findByText(reason);
    expect(screen.queryByText("Request submitted")).not.toBeInTheDocument();
    expect(screen.queryByText(/sk-test-SECRET/)).not.toBeInTheDocument();
  });

it("keeps multiline prompts intact in the user bubble", async () => {
  setup();
  await screen.findByText("No conversations yet.");
  fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Line one\nLine two" } });
  fireEvent.click(screen.getByRole("button", { name: "Send message" }));
  await screen.findByText("Safe AI answer");
  const bubble = screen.getByText((_, element) => element?.tagName === "P" && element.textContent === "Line one\nLine two");
  expect(bubble.closest("article")).toHaveClass("chat-message-user");
});
