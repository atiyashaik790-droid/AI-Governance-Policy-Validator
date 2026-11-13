import { NavLink } from "react-router-dom";

export type DecisionMessage = {
  kind: "policy" | "technical" | "success"; category: string;
  title: string; message: string; next_action: string;
};
export type DecisionResult = {
  decision: string; decision_notice?: DecisionMessage | null; model_invoked?: boolean;
  generation_status?: string; provider_error?: string; safe_response?: string | null; review_id?: string;
  input?: { decision: string; inspection_status?: string; breakdown?: Record<string, string> } | null;
  output?: { decision: string; inspection_status?: string; breakdown?: Record<string, string>; revalidated?: boolean } | null;
};
export function messageFor(result: DecisionResult): DecisionMessage {
  if (result.provider_error || result.generation_status === "FAILED") return {
    kind: "technical", category: "provider", title: "Generation unavailable",
    message: "The AI provider could not complete this request. No response is released.",
    next_action: "Check request history before retrying. If this continues, contact your administrator.",
  };
  if (result.decision_notice) return result.decision_notice;
  if ([result.input, result.output].some(stage => stage?.inspection_status === "INCOMPLETE" || Object.values(stage?.breakdown || {}).includes("UNKNOWN"))) return {
    kind: "technical", category: "incomplete", title: "Inspection could not complete",
    message: "Required inspection could not complete. No response is released until all required checks can finish.",
    next_action: "Check request history before retrying. If this continues, contact your administrator.",
  };
  const common = { kind: "policy" as const, category: "generic", next_action: "Revise your prompt or attachment using non-sensitive information, then resubmit." };
  if (result.decision === "HUMAN_REVIEW") return { ...common, title: "Human review required",
    message: result.model_invoked ? "The AI model was invoked, but its response is withheld pending review." : "This request has not been sent to the AI model.",
    next_action: "Track the metadata-only review. Approval records a disposition; resubmit under current policies before content can be released." };
  if (result.decision === "BLOCK") return { ...common, title: result.model_invoked ? "Response cannot be released" : "Request cannot be processed", message: "The active governance policies restrict this content." };
  if (result.decision === "REDACT") return { ...common, title: "Sensitive information removed", message: "Sensitive information was removed. A response is shown only after output governance succeeds." };
  return { kind: "success", category: "generic", title: "Request passed governance", message: "The required governance checks passed.", next_action: "Review the response before using or sharing it." };
}
export function canRelease(result: DecisionResult) {
  return ["ALLOW", "REDACT"].includes(result.decision) && Boolean(result.safe_response) &&
    Boolean(result.output && ["ALLOW", "REDACT"].includes(result.output.decision) && result.output.inspection_status !== "INCOMPLETE" &&
      !Object.values(result.output.breakdown || {}).includes("UNKNOWN") &&
      (result.output.decision !== "REDACT" || result.output.revalidated === true)) && messageFor(result).kind !== "technical";
}
export function DecisionNotice({ result, allowReviewLink = true }: { result: DecisionResult; allowReviewLink?: boolean }) {
  const notice = messageFor(result);
  return <section className={`panel decision-notice decision-${notice.kind}`} role={notice.kind === "success" ? "status" : "alert"}
    aria-atomic="true" aria-label="Governance decision guidance">
    <h2>{notice.title}</h2><p>{notice.message}</p><p><strong>Next step: </strong>{notice.next_action}</p>
    {allowReviewLink && result.review_id && result.decision === "HUMAN_REVIEW" && <NavLink className="button" to="/reviews">Open metadata-only review</NavLink>}
    {notice.kind !== "success" && <a className="button" href="#playground-prompt">Revise prompt or attachment</a>}
  </section>;
}

export type DecisionSettings = Partial<Record<"BLOCK" | "HUMAN_REVIEW" | "REDACT", "revise" | "public_example" | "contact_admin">>;
export function DecisionMessageSettings({ value, admin, onChange }: { value: DecisionSettings; admin: boolean; onChange: (value: DecisionSettings) => void }) {
  return <fieldset className="rule" disabled={!admin}>
    <legend>Decision message guidance</legend><p>Optional next-step templates. Protection reasons and review requirements always remain visible. Only Admin users can change these settings.</p>
    {(["BLOCK", "HUMAN_REVIEW", "REDACT"] as const).map(decision => <label key={decision}>{decision} message template
      <select value={value[decision] || ""} onChange={event => {
        const next = { ...value };
        if (event.target.value) next[decision] = event.target.value as DecisionSettings[typeof decision];
        else delete next[decision];
        onChange(next);
      }}>
        <option value="">Default guidance</option><option value="revise">Remove protected details and resubmit</option>
        <option value="public_example">Use a public example or placeholders</option><option value="contact_admin">Contact your policy administrator</option>
      </select>
    </label>)}
  </fieldset>;
}
