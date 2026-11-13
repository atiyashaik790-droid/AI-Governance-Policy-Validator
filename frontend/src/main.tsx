import { WorkspaceSessions } from "./WorkspaceSessions";
import { ReviewContent, REVIEW_REASONS } from "./ReviewContent";
import { UserPortal } from "./UserPortal";
import { MultiSelectDropdown } from "./MultiSelectDropdown";
import React, { useCallback, useEffect, useState, useRef } from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
  Navigate,
  NavLink,
  Route,
  Routes,
  useNavigate,
  useParams,
} from "react-router-dom";
import {
  ShieldCheck,
  LayoutDashboard,
  ScrollText,
  FlaskConical,
  Sparkles,
  History,
  UserCheck,
  FileChartColumn,
  Settings,
  ArrowUpRight,
  Plus,
  Search,
  ChevronRight,
  CircleCheck,
  CircleAlert,
  CircleMinus,
  LogOut,
} from "lucide-react";
import { request, setCsrfToken, loginUrl, ApiError, LOCAL_DEMO } from "./api";
import "./styles.css";
import { ErrorBoundary } from "./ErrorBoundary";
import { WorkspaceProvider, AssignmentControl, useWorkspace, useAssignments, workspaceError, normalizeRecord } from "./workspace";
import type { Page } from "./workspace";

import { DecisionNotice, DecisionMessageSettings, canRelease } from "./DecisionNotice";
import type { DecisionMessage, DecisionSettings } from "./DecisionNotice";
import { AttachmentPicker, attachmentBase64 } from "./AttachmentPicker";
import { CustomCategories } from "./CustomCategories";
import type { CustomCategory } from "./CustomCategories";

type RecordData = Record<string, unknown>;
type Rule = {
  enabled: boolean;
  action: string;
  values?: string[];
  entities?: string[] | null;
  categories?: string[] | null;
};
type Document = {
  schema_version: string;
  name: string;
  description: string;
  rules: Record<string, Rule>;
  custom_categories?: CustomCategory[];
  decision_messages?: DecisionSettings;
};
type Policy = {
  id: string;
  name: string;
  status: string;
  enabled: number;
  draft: string;
  revision: number;
  row_version: number;
  has_published_versions?: boolean;
  is_active?: boolean;
  latest_version_number?: number | null;
};
type Stage = {
  decision: string;
  score?: number;
  breakdown?: Record<string, string>;
  contributions: Record<string, number>;
  findings?: RecordData[];
  safe_text: string | null;
  revalidated: boolean;
  policies?: RecordData[];
  policy_count?: number;
  inspection_status?: string;
};
type Result = {
  decision_notice?: DecisionMessage | null;
  decision: string;
  input: Stage | null;
  output: Stage | null;
  safe_response: string | null;
  model_invoked: boolean;
  generation_status?: "NOT_INVOKED" | "SUCCEEDED" | "FAILED";
  provider_mode: string;
  policy_id?: string;
  policy_name?: string;
  policy_version?: number;
  duration_ms?: number;
  request_id: string;
  review_id?: string;
  provider_error?: string;
  provider_diagnostics?: {
    code: string;
    http_status?: number;
    request_id?: string;
  };
};
export type Summary = {
  total_policies: number;
  active_policies: number;
  total_validations: number;
  pending_reviews: number;
  decisions: Record<string, number>;
  trends: { date: string; score: number }[];
  violations: Record<string, number>;
  contributions: Record<string, number>;
  active_policy: { id: string; version: number } | null;
  window?: { start: string; end_exclusive: string };
  trend_sample_limit?: number;
  policy_evaluation_count?: number;
  compliance?: {
    score: number | null;
    scored_requests: number;
    incomplete_inspections: number;
    trends: { date: string; score: number }[];
    violations: Record<string, number>;
    findings_available: boolean;
    counting: string;
  };
};
const initialDocument: Document = {
  schema_version: "1.0",
  name: "Enterprise Data Protection",
  description: "Protect sensitive enterprise information",
  rules: {
    secret_detection: { enabled: true, action: "BLOCK" },
    pii_detection: { enabled: true, action: "REDACT" },
    moderation: { enabled: true, action: "BLOCK" },
    blocked_keywords: {
      enabled: true,
      values: ["internal-only"],
      action: "BLOCK",
    },
  },
};
const navigation = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/policies", label: "Policy management", icon: ScrollText },
  { to: "/simulator", label: "Policy Validation Studio", icon: FlaskConical },
  { to: "/playground", label: "AI playground", icon: Sparkles },
  { to: "/history", label: "Validation history", icon: History },
  { to: "/reviews", label: "Human review", icon: UserCheck },
  { to: "/reports", label: "Audit & reports", icon: FileChartColumn },
  { to: "/settings", label: "Settings", icon: Settings },
];

