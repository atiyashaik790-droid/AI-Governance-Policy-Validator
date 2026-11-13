import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { IntegrationStatus } from "./IntegrationStatus";

const unverified = { status: "CONFIGURED_NOT_VERIFIED", last_verification_at: null, error_code: null, freshness_hours: 24, verification_enabled: false };
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("shows truthful states and never contacts providers while rendering or refreshing", () => {
  const fetch = vi.spyOn(globalThis, "fetch");
  render(<IntegrationStatus value={{ azure_generation: unverified, moderation: { ...unverified, status: "FAILED", error_code: "VERIFICATION_FAILED" }, adls: { ...unverified, status: "STALE", last_verification_at: "2026-11-06T10:00:00Z" } }} admin onRefresh={vi.fn()} />);
  for (const value of ["Configured, not verified", "Verification failed"]) expect(screen.getByText(`Verification result: ${value}`)).toBeInTheDocument();
  expect(screen.queryByText("ADLS upload and read-back")).not.toBeInTheDocument();
  expect(screen.getByText(/VERIFICATION_FAILED/)).toBeInTheDocument();
  expect(screen.getAllByRole("button").every(b => b.hasAttribute("disabled"))).toBe(true);
  expect(fetch).not.toHaveBeenCalled();
});

it("requires confirmation and a deliberate enabled Admin action", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ ...unverified, status: "VERIFIED" }), { status: 200 }));
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
  const refresh = vi.fn().mockResolvedValue(undefined);
  render(<IntegrationStatus value={{ moderation: { ...unverified, verification_enabled: true } }} admin onRefresh={refresh} />);
  fireEvent.click(screen.getByRole("button", { name: "Verify OpenAI Moderation" }));
  expect(fetch).not.toHaveBeenCalled();
  confirm.mockReturnValue(true);
  fireEvent.click(screen.getByRole("button", { name: "Verify OpenAI Moderation" }));
  await screen.findByText("OpenAI Moderation: VERIFIED");
  await waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(JSON.parse(String(fetch.mock.calls[0][1]?.body))).toEqual({ confirm_billable_operation: true });
});

it("does not offer verification to non-Admin roles", () => {
  render(<IntegrationStatus value={{ moderation: { ...unverified, verification_enabled: true } }} admin={false} onRefresh={vi.fn()} />);
  expect(screen.queryByRole("button")).toBeNull();
});
