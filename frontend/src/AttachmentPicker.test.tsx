import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./main";
import { MAX_ATTACHMENT_BYTES } from "./AttachmentPicker";

afterEach(() => { cleanup(); vi.restoreAllMocks(); window.history.replaceState({}, "", "/"); });
function workspace(mode = "LEGACY", failure = false) {
  const calls: { path: string; body: Record<string, unknown>; headers: Record<string, string> }[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url, options = {}) => {
    const path = new URL(String(url)).pathname;
    const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
    if (path === "/api/sso/me") return json({ role: "Admin", user: "fixture", tenant: "one", csrf_token: "csrf" });
    if (path === "/api/sso/status") return json({ configured: true });
    if (path === "/api/settings") return json({ role: "Admin", provider_mode: "fixture", pii_mode: "regex" });
    if (path === "/api/v2/workspace/policy-state") return json({ mode, multi_policy_available: true, active_policy_count: 2, set_revision: 7 });
    if (path.includes("/governance/")) {
      calls.push({ path, body: JSON.parse(String(options.body)), headers: options.headers as Record<string, string> });
      if (failure) return json({ detail: "Encrypted PDF documents are unsupported" }, 422);
      return json({ decision: "ALLOW", output: { decision: "ALLOW" }, safe_response: "Fixture document response", provider_mode: "fixture", model_invoked: true });
    }
    return json([]);
  });
  window.history.replaceState({}, "", "/playground"); render(<App />);
  return calls;
}

it("shows only the three prompt quick tests and keeps governed submission working", async () => {
  const calls = workspace();
  const prompt = await screen.findByLabelText("User prompt");
  const samples = [
    ["Safe prompt", "Explain the benefits of data governance in simple terms."],
    ["Synthetic secret", "api_key=sk-test-ABCDEFGHIJKLMNOPQRSTUVWXYZ12345"],
    ["Synthetic PII", "Contact test.person@example.com about data governance."],
  ];
  expect(screen.queryByRole("button", { name: "Fixture moderation" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Fixture failure" })).not.toBeInTheDocument();
  for (const [label, value] of samples) {
    fireEvent.click(screen.getByRole("button", { name: label }));
    expect(prompt).toHaveValue(value);
  }
  const run = screen.getByRole("button", { name: /Run governed request/ });
  await waitFor(() => expect(run).toBeEnabled());
  fireEvent.click(run);
  await screen.findByText("Fixture document response");
  expect(calls).toHaveLength(1);
  expect(calls[0].body.text).toBe(samples[2][1]);
});

it.each(["LEGACY", "MULTI"])("previews, replaces and submits one governed document request in %s mode", async mode => {
  const calls = workspace(mode);
  const picker = await screen.findByLabelText("Attach PDF, DOCX or TXT");
  fireEvent.change(picker, { target: { files: [new File(["public document"], "first.txt", { type: "text/plain" })] } });
  expect(screen.getByText("first.txt")).toBeInTheDocument();
  expect(screen.getByText(/Type: text\/plain · Size: 15 bytes/)).toBeInTheDocument();
  fireEvent.change(picker, { target: { files: [new File(["replacement document"], "second.txt", { type: "text/plain" })] } });
  expect(screen.queryByText("first.txt")).not.toBeInTheDocument();
  const run = screen.getByRole("button", { name: /Run governed request/ });
  await waitFor(() => expect(run).toBeEnabled());
  fireEvent.click(run); fireEvent.click(run);
  expect(screen.getByText("Reading attachment…")).toBeInTheDocument();
  await screen.findByText("Fixture document response");
  expect(calls).toHaveLength(1);
  expect(calls[0].path).toBe(`${mode === "MULTI" ? "/api/v2" : "/api"}/governance/generate-document`);
  expect(calls[0].body.filename).toBe("second.txt");
  expect(atob(calls[0].body.content_base64 as string)).toBe("replacement document");
  expect(calls[0].headers).toMatchObject({ "X-CSRF-Token": "csrf", ...(mode === "MULTI" ? { "If-Match": '"7"' } : {}) });
  expect(screen.getByText("Document extraction and governance completed.")).toBeInTheDocument();
});

it("removes an attachment and preserves prompt-only routing", async () => {
  const calls = workspace();
  const picker = await screen.findByLabelText("Attach PDF, DOCX or TXT");
  fireEvent.change(picker, { target: { files: [new File(["content"], "data.txt")] } });
  fireEvent.click(screen.getByRole("button", { name: "Remove attachment" }));
  const run = screen.getByRole("button", { name: /Run governed request/ });
  await waitFor(() => expect(run).toBeEnabled()); fireEvent.click(run);
  await screen.findByText("Fixture document response");
  expect(calls[0].path).toBe("/api/governance/generate");
  expect(calls[0].body).not.toHaveProperty("content_base64");
});

it("rejects unsupported and oversized files before submission", async () => {
  workspace();
  const picker = await screen.findByLabelText("Attach PDF, DOCX or TXT");
  fireEvent.change(picker, { target: { files: [new File(["bad"], "run.exe")] } });
  expect(screen.getByRole("alert")).toHaveTextContent("Choose a PDF");
  fireEvent.change(picker, { target: { files: [new File(["a".repeat(MAX_ATTACHMENT_BYTES + 1)], "large.txt")] } });
  expect(screen.getByRole("alert")).toHaveTextContent("256 KiB");
  expect(screen.queryByLabelText("Attachment preview")).not.toBeInTheDocument();
});

it("shows extraction errors without retrying the governed request", async () => {
  const calls = workspace("MULTI", true);
  fireEvent.change(await screen.findByLabelText("Attach PDF, DOCX or TXT"), { target: { files: [new File(["encrypted"], "private.pdf", { type: "application/pdf" })] } });
  const run = screen.getByRole("button", { name: /Run governed request/ });
  await waitFor(() => expect(run).toBeEnabled()); fireEvent.click(run);
  await screen.findByText(/Encrypted PDF documents are unsupported/);
  expect(calls).toHaveLength(1);
  expect(screen.getByText("Request stopped; no content released.")).toBeInTheDocument();
});