// Load endpoint data and surface errors with an explicit retry path.
export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  const reload = useCallback(
    async (signal?: AbortSignal) => {
      if (!path) { setLoading(false); return; }
      setLoading(true);
      setData(null);
      setError("");
      try {
        const next = await request<T>(path, "GET", undefined, { signal });
        if (!signal?.aborted) setData(next);
      } catch (error) {
        if (!signal?.aborted) setError(String(error));
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    [path],
  );
  useEffect(() => {
    const controller = new AbortController();
    void reload(controller.signal);
    return () => controller.abort();
  }, [reload]);
  return { data, error, loading, reload: () => reload() };
}

function useRecordList(path: string) {
  const state = useApi<RecordData[] | Page<RecordData>>(path);
  const rows = Array.isArray(state.data) ? state.data : state.data?.items;
  return { ...state, data: rows?.map(normalizeRecord) || null };
}
// Share the current workspace configuration request within this mounted workspace.
// This is ordinary component state, not a cross-session or authentication cache.
const WorkspaceSettingsContext = React.createContext<ReturnType<
  typeof useApi<RecordData>
> | null>(null);
function WorkspaceSettingsProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const settings = useApi<RecordData>("/api/settings");
  return (
    <WorkspaceSettingsContext.Provider value={settings}>
      {children}
    </WorkspaceSettingsContext.Provider>
  );
}
function useWorkspaceSettings() {
  const settings = React.useContext(WorkspaceSettingsContext);
  if (!settings)
    throw new Error("Workspace settings require an authenticated workspace");
  return settings;
}
// Render an accessible status badge with consistent decision colors.
export function Badge({ value }: { value: string }) {
  return (
    <span className={`badge ${value.toLowerCase()}`}>
      {value.replaceAll("_", " ")}
    </span>
  );
}
// Present operation errors without hiding the page's current state.
function Notice({ message }: { message: string }) {
  return message ? (
    <div role="status" className="notice">
      {message}
    </div>
  ) : null;
}
// Display a loading, retryable error, or actual empty state.
export function DataState({
  loading,
  error,
  empty,
  reload,
}: {
  loading: boolean;
  error: string;
  empty?: boolean;
  reload: () => void;
}) {
  return loading ? (
    <div className="skeleton" aria-label="Loading data" />
  ) : error ? (
    <div className="notice" role="alert">
      {error} <button onClick={reload}>Retry</button>
    </div>
  ) : empty ? (
    <div className="empty">
      No records yet. Run a governed request to get started.
    </div>
  ) : null;
}
// Show live tenant metrics and compliance history.
const Overview = React.lazy(() => import("./Overview"));
// Manage policy drafts and lifecycle using backend-enforced transitions.
function Policies({ role }: { role: string }) {
  const workspace = useWorkspace();
  const assignments = useAssignments();
  const [offset, setOffset] = useState(0),
    [search, setSearch] = useState(""),
    [status, setStatus] = useState(""),
    [enabled, setEnabled] = useState("");
  const canManage = ["Admin", "Policy Owner"].includes(role);
  const canReview = ["Admin", "Reviewer"].includes(role);
  const { data, error, loading, reload } = useApi<Policy[]>(
      `/api/policies?offset=${offset}&limit=20&search=${encodeURIComponent(search)}${status ? `&status=${status}` : ""}${enabled ? `&enabled=${enabled}` : ""}`,
    ),
    [message, setMessage] = useState(""),
    [versions, setVersions] = useState<RecordData[] | null>(null),
    [versionPolicy, setVersionPolicy] = useState(""),
    [versionOffset, setVersionOffset] = useState(0),
    [busy, setBusy] = useState(false);
  async function loadVersions(policyId: string, nextOffset = 0) {
    setBusy(true);
    try {
      const rows = await request<RecordData[]>(
        `/api/policies/${policyId}/versions?limit=20&offset=${nextOffset}`,
      );
      setVersions(rows);
      setVersionPolicy(policyId);
      setVersionOffset(nextOffset);
    } catch (error) {
      setMessage(String(error));
    } finally {
      setBusy(false);
    }
  }
  // Confirm and execute a policy action, then refresh live data.
  async function act(policy: Policy, operation: string) {
    if (busy) return;
    if (
      !confirm(
        operation === "delete"
          ? `Delete “${policy.name}” from Policies? Audit history and published versions will be kept.`
          : `${operation} “${policy.name}”?`,
      )
    )
      return;
    setBusy(true);
    try {
      await request(
        `/api/policies/${policy.id}${operation === "delete" ? "" : `/${operation}`}`,
        operation === "delete" ? "DELETE" : "POST",
        undefined,
        operation === "delete"
          ? { headers: { "If-Match": String(policy.row_version) } }
          : {},
      );
      await reload();
      await workspace.reload();
      setMessage(
        operation === "delete"
          ? "Policy removed from Policies. Audit history is retained."
          : `Policy ${operation} completed.`,
      );
      if (operation === "delete") setVersions(null);
    } catch (error) {
      setMessage(String(error));
    } finally {
      setBusy(false);
    }
  }
  async function disablePolicy(policy: Policy) {
    if (busy || !canManage) return;
    const requiresDeactivation = workspace.data?.mode === "MULTI" && policy.is_active;
    if (requiresDeactivation && role !== "Admin") {
      setMessage("An Admin must deactivate this assignment before the policy can be disabled.");
      return;
    }
    if (!confirm(requiresDeactivation
      ? `Deactivate “${policy.name}” and then disable it? Active enforcement will stop.`
      : `Disable “${policy.name}”? Active enforcement will stop.`)) return;
    setBusy(true);
    try {
      if (requiresDeactivation) await workspace.mutate(`/api/v2/workspace/policy-assignments/${policy.id}`, { active: false });
      await request(`/api/policies/${policy.id}/disable`, "POST");
      await reload();
      await workspace.reload();
      setMessage("Policy disabled.");
    } catch (error) {
      await reload();
      await workspace.reload();
      setMessage(`Policy change was not completed. ${workspaceError(error)}`);
    } finally { setBusy(false); }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">POLICY WORKSPACE</span>
          <h1>Policy management</h1>
          <p>Build, review, and publish immutable governance rules.</p>
        </div>
        {canManage && (
          <NavLink to="/policies/new" className="primary button">
            <Plus size={17} />
            Create policy
          </NavLink>
        )}
        {!canManage && (
          <small>
            Your role can view policies. Admin or Policy Owner access is
            required to change drafts.
          </small>
        )}
      </div>
      <Notice message={message} />
      {workspace.error && <Notice message={workspace.error} />}
      {workspace.data?.mode === "MULTI" && <Notice message={assignments.error} />}
      <section className="panel">
        <div className="toolbar">
          <label className="search">
            <Search size={17} />
            <input
              aria-label="Search policies"
              placeholder="Search all policies…"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setOffset(0);
              }}
            />
          </label>
          <select
            aria-label="Filter status"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setOffset(0);
            }}
          >
            <option value="">All statuses</option>
            {["DRAFT", "SUBMITTED", "APPROVED", "PUBLISHED", "ARCHIVED"].map(
              (value) => (
                <option key={value}>{value}</option>
              ),
            )}
          </select>
        </div>
        <label>
          Enabled filter
          <select
            aria-label="Filter enabled"
            value={enabled}
            onChange={(event) => {
              setEnabled(event.target.value);
              setOffset(0);
            }}
          >
            <option value="">All</option>
            <option value="true">Enabled</option>
            <option value="false">Disabled</option>
          </select>
        </label>
        <DataState {...{ loading, error, reload }} empty={data?.length === 0} />
        <div className="table-wrap policy-table-wrap">
          <table className="policy-table">
            <thead>
              <tr>
                <th>Policy name</th>
                <th>Status</th>
                <th>Version</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {data?.map((policy) => (
                <tr key={policy.id}>
                  <td>
                    <NavLink to={`/policies/${policy.id}`}>
                      {policy.name}
                    </NavLink>
                    {policy.status === "DRAFT" && <small>Draft revision {policy.revision}</small>}
                  </td>
                  <td>
                    <Badge value={policy.is_active && policy.enabled ? "ACTIVE" : policy.has_published_versions || policy.status === "PUBLISHED" ? "INACTIVE" : "DRAFT"} />
                    {policy.status !== "DRAFT" && <small>{policy.status.toLowerCase()}</small>}
                  </td>
                  <td>
                    {policy.latest_version_number ? `Version ${policy.latest_version_number}` : `Draft ${policy.revision}`}
                  </td>
                  <td>
                    <div className="actions">
                      <NavLink className="button" to={`/policies/${policy.id}`}>
                        {canManage ? "Edit" : "View"}
                      </NavLink>
                      {canManage && policy.status !== "ARCHIVED" && (policy.enabled
                        ? <button disabled={busy || (workspace.data?.mode === "MULTI" && Boolean(policy.is_active) && role !== "Admin")} onClick={() => void disablePolicy(policy)}>Disable</button>
                        : <button disabled={busy} onClick={() => void act(policy, "enable")}>Enable</button>)}
                      <button onClick={() => void loadVersions(policy.id)}>History</button>
                      <details className="policy-more-actions"><summary>More</summary><div className="actions">
                      {[
                        ...(canManage && policy.status === "DRAFT"
                          ? ["submit"]
                          : []),
                        ...(canReview && policy.status === "SUBMITTED"
                          ? ["approve", "reject"]
                          : []),
                        ...(canManage && policy.status === "APPROVED"
                          ? ["publish"]
                          : []),
                        ...(canManage && workspace.data?.mode === "LEGACY" &&
                        policy.status === "PUBLISHED" &&
                        policy.enabled
                          ? ["activate"]
                          : []),
                        ...(canManage && policy.status !== "ARCHIVED"
                          ? [
                              ...(policy.is_active ? [] : ["archive"]),
                            ]
                          : []),
                      ].map((operation) => (
                        <button
                          key={operation}
                          disabled={busy}
                          onClick={() => void act(policy, operation)}
                        >
                          {operation}
                        </button>
                      ))}
                      {workspace.data?.mode === "MULTI" && <AssignmentControl policy={policy} role={role}
                        assignment={assignments.data[policy.id]} disabled={busy || assignments.loading || Boolean(assignments.error) || workspace.loading}
                        changed={reload} />}
                      {canManage && (
                        <button
                          disabled={
                            busy ||
                            Boolean(policy.is_active) ||
                            (policy.has_published_versions
                              ? Boolean(policy.enabled)
                              : policy.status !== "DRAFT")
                          }
                          title={
                            policy.is_active
                              ? "Activate another policy before deleting this policy"
                              : policy.has_published_versions && policy.enabled
                                ? "Disable this policy before deleting it"
                                : "Remove from Policies and keep history"
                          }
                          onClick={() => void act(policy, "delete")}
                        >
                          Delete
                        </button>
                      )}
                      </div></details>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <div className="pagination">
        <button
          disabled={!offset}
          onClick={() => setOffset(Math.max(0, offset - 20))}
        >
          Previous
        </button>
        <span>Page {offset / 20 + 1}</span>
        <button
          disabled={!data || data.length < 20}
          onClick={() => setOffset(offset + 20)}
        >
          Next
        </button>
      </div>
      {versions && (
        <section className="panel">
          <div className="panel-heading">
            <h2>Immutable version history</h2>
            <button onClick={() => setVersions(null)}>Close</button>
          </div>
          <p>
            Restoring a version creates a draft and requires approval,
            publication and activation again.
          </p>
          {canManage &&
            versions.map((version) => (
              <button
                key={String(version.id)}
                disabled={busy}
                onClick={async () => {
                  if (
                    !confirm(
                      "Restore this version as a draft? Current enforcement stays on its published snapshot.",
                    )
                  )
                    return;
                  setBusy(true);
                  try {
                    await request(
                      `/api/policies/${version.policy_id}/rollback`,
                      "POST",
                      { version: version.number },
                    );
                    setMessage(
                      "Version restored as draft. Submit for approval before activating.",
                    );
                    await reload();
                  } catch (error) {
                    setMessage(String(error));
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Restore version {String(version.number)} as draft
              </button>
            ))}
          {role === "Admin" && workspace.data?.mode === "MULTI" && versions.map((version) => <button key={`legacy-${version.id}`}
            disabled={busy || workspace.busy || (workspace.data?.active_policy_count || 0) > 1}
            onClick={async () => {
              if (!confirm(`Return to LEGACY using published version ${version.number}? Other active policies must be deactivated first.`)) return;
              try { await workspace.mutate("/api/v2/workspace/policy-mode", { mode: "LEGACY", legacy_version_id: version.id }); await reload(); setVersions(null); }
              catch (error) { setMessage(workspaceError(error)); }
            }}>Use version {String(version.number)} in LEGACY mode</button>)}
          <div className="pagination">
            <button
              disabled={busy || !versionOffset}
              onClick={() =>
                void loadVersions(
                  versionPolicy,
                  Math.max(0, versionOffset - 20),
                )
              }
            >
              Previous versions
            </button>
            <span>Page {versionOffset / 20 + 1}</span>
            <button
              disabled={busy || versions.length < 20}
              onClick={() =>
                void loadVersions(versionPolicy, versionOffset + 20)
              }
            >
              Next versions
            </button>
          </div>
          <ul>{versions.map((version) => <li key={String(version.id)}>Version {String(version.number)} · {String(version.created).slice(0, 19)}</li>)}</ul>
        </section>
      )}
    </>
  );
}
// Provide structured editing with a live versioned JSON preview.
function Editor({ role }: { role: string }) {
  const { id } = useParams(),
    navigate = useNavigate(),
    [document, setDocument] = useState<Document>(initialDocument),
    [message, setMessage] = useState(""),
    [ready, setReady] = useState(!id),
    [saving, setSaving] = useState(false),
    [policyState, setPolicyState] = useState("DRAFT"),
    [loadedVersion, setLoadedVersion] = useState<number | null>(null);
  const capabilities = useApi<{
    available_pii_entities: string[];
    pii_status: string;
    pii_mode: string;
  }>("/api/capabilities");
  const editable =
    ["Admin", "Policy Owner"].includes(role) &&
    !["ARCHIVED", "DELETED"].includes(policyState);
  useEffect(() => {
    const controller = new AbortController();
    setReady(!id);
    setLoadedVersion(null);
    setMessage("");
    setDocument(initialDocument);
    setPolicyState("DRAFT");
    if (id)
      void request<Policy>(`/api/policies/${id}`, "GET", undefined, {
        signal: controller.signal,
      })
        .then((policy) => {
          if (controller.signal.aborted) return;
          setDocument(JSON.parse(policy.draft));
          setPolicyState(policy.status);
          setLoadedVersion(policy.row_version);
          setReady(true);
        })
        .catch((error) => {
          if (!controller.signal.aborted) setMessage(String(error));
        });
    return () => controller.abort();
  }, [id]);
  // Persist a validated draft without modifying published snapshots.
  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (saving || !editable || !ready || (id && loadedVersion === null)) return;
    setSaving(true);
    try {
      await request(
        id ? `/api/policies/${id}` : "/api/policies",
        id ? "PUT" : "POST",
        document,
        id ? { headers: { "If-Match": String(loadedVersion) } } : {},
      );
      navigate("/policies");
    } catch (error) {
      setMessage(String(error));
    } finally {
      setSaving(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">RULE CONFIGURATION</span>
          <h1>{id ? "Edit policy draft" : "Create a policy"}</h1>
          <p>Changes create a draft. Published versions stay immutable.</p>
        </div>
      </div>
      <Notice message={message} />
      {ready && (
        <div className="editor-grid">
          <form className="panel" onSubmit={save}>
            <fieldset className="editor-fields" disabled={!editable || saving}>
              <label>
                Policy name
                <input
                  required
                  maxLength={120}
                  pattern="[\w .\-]+"
                  value={document.name}
                  onChange={(event) =>
                    setDocument({ ...document, name: event.target.value })
                  }
                />
              </label>
              <label>
                Description
                <textarea
                  value={document.description}
                  maxLength={1000}
                  onChange={(event) =>
                    setDocument({
                      ...document,
                      description: event.target.value,
                    })
                  }
                />
              </label>
              {Object.entries(document.rules).map(([name, rule]) => (
                <div className="rule" key={name}>
                  <label className="checkbox">
                    <input
                      type="checkbox"
                      checked={rule.enabled}
                      onChange={(event) =>
                        setDocument({
                          ...document,
                          rules: {
                            ...document.rules,
                            [name]: { ...rule, enabled: event.target.checked },
                          },
                        })
                      }
                    />
                    <strong>{name.replaceAll("_", " ")}</strong>
                  </label>
                  <select
                    aria-label={`${name} action`}
                    value={rule.action}
                    onChange={(event) =>
                      setDocument({
                        ...document,
                        rules: {
                          ...document.rules,
                          [name]: { ...rule, action: event.target.value },
                        },
                      })
                    }
                  >
                    {(name === "moderation"
                      ? ["BLOCK", "HUMAN_REVIEW"]
                      : ["BLOCK", "REDACT", "HUMAN_REVIEW"]
                    ).map((action) => (
                      <option key={action}>{action}</option>
                    ))}
                  </select>
                  {(name === "pii_detection" || name === "moderation") && (
                    <div className="rule-selection">
                      <MultiSelectDropdown
                        label={
                          name === "pii_detection"
                            ? "PII entity selection"
                            : "Moderation categories"
                        }
                        options={
                          name === "pii_detection"
                            ? [
                                "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD",
                                "IN_AADHAAR", "IN_PAN", "IBAN_CODE", "PERSON",
                                "IP_ADDRESS", "US_SSN",
                              ]
                            : [
                                "harassment",
                                "harassment/threatening",
                                "hate",
                                "hate/threatening",
                                "illicit",
                                "illicit/violent",
                                "self-harm",
                                "self-harm/intent",
                                "self-harm/instructions",
                                "sexual",
                                "sexual/minors",
                                "violence",
                                "violence/graphic",
                              ]
                        }
                        selected={
                          rule[
                            name === "pii_detection" ? "entities" : "categories"
                          ] || []
                        }
                        available={
                          name === "pii_detection"
                            ? capabilities.data?.available_pii_entities || []
                            : undefined
                        }
                        unsupportedExplanation={name === "pii_detection" ? (
                          capabilities.data?.pii_mode === "regex"
                            ? "Regex mode supports email, phone, credit card and US SSN. Presidio mode requires the installed English NLP model."
                            : capabilities.data?.pii_status === "UNAVAILABLE"
                              ? "The English Presidio model or recognizer registry is unavailable."
                              : "These detectors have no executable recognizer in the current English pipeline."
                        ) : undefined}
                        allLabel={
                          name === "pii_detection"
                            ? "All installed PII entities (default)"
                            : "All moderation categories (default)"
                        }
                        disabled={!editable || saving}
                        onChange={(values) =>
                          setDocument({
                            ...document,
                            rules: {
                              ...document.rules,
                              [name]: {
                                ...rule,
                                [name === "pii_detection"
                                  ? "entities"
                                  : "categories"]: values.length
                                  ? values
                                  : null,
                              },
                            },
                          })
                        }
                      />
                      <p className="muted">
                        {name === "pii_detection"
                          ? "No selection uses all installed PII entities. Unavailable entities cannot be added."
                          : "No selection uses all provider moderation categories."}
                      </p>
                      {name === "pii_detection" && !capabilities.data && (
                        <p role="status">
                          {capabilities.error ||
                            "Checking detector capabilities…"}
                        </p>
                      )}
                    </div>
                  )}
                  {rule.values && (
                    <label>
                      Blocked words (comma separated)
                      <input
                        value={rule.values.join(",")}
                        onChange={(event) =>
                          setDocument({
                            ...document,
                            rules: {
                              ...document.rules,
                              [name]: {
                                ...rule,
                                values: event.target.value.split(","),
                              },
                            },
                          })
                        }
                      />
                    </label>
                  )}
                </div>
              ))}
              <DecisionMessageSettings value={document.decision_messages || {}} admin={role === "Admin"}
                onChange={decision_messages => setDocument({ ...document, decision_messages })} />
              <CustomCategories categories={document.custom_categories || []} admin={role === "Admin"}
                onChange={custom_categories => setDocument({ ...document, custom_categories })} />
              <p>
                {!editable
                  ? "Read-only: your role or this policy's state does not permit editing."
                  : ""}
              </p>
              <button
                className="primary"
                type="submit"
                disabled={saving || !editable}
              >
                Save draft
              </button>
            </fieldset>
          </form>
          <section className="panel">
            <h2>JSON preview</h2>
            <p>Schema version 1.0 · validated by the backend</p>
            <pre>{JSON.stringify(document, null, 2)}</pre>
          </section>
        </div>
      )}
    </>
  );
}
// Show detector outcomes and findings without rendering raw HTML.
function Inspection({ stage, title, playground = false }: { stage: Stage | null; title: string; playground?: boolean }) {
  if (stage?.policies && playground) return <section className="panel playground-inspection"><h2>{title}</h2>
    <p>{stage.policy_count} policies evaluated · Evidence: {stage.inspection_status}</p>
    <div className="playground-policy-list">{stage.policies.map((policy) => {
      const local = policy.local as RecordData | undefined;
      const findings = Array.isArray(local?.findings) ? local.findings as RecordData[] : [];
      const categories = findings.map(finding => String(finding.category || "control").replaceAll("_", " "));
      const explanation = categories.length ? `${[...new Set(categories)].join(", ")} detected` : policy.inspection_status === "INCOMPLETE" ? "Inspection incomplete" : "Enabled checks passed";
      return <div className="playground-policy-row" key={String(policy.policy_id)}>
        <div><strong>{String(policy.policy_name || "Policy name unavailable")}</strong><small>Version {String(policy.version)} · {explanation}</small></div>
        <Badge value={String(policy.decision)} />
      </div>;
    })}</div>
  </section>;
  if (stage?.policies) return <section className="panel"><h2>{title}</h2>
    <div className="panel-heading"><Badge value={stage.decision} /><strong>{stage.policy_count} policies evaluated</strong></div>
    <p>Evidence: {stage.inspection_status}</p>
    {stage.policies.map((policy) => <details key={String(policy.policy_id)}>
      <summary>{String(policy.policy_name || policy.policy_id)} · {String(policy.version_label || `Published version ${policy.version}`)} · {String(policy.decision)}</summary>
      <pre>{JSON.stringify(policy, null, 2)}</pre>
    </details>)}
  </section>;
  return (
    <section className="panel">
      <h2>{title}</h2>
      {stage ? (
        <>
          <div className="panel-heading">
            <Badge value={stage.decision} />
            {typeof stage.score === "number" && <strong>{stage.score}/100</strong>}
          </div>
          {Object.entries(stage.breakdown || {}).map(([name, value]) => (
            <div className="detector" key={name}>
              <span>{name.replaceAll("_", " ")}</span>
              <Badge value={value} />
            </div>
          ))}
          <p>
            Redaction revalidated:{" "}
            {stage.revalidated ? "yes" : "not applicable / not approved"}
          </p>
          {stage.breakdown?.pii_detection === "FAILED" && (
            <p className="muted">
              PII detected: this control failed compliance. Detector
              unavailability is reported as UNKNOWN.
            </p>
          )}
          {Boolean(stage.findings?.length) && (
            <pre>{JSON.stringify(stage.findings, null, 2)}</pre>
          )}
        </>
      ) : (
        <p>Not invoked.</p>
      )}
    </section>
  );
}
// Execute input governance, model generation, and output inspection through one gateway.
function Playground() {
  const workspace = useWorkspace();
  const settings = useWorkspaceSettings();
  const inFlight = useRef(false);
  const [attachment, setAttachment] = useState<File | null>(null);
  const [stage, setStage] = useState("");
  const sourceReview = new URLSearchParams(window.location.search).get(
    "review",
  );
  const [text, setText] = useState(
      "Explain the benefits of data governance in simple terms.",
    ),
    [result, setResult] = useState<Result | null>(null),
    [rated, setRated] = useState(false),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  // Submit only to the backend; provider credentials never enter the browser.
  async function run(event: React.FormEvent) {
    event.preventDefault();
    if (inFlight.current || !workspace.data || workspace.loading) return;
    inFlight.current = true;
    setBusy(true);
    setMessage("");
    setResult(null);
    setRated(false);
    try {
      setStage(attachment ? "Reading attachment…" : "Inspecting prompt…");
      const documentFields = attachment ? {
        filename: attachment.name, content_type: attachment.type, content_base64: await attachmentBase64(attachment),
      } : {};
      if (attachment) setStage("Extracting document and inspecting complete content…");
      const base = workspace.data.mode === "MULTI" ? "/api/v2/governance" : "/api/governance";
      setResult(await request<Result>(`${base}/${attachment ? "generate-document" : "generate"}`, "POST", {
        text, ...documentFields, ...(sourceReview ? { source_review_id: sourceReview } : {}),
      }, workspace.data.mode === "MULTI" ? { headers: { "If-Match": `"${workspace.data.set_revision}"` } } : {}));
      setStage(attachment ? "Document extraction and governance completed." : "Governance completed.");
    } catch (error) {
      setStage("Request stopped; no content released.");
      setMessage(workspaceError(error));
      await workspace.reload();
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">PROTECTED AI WORKSPACE</span>
          <h1>AI playground</h1>
          <p>Every prompt inspected. Every response governed.</p>
        </div>
        <span className="badge">INPUT → MODEL → OUTPUT</span>
      </div>
      <Notice message={message} />
      {settings.data?.provider_mode === "fixture" && (
        <div role="status" className="notice">
          Local test mode is active. Approved prompts receive the same sample response; no Azure AI generation is used.
        </div>
      )}
      <form className="panel prompt-panel" onSubmit={run}>
        <h2>What would you like to explore?</h2>
        <textarea
          id="playground-prompt"
          aria-label="User prompt"
          value={text}
          maxLength={12000}
          required={!attachment}
          onChange={(event) => setText(event.target.value)}
        />
        <AttachmentPicker file={attachment} disabled={busy} onChange={file => { setAttachment(file); setResult(null); setStage(""); }} />
        {stage && <p role="status">{stage}</p>}
        <div className="toolbar">
          <span className="muted">
            Only approved content reaches the configured model.
          </span>
          <button className="primary" disabled={busy || workspace.loading || !workspace.data}>
            {busy ? "Inspecting…" : "Run governed request"}{" "}
            <ArrowUpRight size={16} />
          </button>
        </div>
        <div className="samples">
          {[
            "Safe prompt",
            "Synthetic secret",
            "Synthetic PII",
          ].map((label, index) => (
            <button
              type="button"
              key={label}
              onClick={() =>
                setText(
                  [
                    "Explain the benefits of data governance in simple terms.",
                    "api_key=sk-test-ABCDEFGHIJKLMNOPQRSTUVWXYZ12345",
                    "Contact test.person@example.com about data governance.",
                  ][index],
                )
              }
            >
              {label}
            </button>
          ))}
        </div>
      </form>
      {busy && <div className="skeleton" />}
      {result && (
        <>
          <DecisionNotice result={result} />
          <div className="result-banner">
            <ShieldCheck />
            <div>
              <strong>Final decision: {result.decision}</strong>
              <p>
                {result.input?.policies || result.output?.policies
                  ? `${result.input?.policy_count || result.output?.policy_count} active published policies evaluated`
                  : `Policy ${result.policy_name || result.policy_id?.slice(0, 8)} · v${result.policy_version} · ${result.duration_ms} ms`}
              </p>
            </div>
            {result.provider_mode === "fixture" && <Badge value="LOCAL TEST FIXTURE" />}
          </div>
          <div className="inspection-grid">
            <Inspection stage={result.input} title="01 · Input inspection" playground />
            <section className="panel">
              <h2>02 · Model gateway</h2>
              {result.provider_error ||
              result.generation_status === "FAILED" ? (
                <CircleAlert className="gateway-icon" />
              ) : result.output ? (
                <CircleCheck className="gateway-icon" />
              ) : (
                <CircleMinus className="gateway-icon" />
              )}
              <h3>
                {result.provider_error || result.generation_status === "FAILED"
                  ? "Generation failed"
                  : result.output && result.model_invoked
                    ? "Generation succeeded"
                    : result.model_invoked
                      ? "Invocation attempted"
                      : "Model not invoked"}
              </h3>
              <p>
                {result.provider_error ||
                  (result.output && result.model_invoked
                    ? "Generated content passed through output inspection. The final policy decision controls release."
                    : "Input approval is required before generation.")}
              </p>
              {result.provider_diagnostics && (
                <p>
                  Provider status: {result.provider_diagnostics.code}
                  {result.provider_diagnostics.http_status
                    ? ` · HTTP ${result.provider_diagnostics.http_status}`
                    : ""}
                  {result.provider_diagnostics.request_id
                    ? ` · Azure request ${result.provider_diagnostics.request_id}`
                    : ""}
                </p>
              )}
              <p className="muted">Provider: {result.provider_mode === "fixture" ? "Local deterministic fixture" : "Azure OpenAI"}</p>
            </section>
            <Inspection stage={result.output} title="03 · Output inspection" playground />
          </div>
          <section className="panel">
            <h2>Safe response</h2>
            <p className="response">
              {canRelease(result) ? result.safe_response :
                "Response withheld. No unvalidated model content was released."}
            </p>
            {result.review_id && (
              <NavLink className="button" to="/reviews">
                Track human review
              </NavLink>
            )}
            <div className="actions">
              <span>Rate the decision:</span>
              {[1, 2, 3, 4, 5].map((rating) => (
                <button
                  key={rating}
                  disabled={rated}
                  onClick={async () => {
                    try {
                      await request("/api/feedback", "POST", {
                        execution_id: result.request_id,
                        rating,
                      });
                      setRated(true);
                      setMessage("Feedback saved.");
                    } catch (error) {
                      setMessage(String(error));
                    }
                  }}
                >
                  {rating}
                </button>
              ))}
            </div>
          </section>
        </>
      )}
    </>
  );
}
// Simulate drafts independently from active policy assignment and generation.
function Simulator() {
  const workspace = useWorkspace();
  const [mode, setMode] = useState<"selected" | "workspace">("selected");
  const [policyOffset, setPolicyOffset] = useState(0),
    [policySearch, setPolicySearch] = useState("");
  const policies = useApi<Policy[]>(
      `/api/policies?limit=20&offset=${policyOffset}&search=${encodeURIComponent(policySearch)}`,
    ),
    [id, setId] = useState(""),
    [text, setText] = useState("Contact demo@example.com"),
    [result, setResult] = useState<Stage | null>(null),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">TEST BEFORE PUBLISHING</span>
          <h1>Policy Validation Studio</h1>
          <p>Validate governance policies before publishing or activating them.</p>
        </div>
      </div>
      <form
        className="panel"
        aria-label="Policy validation"
        onSubmit={async (event) => {
          event.preventDefault();
          setBusy(true);
          setResult(null);
          try {
            setResult(await request(mode === "selected" ? `/api/v2/simulation/policies/${id}` : "/api/v2/simulation/workspace", "POST", { text }));
            setMessage("");
          } catch (error) {
            setMessage(error instanceof Error ? error.message : String(error));
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>Simulation mode
          <select value={mode} onChange={(event) => { setMode(event.target.value as "selected" | "workspace"); setResult(null); }}>
            <option value="selected">Selected policy draft</option>
            {workspace.data?.mode === "MULTI" && <option value="workspace">Active workspace policy set</option>}
          </select>
        </label>
        {mode === "selected" && <label>
          Search policies
          <input
            value={policySearch}
            onChange={(event) => {
              setPolicySearch(event.target.value);
              setPolicyOffset(0);
              setId("");
            }}
          />
        </label>}
        {mode === "selected" && <div className="pagination">
          <button
            type="button"
            disabled={!policyOffset || policies.loading}
            onClick={() => {
              setPolicyOffset(Math.max(0, policyOffset - 20));
              setId("");
            }}
          >
            Previous policies
          </button>
          <span>Page {policyOffset / 20 + 1}</span>
          <button
            type="button"
            disabled={
              policies.loading || !policies.data || policies.data.length < 20
            }
            onClick={() => {
              setPolicyOffset(policyOffset + 20);
              setId("");
            }}
          >
            Next policies
          </button>
        </div>}
        {mode === "selected" && <label>
          Policy draft
          <select
            required
            value={id}
            onChange={(event) => setId(event.target.value)}
          >
            <option value="">Choose policy…</option>
            {policies.data?.map((policy) => (
              <option value={policy.id} key={policy.id}>
                {policy.name}
              </option>
            ))}
          </select>
          {policies.loading && <small className="field-status" role="status">Loading policies…</small>}
          {policies.error && !policies.loading && <span className="field-error" role="alert">
            Policies couldn't be loaded: {policies.error}{" "}
            <button type="button" onClick={() => void policies.reload()}>Try again</button>
          </span>}
        </label>}
        <label>
          Sample prompt
          <textarea
            required
            maxLength={12000}
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
        </label>
        <button className="primary" disabled={busy || !text.trim() || (mode === "selected" && !id) || (mode === "workspace" && workspace.data?.mode !== "MULTI")}>
          Simulate policy
        </button>
        {message && <p className="field-error" role="alert">Validation failed: {message}</p>}
      </form>
      {result && <><p>The decision reflects the strongest action from the evaluated policy rules. Expand each policy for detector findings.</p><Inspection stage={result} title="Simulation only · no AI generation" /></>}
    </>
  );
}
// Keep published snapshots accessible after a policy is removed from the workspace.
function RetainedPolicyHistory({
  policyId,
  close,
}: {
  policyId: string;
  close: () => void;
}) {
  const [offset, setOffset] = useState(0);
  const policy = useApi<Policy>(`/api/policies/${policyId}`);
  const versions = useApi<RecordData[]>(
    `/api/policies/${policyId}/versions?limit=20&offset=${offset}`,
  );
  return (
    <section className="panel">
      <div className="panel-heading">
        <h2>
          Retained policy history{policy.data ? `: ${policy.data.name}` : ""}
        </h2>
        <button onClick={close}>Close policy history</button>
      </div>
      <p>
        This policy was removed from Policies. Published versions remain
        read-only.
      </p>
      <DataState
        loading={versions.loading}
        error={versions.error || policy.error}
        reload={versions.reload}
      />
      {versions.data?.map((version) => (
        <details key={String(version.id)}>
          <summary>
            Published version {String(version.number)} ·{" "}
            {String(version.created).slice(0, 19)}
          </summary>
          <pre>{String(version.document)}</pre>
        </details>
      ))}
      <div className="pagination">
        <button
          disabled={!offset || versions.loading}
          onClick={() => setOffset(Math.max(0, offset - 20))}
        >
          Previous versions
        </button>
        <span>Page {offset / 20 + 1}</span>
        <button
          disabled={
            versions.loading || !versions.data || versions.data.length < 20
          }
          onClick={() => setOffset(offset + 20)}
        >
          Next versions
        </button>
      </div>
    </section>
  );
}
// Present paginated real records with optional review and export actions.
function Records({
  kind,
  role,
}: {
  kind: "history" | "reviews" | "reports";
  role: string;
}) {
  const workspace = useWorkspace();
  const versioned = workspace.data?.multi_policy_available === true;
  const api = versioned ? "/api/v2" : "/api";
  const [offset, setOffset] = useState(0),
    [auditCategory, setAuditCategory] = useState("policy"),
    [retainedPolicyId, setRetainedPolicyId] = useState(""),
    [message, setMessage] = useState(""),
    [details, setDetails] = useState<RecordData | null>(null),
    [busy, setBusy] = useState(false),
    [reason, setReason] = useState(""),
    [assignee, setAssignee] = useState(""),
    [startDate, setStartDate] = useState(""),
    [endDate, setEndDate] = useState("");
  const [appliedDates, setAppliedDates] = useState({ start: "", end: "" });
  const [filterError, setFilterError] = useState("");
  const dateQuery = kind === "reports" ? `${appliedDates.start ? `&start_date=${appliedDates.start}` : ""}${appliedDates.end ? `&end_date=${appliedDates.end}` : ""}` : "";
  const canReview = ["Admin", "Reviewer"].includes(role);
  const path =
    (kind === "history" || (kind === "reports" && auditCategory === "governance"))
      ? `${api}/audit/executions`
      : kind === "reviews"
        ? `${api}/reviews`
        : `${api}/audit/events`;
  const { data, error, loading, reload } = useRecordList(
    `${path}?offset=${offset}&limit=20${kind === "reports" ? `&category=${auditCategory}` : ""}${dateQuery}`,
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">TRACEABLE BY DESIGN</span>
          <h1>
            {kind === "history"
              ? "Validation history"
              : kind === "reviews"
                ? "Human review"
                : "Audit & reports"}
          </h1>
          <p>
            {kind === "reviews"
              ? "Approval records a disposition. Revised content must pass all gates before release."
              : "Sanitized metadata, persisted by the governance gateway."}
          </p>
        </div>
      </div>
      <Notice message={message} />
      {kind === "reports" && (
        <section className="panel">
          <h2>History date filter</h2>
          <p>Dates use UTC, including the entire end date. With one date omitted, the end defaults to today and the start to 89 days before the end. Maximum range: 366 days.</p>
          {filterError && <p role="alert" className="notice">{filterError}</p>}
          <label>
            Start date
            <input
              type="date"
              value={startDate}
              onChange={(event) => setStartDate(event.target.value)}
            />
          </label>
          <label>
            End date
            <input
              type="date"
              value={endDate}
              onChange={(event) => setEndDate(event.target.value)}
            />
          </label>
          <div className="actions">
            <button className="primary" onClick={() => {
              const valid = (value: string) => !value || /^\d{4}-\d{2}-\d{2}$/.test(value) && !value.startsWith("0000") && value === new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10);
              try {
                if (!valid(startDate) || !valid(endDate)) throw new Error();
                if (startDate || endDate) {
                  const end = Date.parse(`${endDate || new Date().toISOString().slice(0, 10)}T00:00:00Z`);
                  const start = startDate ? Date.parse(`${startDate}T00:00:00Z`) : end - 89 * 86400000;
                  if (start > end || start < Date.parse("0001-01-01T00:00:00Z") || end - start > 365 * 86400000 || endDate === "9999-12-31") throw new Error();
                }
                setFilterError(""); setOffset(0); setDetails(null); setRetainedPolicyId("");
                setAppliedDates({ start: startDate, end: endDate });
              } catch { setFilterError("Use valid dates with the start on or before the end, within 366 days."); }
            }}>Apply Filter</button>
            <button onClick={() => { setStartDate(""); setEndDate(""); setAppliedDates({ start: "", end: "" }); setFilterError(""); setOffset(0); setDetails(null); setRetainedPolicyId(""); }}>Clear Filter</button>
          </div>
          {(appliedDates.start || appliedDates.end) && <p role="status">Applied range (UTC): {appliedDates.start || "89 days before end date"} through {appliedDates.end || "today"}.</p>}
        </section>
      )}
      <section className="panel">
        {kind === "reports" && (
          <>
            <div
              className="actions"
              role="group"
              aria-label="Audit history category"
            >
              {[
                ["policy", "Policy history"],
                ["governance", "Governance execution history"],
                ["administration", "Administrative history"],
              ].map(([category, label]) => (
                <button
                  key={category}
                  className={auditCategory === category ? "primary" : ""}
                  aria-pressed={auditCategory === category}
                  onClick={() => {
                    setAuditCategory(category);
                    setOffset(0);
                    setDetails(null);
                    setRetainedPolicyId("");
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
            <h2>
              {auditCategory === "policy"
                ? "Policy history"
                : auditCategory === "governance"
                  ? "Governance execution history"
                  : "Administrative history"}
            </h2>
            {!loading && !error && data?.length === 0 && (
              <p role="status">{appliedDates.start || appliedDates.end ? "No records found for the selected date range" : "No events in this history yet."}</p>
            )}
          </>
        )}
        <DataState
          {...{ loading, error, reload }}
          empty={kind !== "reports" && data?.length === 0}
        />
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Record</th>
                <th>Timestamp</th>
                {(kind === "history" || kind === "reports") && <>
                  {(kind === "history" || auditCategory !== "administration") && <th>Policy name(s)</th>}
                  <th>{kind === "history" || auditCategory === "governance" ? "Executed By" : "Actor"}</th>
                  <th>Role at event time</th>
                </>}
                <th>Status / event</th>
                {(kind === "history" || (kind === "reports" && auditCategory === "governance")) && <th>Safe violation category</th>}
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {data?.map((row) => (
                <tr key={String(row.id)}>
                  <td className="mono">{String(row.id).slice(0, 8)}
                    {Boolean(row.execution_mode || (row.execution as RecordData | undefined)?.execution_mode) && <small>
                      {String(row.execution_mode || (row.execution as RecordData)?.execution_mode)} · {String(row.policy_evaluation_count ?? (row.execution as RecordData)?.policy_evaluation_count)} policy evaluations
                    </small>}
                  </td>
                  <td>{String(row.created).slice(0, 19)}</td>
                  {(kind === "history" || kind === "reports") && <>
                    {(kind === "history" || auditCategory !== "administration") && <td>{Array.isArray(row.policy_names) ? row.policy_names.join(", ") : String(row.policy_name || "Not recorded")}</td>}
                    <td>{String(row.actor || "Not recorded")}</td><td>{String(row.actor_role || "Historical role unavailable")}</td>
                  </>}
                  <td>
                    <Badge
                      value={String(row.decision || row.status || row.action)}
                    />
                  </td>
                  {(kind === "history" || (kind === "reports" && auditCategory === "governance")) && <td>{Array.isArray(row.violation_categories) ? row.violation_categories.join(", ") : "Not recorded"}</td>}
                  <td>
                    <div className="actions">
                      <button
                        onClick={async () => {
                          if (kind !== "reviews" && !((kind === "history" || (kind === "reports" && auditCategory === "governance")) && versioned)) {
                            setDetails(row);
                            return;
                          }
                          setDetails(null);
                          try {
                            const detail = await request<RecordData>(
                              (kind === "history" || (kind === "reports" && auditCategory === "governance")) ? `${api}/audit/executions/${row.id}` : `${api}/reviews/${row.id}`,
                            );
                            setDetails(normalizeRecord(detail));
                            const assignment =
                              detail.assignment as RecordData | null;
                            setAssignee(
                              String(assignment?.assigned_reviewer || detail.assigned_reviewer || ""),
                            );
                          } catch (error) {
                            setMessage(String(error));
                          }
                        }}
                      >
                        {kind === "reviews" ? "Open review" : "Inspect metadata"}
                      </button>
                      {kind === "reports" &&
                        row.action === "policy.removed" && (
                          <button
                            onClick={() =>
                              setRetainedPolicyId(String(row.resource))
                            }
                          >
                            View retained versions
                          </button>
                        )}
                      {kind === "reviews" &&
                        canReview &&
                        row.status === "PENDING" &&
                        ["approve", "reject"].map((operation) => (
                          <button
                            key={operation}
                            disabled={busy}
                            onClick={async () => {
                              if (busy) return;
                              if (
                                !confirm(
                                  `${operation} review? This never releases held content.`,
                                )
                              )
                                return;
                              setBusy(true);
                              setDetails(null);
                              try {
                                await request(
                                  `${api}/reviews/${row.id}/${operation}`,
                                  "POST",
                                  { reason },
                                );
                                setDetails(null);
                                setMessage(`Review ${operation} recorded.`);
                                await reload();
                              } catch (error) {
                                setMessage(String(error));
                              } finally {
                                setBusy(false);
                              }
                            }}
                          >
                            {operation}
                          </button>
                        ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="pagination">
          <button
            disabled={!offset}
            onClick={() => setOffset(Math.max(0, offset - 20))}
          >
            Previous
          </button>
          <span>Page {offset / 20 + 1}</span>
          <button
            disabled={!data || data.length < 20}
            onClick={() => setOffset(offset + 20)}
          >
            Next
          </button>
        </div>
      </section>
      {kind === "reports" && retainedPolicyId && (
        <RetainedPolicyHistory
          key={retainedPolicyId}
          policyId={retainedPolicyId}
          close={() => setRetainedPolicyId("")}
        />
      )}
      {kind === "reviews" && (
        <section className="panel">
          <h2>Review decision note</h2>
          <label>
            Reason (metadata only; omit sensitive content)
            <select value={reason} onChange={(event) => setReason(event.target.value)}>
              <option value="">Select a safe review note</option>
              {REVIEW_REASONS.map((value) => <option key={value}>{value}</option>)}
            </select>
          </label>
          <p>
            Approval never releases held content. The author must revise and
            resubmit through every current gate.
          </p>
        </section>
      )}
      {details && (
        <section className="panel">
          <div className="panel-heading">
            <h2>{kind === "reviews" ? "Review case" : "Record metadata"}</h2>
            <button onClick={() => setDetails(null)}>Close</button>
          </div>
          {kind === "reviews" && (
            <>
              <ReviewContent key={JSON.stringify([details.id, details.row_version, details.status, details.assigned_reviewer, details.assignment, details.protected_content])} record={details} refreshPath={`${api}/reviews/${details.id}`} onRefresh={(value) => setDetails(normalizeRecord(value))} />
              {details.status === "PENDING" && canReview && (
                <>
                  <label>
                    Assigned reviewer username
                    <input
                      value={assignee}
                      maxLength={100}
                      onChange={(event) => setAssignee(event.target.value)}
                    />
                  </label>
                  <button
                    disabled={busy}
                    onClick={async () => {
                      setBusy(true);
                      setDetails(null);
                      try {
                        await request(
                          `${api}/reviews/${details.id}/assignment`,
                          "PUT",
                          { assigned_reviewer: assignee, reason },
                        );
                        setMessage("Review assignment recorded.");
                        setDetails(normalizeRecord(await request<RecordData>(`${api}/reviews/${details.id}`)));
                      } catch (error) {
                        setMessage(String(error));
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    Save assignment
                  </button>
                </>
              )}
              {details.status !== "PENDING" &&
                ["Admin", "Developer", "Policy Owner"].includes(role) && (
                  <NavLink
                    className="button"
                    to={`/playground?review=${details.id}`}
                  >
                    Submit revised text for reinspection
                  </NavLink>
                )}
            </>
          )}
          <details><summary>Technical metadata</summary><pre>
            {JSON.stringify(
              {
                ...details,
                ...(typeof details.metadata_json === "string"
                  ? { metadata_json: JSON.parse(details.metadata_json) }
                  : {}),
              },
              null,
              2,
            )}
          </pre></details>
        </section>
      )}
    </>
  );
}
// Settings shows only workspace session management; diagnostics stay available server-side.

type SettingsIdentity = { user: string; role: string; tenant: string; expires_at?: string };
function Configuration() {
  const { data, error, loading, reload } = useWorkspaceSettings();
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">WORKSPACE SETTINGS</span>
          <h1>Workspace Sessions</h1>
          <p>Review active, expired and revoked sign-in sessions for this workspace.</p>
        </div>
      </div>
      <DataState {...{ loading, error, reload }} />
      {data && <div className="settings-page">
        {data.role === "Admin" ? <WorkspaceSessions mode={data.sso_enabled === false ? "demo" : "sso"} /> : <section className="panel" aria-labelledby="sessions-heading">
          <h2 id="sessions-heading">Session management</h2><p>Session management is available to workspace administrators.</p>
        </section>}
      </div>}
    </>
  );
}
// Restore only the server-managed Microsoft session before loading workspace data.
export function App() {
  const sessionKnown = useRef(false);
  const sessionDeadline = useRef<number | null>(null);
  const [authenticated, setAuthenticated] = useState(false),
    [error, setError] = useState(""),
    [loggingIn, setLoggingIn] = useState(false);
  const [restoring, setRestoring] = useState(true);
  const [ssoReady, setSsoReady] = useState(false);
  const [checkingSso, setCheckingSso] = useState(true);
  const [statusError, setStatusError] = useState("");
  const [demoCredential, setDemoCredential] = useState("");
  const [restoreAttempt, setRestoreAttempt] = useState(0);
  const [identity, setIdentity] = useState<SettingsIdentity | null>(null);
  useEffect(() => {
    if (!LOCAL_DEMO) sessionStorage.removeItem("governance-token");
    const controller = new AbortController();
    const options = {
      signal: controller.signal,
      timeoutMs: 10000,
      notifyUnauthorized: false,
    };
    const reason = new URLSearchParams(window.location.search).get(
      "auth_error",
    );
    if (reason) {
      setError(
        reason === "access_denied"
          ? "Access denied. Ask your workspace administrator for authorized membership."
          : "Microsoft sign-in could not be completed. Please try again.",
      );
      window.history.replaceState({}, "", window.location.pathname);
    }
    // Availability and cookie authentication are independent. A valid /me response
    // unlocks the workspace without waiting for the public status request.
    void request<{ configured: boolean; demo_login_enabled: boolean }>(
      "/api/sso/status",
      "GET",
      undefined,
      options,
    )
      .then((status) => {
        if (!controller.signal.aborted) setSsoReady(status.configured || (LOCAL_DEMO && status.demo_login_enabled));
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setStatusError(
            "Sign-in service is unavailable. Please try again later.",
          );
      })
      .finally(() => {
        if (!controller.signal.aborted) setCheckingSso(false);
      });
    void request<{
      user: string;
      role: string;
      tenant: string;
      csrf_token: string;
      expires_at?: string;
      server_now?: string;
    }>(LOCAL_DEMO ? "/api/auth/me" : "/api/sso/me", "GET", undefined, options)
      .then((user) => {
        if (controller.signal.aborted) return;
        if (!["Admin", "User", "Policy Owner", "Developer", "Reviewer", "Auditor"].includes(user.role) ||
            !user.user?.trim() || !user.tenant?.trim() || !user.csrf_token?.trim())
          throw new Error("Authorized membership is required");
        sessionKnown.current = true;
        const remaining = Date.parse(user.expires_at || "") - Date.parse(user.server_now || "");
        sessionDeadline.current = Number.isFinite(remaining) ? performance.now() + remaining : null;
        setCsrfToken(user.csrf_token);
        setIdentity(user);
        setAuthenticated(true);
        setError("");
      })
      .catch((error) => {
        if (!controller.signal.aborted && error instanceof ApiError && error.status === 401) {
          if (error.sessionReason === "expired") setError("Your session has expired. Please sign in again.");
          else if (error.sessionReason === "ended") setError("Your session has ended. Please sign in again.");
          return;
        }
        if (!controller.signal.aborted)
          setError(
            "Your session could not be checked. Retry the connection to continue.",
          );
      })
      .finally(() => {
        if (!controller.signal.aborted) setRestoring(false);
      });
    return () => controller.abort();
  }, [restoreAttempt]);
  useEffect(() => {
    const ended = (event: Event) => {
      const reason = (event as CustomEvent<{ reason?: string }>).detail?.reason;
      const previouslyAuthenticated = sessionKnown.current;
      const expired = reason === "expired" || (reason !== "ended" && sessionDeadline.current !== null && performance.now() >= sessionDeadline.current);
      sessionKnown.current = false;
      sessionDeadline.current = null;
      setAuthenticated(false);
      setIdentity(null);
      setCsrfToken("");
      if (previouslyAuthenticated) setError(expired ? "Your session has expired. Please sign in again." : "Your session has ended. Please sign in again.");
    };
    window.addEventListener("governance-session-ended", ended);
    return () => window.removeEventListener("governance-session-ended", ended);
  }, []);
  if (!authenticated)
    return (
      <div className="login">
        <div className="login-brand">
          <ShieldCheck size={48} />
          <h1>Governance Studio</h1>
          <p>Secure Enterprise AI Governance Platform</p>
        </div>
        <section className="panel" aria-labelledby="sso-title">
          <span className="eyebrow">SECURE WORKSPACE ACCESS</span>
          <h2 id="sso-title">Welcome to Governance Studio</h2>
          <p>{LOCAL_DEMO ? "Local demo preview. Provider mode is shown after sign-in." :
            "Use your organization's Microsoft account to securely access your workspace."}</p>
          <Notice message={error || statusError} />
          {restoring && <p role="status">Checking sign-in…</p>}
          {checkingSso && (
            <p role="status">Checking Microsoft sign-in availability…</p>
          )}
          {!checkingSso && !ssoReady && (
            <p role="status">
              {LOCAL_DEMO ? "Local demo login is unavailable." : "Microsoft sign-in is not available. Contact your application administrator."}
            </p>
          )}
          {LOCAL_DEMO && <label>Local demo credential<input type="password" autoComplete="off" value={demoCredential}
            onChange={event => setDemoCredential(event.target.value)} /></label>}
          <button
            className="primary"
            aria-busy={loggingIn}
            disabled={!ssoReady || loggingIn || restoring || (LOCAL_DEMO && !demoCredential)}
            onClick={() => {
              setLoggingIn(true);
              if (!LOCAL_DEMO) { window.location.assign(loginUrl()); return; }
              void request<{ access_token: string }>("/api/auth/session", "POST", undefined,
                { headers: { Authorization: `Bearer ${demoCredential}` } })
                .then(result => { sessionStorage.setItem("governance-token", result.access_token); setDemoCredential(""); setRestoreAttempt(value => value + 1); })
                .catch(failure => setError((failure as Error).message))
                .finally(() => setLoggingIn(false));
            }}
          >
            {LOCAL_DEMO ? "Enter local preview" : "Sign in"}
          </button>
          {!restoring &&
            !checkingSso &&
            (error || statusError || !ssoReady) && (
              <button
                onClick={() => {
                  setError("");
                  setStatusError("");
                  setSsoReady(false);
                  setRestoring(true);
                  setCheckingSso(true);
                  setRestoreAttempt((attempt) => attempt + 1);
                }}
              >
                Retry connection
              </button>
            )}
          <small>
            Access follows your approved workspace membership. Your organization
            manages MFA and sign-in policies.
          </small>
        </section>
      </div>
    );
  if (identity?.role === "User") return <BrowserRouter><WorkspaceProvider><Routes>
    <Route path="/chat" element={<UserPortal account={identity.user} sessionError={error} onSignOut={async () => {
      try {
        const result = LOCAL_DEMO ? null : await request<{ logout_url: string }>("/api/sso/logout", "POST");
        if (LOCAL_DEMO) { await request("/api/auth/logout", "POST"); sessionStorage.removeItem("governance-token"); }
        sessionKnown.current = false; sessionDeadline.current = null; setError("");
        setCsrfToken(""); setIdentity(null); setAuthenticated(false); if (result) window.location.assign(result.logout_url);
      } catch { setError("Sign out could not be confirmed. Please retry; your server session may still be active."); }
    }} />} />
    <Route path="*" element={<Navigate to="/chat" replace />} />
  </Routes></WorkspaceProvider></BrowserRouter>;
  return (
    <WorkspaceSettingsProvider>
      <WorkspaceProvider>
      <BrowserRouter>
        <aside className="sidebar">
          <div className="brand">
            <span>
              <ShieldCheck size={24} />
            </span>
            <div>
              Governance<small>STUDIO</small>
            </div>
          </div>
          <span className="nav-label">WORKSPACE</span>
          <nav>
            {navigation.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.to === "/"}>
                <item.icon size={18} />
                {item.label}
                {item.to === "/playground" && <span className="nav-dot" />}
              </NavLink>
            ))}
          </nav>
          <div className="sidebar-bottom">
            <ShieldCheck size={21} />
            <strong>Govern with confidence</strong>
            <p>Policy enforcement at every step of the AI lifecycle.</p>
            <small>DEMO WORKSPACE · v1.1</small>
          </div>
        </aside>
        <div className="workspace">
          <header>
            <div className="breadcrumbs">
              Workspace <ChevronRight size={13} />{" "}
              <strong>AI Governance</strong>
            </div>
            <div className="header-right">
              <span className="local-pill">
                <i />
                {identity
                  ? `${identity.user} · ${identity.role} · ${identity.tenant}`
                  : "Governed workspace"}
              </span>
              <button
                title="Sign out"
                onClick={async () => {
                  try {
                    const result = LOCAL_DEMO ? null : await request<{ logout_url: string }>("/api/sso/logout", "POST");
                    if (LOCAL_DEMO) { await request("/api/auth/logout", "POST"); sessionStorage.removeItem("governance-token"); }
                    sessionKnown.current = false;
                    sessionDeadline.current = null;
                    setError("");
                    setCsrfToken("");
                    setIdentity(null);
                    setAuthenticated(false);
                    if (result) window.location.assign(result.logout_url);
                  } catch {
                    setError(
                      "Sign out could not be confirmed. Please retry; your server session may still be active.",
                    );
                  }
                }}
              >
                <LogOut size={17} />
              </button>
              <span className="avatar">GV</span>
            </div>
          </header>
          <main>
            <Notice message={error} />
            <React.Suspense
              fallback={<div className="skeleton" aria-label="Loading page" />}
            >
              <Routes>
                <Route path="/" element={<Overview />} />
                <Route
                  path="/policies"
                  element={<Policies role={identity?.role || ""} />}
                />
                <Route path="/categories" element={<Navigate to="/" replace />} />
                <Route
                  path="/policies/new"
                  element={<Editor key="new" role={identity?.role || ""} />}
                />
                <Route
                  path="/policies/:id"
                  element={
                    <Editor key="existing" role={identity?.role || ""} />
                  }
                />
                <Route path="/simulator" element={<Simulator />} />
                <Route path="/playground" element={<Playground />} />
                <Route
                  path="/history"
                  element={
                    <Records
                      key="history"
                      kind="history"
                      role={identity?.role || ""}
                    />
                  }
                />
                <Route
                  path="/reviews"
                  element={
                    <Records
                      key="reviews"
                      kind="reviews"
                      role={identity?.role || ""}
                    />
                  }
                />
                <Route path="/analytics" element={<Navigate to="/" replace />} />
                <Route
                  path="/reports"
                  element={
                    <Records
                      key="reports"
                      kind="reports"
                      role={identity?.role || ""}
                    />
                  }
                />
                <Route path="/settings" element={<Configuration />} />
                <Route path="*" element={<p>Page not found.</p>} />
              </Routes>
            </React.Suspense>
            <footer>
              <ShieldCheck size={14} /> Governance signals are heuristic
              controls, not legal compliance certification.
            </footer>
          </main>
        </div>
      </BrowserRouter>
      </WorkspaceProvider>
    </WorkspaceSettingsProvider>
  );
}

const root = document.getElementById("root");
if (root)
  createRoot(root).render(
    <React.StrictMode>
      <ErrorBoundary>
        <App />
      </ErrorBoundary>
    </React.StrictMode>,
  );
