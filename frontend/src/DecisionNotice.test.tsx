import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { BrowserRouter } from "react-router-dom";
import { DecisionNotice, DecisionMessageSettings, canRelease, messageFor } from "./DecisionNotice";
import type { DecisionResult } from "./DecisionNotice";
import { App } from "./main";

afterEach(() => { cleanup(); vi.restoreAllMocks(); window.history.replaceState({}, "", "/"); });

it.each(["BLOCK", "HUMAN_REVIEW", "REDACT", "ALLOW"])("shows accessible default %s guidance with a next action", decision => {
  render(<BrowserRouter><DecisionNotice result={{ decision, model_invoked: false, review_id: decision === "HUMAN_REVIEW" ? "review-one" : undefined }} /></BrowserRouter>);
  const panel = screen.getByRole(decision === "ALLOW" ? "status" : "alert");
  expect(panel).toHaveTextContent("Next step:");
  if (decision === "HUMAN_REVIEW") {
    expect(panel).toHaveTextContent("has not been sent to the AI model");
    expect(panel).toHaveTextContent("resubmit under current policies");
    expect(screen.getByRole("link", { name: "Open metadata-only review" })).toHaveAttribute("href", "/reviews");
  }
});

it("distinguishes output review and technical failures", () => {
  expect(messageFor({ decision: "HUMAN_REVIEW", model_invoked: true }).message).toContain("was invoked");
  expect(messageFor({ decision: "BLOCK", generation_status: "FAILED", provider_error: "SensitiveProviderError" }).message).not.toContain("SensitiveProviderError");
  expect(messageFor({ decision: "BLOCK", output: { decision: "BLOCK", inspection_status: "INCOMPLETE" } }).kind).toBe("technical");
});

it.each([
  { decision: "BLOCK", output: { decision: "ALLOW" } },
  { decision: "HUMAN_REVIEW", output: { decision: "ALLOW" } },
  { decision: "REDACT", output: null },
  { decision: "REDACT", output: { decision: "BLOCK" } },
  { decision: "REDACT", output: { decision: "REDACT", revalidated: false } },
  { decision: "REDACT", output: { decision: "ALLOW", inspection_status: "INCOMPLETE" } },
  { decision: "ALLOW", output: { decision: "ALLOW", breakdown: { secret_detection: "UNKNOWN" } } },
  { decision: "BLOCK", generation_status: "FAILED", output: { decision: "ALLOW" } },
])("never releases a response without successful output governance: %j", value => {
  expect(canRelease({ ...value, safe_response: "MustNotEscape" })).toBe(false);
});

it("renders message text without executing HTML or exposing other result fields", () => {
  const result = { decision: "BLOCK", original_prompt: "OriginalSecret", matched_pattern: "PrivatePattern", decision_notice: {
    kind: "policy" as const, category: "custom", title: "Custom category protection", message: '<img src=x onerror="alert(1)">', next_action: "Revise and resubmit.",
  } };
  const { container } = render(<BrowserRouter><DecisionNotice result={result} /></BrowserRouter>);
  expect(container.querySelector("img")).toBeNull();
  expect(container).not.toHaveTextContent("OriginalSecret");
  expect(container).not.toHaveTextContent("PrivatePattern");
});

it("offers safe Admin message templates and read-only controls to other roles", () => {
  const change = vi.fn();
  const { rerender } = render(<DecisionMessageSettings value={{}} admin onChange={change} />);
  fireEvent.change(screen.getByLabelText("BLOCK message template"), { target: { value: "contact_admin" } });
  expect(change).toHaveBeenCalledWith({ BLOCK: "contact_admin" });
  rerender(<DecisionMessageSettings value={{ BLOCK: "contact_admin" }} admin={false} onChange={change} />);
  expect(screen.getByLabelText("BLOCK message template")).toBeDisabled();
});

it.each([false, true])("integrates review guidance into the Playground for uploads=%s without showing held content", async attachment => {
  const posts: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async url => {
    const path = new URL(String(url)).pathname;
    const json = (body: unknown) => new Response(JSON.stringify(body));
    if (path === "/api/sso/me") return json({ role: "Admin", user: "fixture", tenant: "one", csrf_token: "csrf" });
    if (path === "/api/sso/status") return json({ configured: true });
    if (path === "/api/settings") return json({ role: "Admin", provider_mode: "fixture", pii_mode: "regex" });
    if (path === "/api/v2/workspace/policy-state") return json({ mode: "MULTI", multi_policy_available: true, active_policy_count: 2, set_revision: 7 });
    if (path.includes("/governance/")) {
      posts.push(path);
      return json({ decision: "HUMAN_REVIEW", model_invoked: false, safe_response: "MustNotEscape", review_id: "r", request_id: "q", provider_mode: "fixture", decision_notice: {
        kind: "policy", category: "custom", title: "Human review required", message: "A custom policy category restricts this content. This request has not been sent to the AI model.",
        next_action: "Track the metadata-only review. Approval requires resubmission under current policies.",
      } });
    }
    return json([]);
  });
  window.history.replaceState({}, "", "/playground"); render(<App />);
  if (attachment) fireEvent.change(await screen.findByLabelText("Attach PDF, DOCX or TXT"), { target: { files: [new File(["synthetic text"], "sample.txt", { type: "text/plain" })] } });
  const run = await screen.findByRole("button", { name: /Run governed request/ });
  await waitFor(() => expect(run).toBeEnabled()); fireEvent.click(run);
  await screen.findByRole("heading", { name: "Human review required" });
  expect(screen.getByRole("alert")).toHaveTextContent("has not been sent to the AI model");
  expect(screen.queryByText("MustNotEscape")).not.toBeInTheDocument();
  expect(posts).toEqual([`/api/v2/governance/${attachment ? "generate-document" : "generate"}`]);
});

it("releases ALLOW and REDACT only after successful output inspection", () => {
  for (const decision of ["ALLOW", "REDACT"]) {
    const result: DecisionResult = { decision, safe_response: "Safe response", output: { decision: "ALLOW", inspection_status: "COMPLETE" } };
    expect(canRelease(result)).toBe(true);
  }
});
