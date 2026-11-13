import { useState } from "react";
import { request } from "./api";

type Evidence = { status: string; last_verification_at: string | null; error_code: string | null; freshness_hours: number; verification_enabled: boolean };
const labels: Record<string, string> = { azure_generation: "Azure OpenAI Generation", moderation: "OpenAI Moderation" };
const statusLabels: Record<string, string> = { NOT_CONFIGURED: "Not configured", CONFIGURED_NOT_VERIFIED: "Configured, not verified", VERIFIED: "Verified", FAILED: "Verification failed", STALE: "Verification expired" };

export function IntegrationStatus({ value, admin, onRefresh }: { value: unknown; admin: boolean; onRefresh: () => Promise<unknown> }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  if (!value || typeof value !== "object") return null;
  const entries = value as Record<string, Evidence>;
  return <section className="panel" aria-label="Integration verification">
    <h2>Integration Verification</h2>
    <p>These results come from saved verification evidence. Refreshing this page does not contact providers.</p>
    {Object.entries(labels).map(([name, label]) => {
      const evidence = entries[name];
      if (!evidence) return null;
      return <div className="detector" key={name}>
        <strong>{label}</strong><span>Configuration: {evidence.status === "NOT_CONFIGURED" ? "Not configured" : "Configured"}</span>
        <span>Verification result: {statusLabels[evidence.status] || evidence.status}</span>
        <span>Last verification attempt: {evidence.last_verification_at ? new Date(evidence.last_verification_at).toLocaleString() : "Not recorded"}</span>
        {evidence.error_code && <span>Result code: {evidence.error_code}</span>}
        {admin && <button disabled={busy || !evidence.verification_enabled || evidence.status === "NOT_CONFIGURED"} onClick={async () => {
          if (!window.confirm(`Run one real ${label} verification using synthetic data? This may contact an external provider and incur charges.`)) return;
          setBusy(true); setMessage("");
          try {
            const result = await request<Evidence>(`/api/integrations/${name}/verify`, "POST", { confirm_billable_operation: true }, { timeoutMs: 90000 });
            setMessage(`${label}: ${result.status}`);
            await onRefresh();
          } catch (error) { setMessage(error instanceof Error ? error.message : "Verification unavailable"); }
          finally { setBusy(false); }
        }}>Verify {label}</button>}
      </div>;
    })}
    <p role="status">{message}</p>
  </section>;
}
