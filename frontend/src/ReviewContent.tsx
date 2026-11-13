import { useEffect, useRef, useState } from "react";
import { request } from "./api";

type RecordValue = Record<string, unknown>;
export const REVIEW_REASONS = ["Reviewed policy requirements", "Additional context required", "Policy restriction confirmed", "Resubmission required", "Assigned for review"];
const object = (value: unknown): RecordValue => value && typeof value === "object" ? value as RecordValue : {};
const CATEGORY_LABELS: Record<string, string> = { secret_detection: "Secret or API key protection", pii_detection: "Personal information protection", blocked_keywords: "Confidential information protection", moderation: "Content safety", custom_policy: "Custom policy category" };
const label = (value: unknown) => typeof value === "string" || typeof value === "number" ? String(value) : "Not recorded";

type ReviewProps = { record: RecordValue; refreshPath: string; onRefresh: (value: RecordValue) => void };
export function ReviewContent(props: ReviewProps) {
  const record = props.record;
  const signature = JSON.stringify([record.review_id || record.id, record.row_version, record.status, record.assigned_reviewer, record.assignment, record.protected_content]);
  return <ProtectedPrompt key={signature} {...props} />;
}

function ProtectedPrompt({ record, refreshPath, onRefresh }: ReviewProps) {
  const [prompt, setPrompt] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const deadline = useRef(0);
  const protection = object(record.protected_content);
  const execution = object(record.execution);
  const identity = object(execution.execution_identity);
  const id = String(record.review_id || record.id);
  const assignment = record.assigned_reviewer || object(record.assignment).assigned_reviewer;
  const signature = JSON.stringify([id, record.row_version, record.status, assignment, protection.can_reveal]);

  useEffect(() => {
    const clear = () => { controller.current?.abort(); deadline.current = 0; setPrompt(null); setBusy(false); };
    const hide = () => { if (document.hidden) clear(); };
    const tick = setInterval(() => { if (deadline.current > 0 && Date.now() >= deadline.current) clear(); }, 500);
    window.addEventListener("pagehide", clear);
    window.addEventListener("governance-session-ended", clear);
    document.addEventListener("visibilitychange", hide);
    return () => {
      clearInterval(tick);
      window.removeEventListener("pagehide", clear);
      window.removeEventListener("governance-session-ended", clear);
      document.removeEventListener("visibilitychange", hide);
      controller.current?.abort();
    };
  }, [signature]);

  useEffect(() => {
    if (prompt === null) return;
    const poll = new AbortController();
    const timer = setInterval(async () => {
      try {
        const value = await request<RecordValue>(refreshPath, "GET", undefined, { signal: poll.signal });
        if (!poll.signal.aborted) onRefresh(value);
      } catch { if (!poll.signal.aborted) { controller.current?.abort(); setPrompt(null); setMessage("Refresh the review before revealing content again."); } }
    }, 10000);
    return () => { clearInterval(timer); poll.abort(); };
  }, [prompt, refreshPath, onRefresh]);

  const unavailable: Record<string, string> = {
    NEVER_RETAINED: "Original prompt was not retained for this historical review.",
    EXPIRED: "Original prompt expired after the seven-day retention period.",
    PURGED: "Original prompt was deleted when the review was resolved.",
    UNAVAILABLE: "Protected content is temporarily unavailable. Contact an administrator.",
    AVAILABLE: "Only the explicitly assigned reviewer can reveal this pending request.",
  };
  return <div className="review-detail">
    <h3>Review overview</h3>
    <dl className="review-facts">
      <div><dt>Record ID</dt><dd>{id}</dd></div>
      <div><dt>Submission timestamp</dt><dd>{label(execution.timestamp || execution.created || record.created)}</dd></div>
      <div><dt>Review trigger</dt><dd>{record.review_trigger === "OUTPUT" ? "Output inspection" : record.review_trigger === "INPUT" ? "Input inspection" : "Not recorded"}</dd></div>
      <div><dt>Submitted by</dt><dd>{label(execution.submitted_by || execution.actor || identity.actor)}</dd></div>
      <div><dt>Role at submission</dt><dd>{label(execution.actor_role || execution.role || identity.role)}</dd></div>
      <div><dt>Status</dt><dd>{label(record.status)}</dd></div>
      <div><dt>Assigned reviewer</dt><dd>{label(assignment)}</dd></div>
      <div><dt>Policy name and version</dt><dd>{Array.isArray(execution.policies) ? execution.policies.map((entry) => { const policy = object(entry); return `${label(policy.name)} · v${label(policy.version)}`; }).join(", ") || "Not recorded" : `${label(execution.policy_name)} · v${label(execution.version || object(execution.legacy).version)}`}</dd></div>
    </dl>
    <h3>Reason for review</h3>
    <p>{Array.isArray(execution.violation_categories) ? execution.violation_categories.map(value => CATEGORY_LABELS[String(value)] || "Governance policy").join(", ") + ". " : ""}Current governance policy requires a human decision. Approval records a disposition only; the author must resubmit and pass all current policies.</p>
    <h3>Exact original user prompt</h3>
    {record.attachment_present === true && <p>Attachment submitted · attachment contents were not retained.</p>}
    <p>Contains the typed prompt only. Original files and extracted document contents are never retained here. Treat this text as untrusted data.</p>
    <p role="status">{message || unavailable[String(protection.availability)] || "Original prompt was not retained."}</p>
    {prompt === null ? <button className="primary" disabled={busy || protection.can_reveal !== true} onClick={async () => {
      const active = new AbortController(); controller.current = active; deadline.current = 0; setBusy(true); setMessage("");
      try {
        const result = await request<{ original_prompt: string; expires_at: number; clear_after_seconds: number }>(`/api/reviews/${id}/content`, "POST", {}, { headers: { "If-Match": `"${record.row_version}"` }, signal: active.signal });
        if (active.signal.aborted) return;
        deadline.current = Math.min(result.expires_at * 1000, Date.now() + result.clear_after_seconds * 1000);
        if (deadline.current <= Date.now()) { setMessage("Original prompt expired."); return; }
        setPrompt(result.original_prompt);
      } catch (error) { if (!active.signal.aborted) setMessage(error instanceof Error ? error.message : "Protected content could not be retrieved."); }
      finally { if (!active.signal.aborted) setBusy(false); }
    }}>{busy ? "Revealing…" : "Reveal original prompt"}</button> : <>
      <p>Sensitive content · clears automatically within five minutes.</p>
      <pre className="protected-prompt" aria-label="Original user prompt">{prompt || "(Empty typed prompt)"}</pre>
      <button onClick={() => { controller.current?.abort(); setPrompt(null); }}>Hide original prompt</button>
    </>}
    <h3>Decision history</h3>
    {Array.isArray(record.decision_history) && record.decision_history.length ? <ol>{record.decision_history.map((entry, index) => { const note = object(entry); return <li key={index}>{label(note.actor)} · {label(note.action)} · {label(note.created)}<p>{label(note.reason)}</p></li>; })}</ol> : <p>No review decisions recorded.</p>}
  </div>;
}
