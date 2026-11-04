import { MultiSelectDropdown } from "./MultiSelectDropdown";
import React, { useCallback, useEffect, useState, useRef } from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
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
  ChartNoAxesCombined,
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
import { request, getToken } from "./api";
import "./styles.css";
import { ErrorBoundary } from "./ErrorBoundary";

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
};
type Stage = {
  decision: string;
  score: number;
  breakdown: Record<string, string>;
  contributions: Record<string, number>;
  findings: RecordData[];
  safe_text: string | null;
  revalidated: boolean;
};
type Result = {
  decision: string;
  input: Stage | null;
  output: Stage | null;
  safe_response: string | null;
  model_invoked: boolean;
  generation_status?: "NOT_INVOKED" | "SUCCEEDED" | "FAILED";
  provider_mode: string;
  policy_id: string;
  policy_name?: string;
  policy_version: number;
  duration_ms: number;
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
  { to: "/simulator", label: "Policy simulator", icon: FlaskConical },
  { to: "/playground", label: "AI playground", icon: Sparkles },
  { to: "/history", label: "Validation history", icon: History },
  { to: "/reviews", label: "Human review", icon: UserCheck },
  {
    to: "/analytics",
    label: "Compliance analytics",
    icon: ChartNoAxesCombined,
  },
  { to: "/reports", label: "Audit & reports", icon: FileChartColumn },
  { to: "/settings", label: "Settings", icon: Settings },
];

// Load endpoint data and surface errors with an explicit retry path.
export function useApi<T>(path: string) {
  const [data, setData] = useState<T | null>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  const reload = useCallback(
    async (signal?: AbortSignal) => {
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
function Policies() {
  const [offset, setOffset] = useState(0),
    [search, setSearch] = useState(""),
    [status, setStatus] = useState(""),
    [enabled, setEnabled] = useState("");
  const identity = useApi<RecordData>("/api/settings");
  const role = String(identity.data?.role || "");
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
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Policy name</th>
                <th>Status</th>
                <th>Enabled</th>
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
                    <small>Draft revision {policy.revision}</small>
                    {policy.is_active && (
                      <small>
                        Active assignment — activate another policy before
                        deleting.
                      </small>
                    )}
                  </td>
                  <td>
                    <Badge value={policy.status} />
                  </td>
                  <td>
                    <Badge value={policy.enabled ? "ENABLED" : "DISABLED"} />
                  </td>
                  <td>
                    <div className="actions">
                      <NavLink className="button" to={`/policies/${policy.id}`}>
                        View / edit
                      </NavLink>
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
                        ...(canManage &&
                        policy.status === "PUBLISHED" &&
                        policy.enabled
                          ? ["activate"]
                          : []),
                        ...(canManage && policy.status !== "ARCHIVED"
                          ? [
                              policy.enabled ? "disable" : "enable",
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
                      <button
                        onClick={async () => {
                          try {
                            await loadVersions(policy.id);
                          } catch (error) {
                            setMessage(String(error));
                          }
                        }}
                      >
                        History
                      </button>
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
          <pre>{JSON.stringify(versions, null, 2)}</pre>
        </section>
      )}
    </>
  );
}
// Provide structured editing with a live versioned JSON preview.
function Editor() {
  const { id } = useParams(),
    navigate = useNavigate(),
    [document, setDocument] = useState<Document>(initialDocument),
    [message, setMessage] = useState(""),
    [ready, setReady] = useState(!id),
    [saving, setSaving] = useState(false),
    [policyState, setPolicyState] = useState("DRAFT"),
    [loadedVersion, setLoadedVersion] = useState<number | null>(null);
  const identity = useApi<RecordData>("/api/settings");
  const capabilities = useApi<{
    available_pii_entities: string[];
    pii_status: string;
  }>("/api/capabilities");
  const editable =
    ["Admin", "Policy Owner"].includes(String(identity.data?.role)) &&
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
                                "EMAIL_ADDRESS",
                                "PHONE_NUMBER",
                                "CREDIT_CARD",
                                "US_SSN",
                                "PERSON",
                                "LOCATION",
                                "IP_ADDRESS",
                                "URL",
                                "DATE_TIME",
                                "IBAN_CODE",
                                "US_BANK_NUMBER",
                                "US_DRIVER_LICENSE",
                                "US_PASSPORT",
                                "US_ITIN",
                                "UK_NHS",
                                "MEDICAL_LICENSE",
                                "CRYPTO",
                                "NRP",
                                "AU_ABN",
                                "AU_ACN",
                                "AU_TFN",
                                "AU_MEDICARE",
                                "IN_PAN",
                                "IN_AADHAAR",
                                "IN_VEHICLE_REGISTRATION",
                                "SG_NRIC_FIN",
                                "ES_NIF",
                                "IT_FISCAL_CODE",
                                "IT_DRIVER_LICENSE",
                                "IT_VAT_CODE",
                                "IT_PASSPORT",
                                "IT_IDENTITY_CARD",
                                "PL_PESEL",
                                "FI_PERSONAL_ID",
                                "KR_RRN",
                                "TH_TNIN",
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
function Inspection({ stage, title }: { stage: Stage | null; title: string }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      {stage ? (
        <>
          <div className="panel-heading">
            <Badge value={stage.decision} />
            <strong>{stage.score}/100</strong>
          </div>
          {Object.entries(stage.breakdown).map(([name, value]) => (
            <div className="detector" key={name}>
              <span>{name.replaceAll("_", " ")}</span>
              <Badge value={value} />
            </div>
          ))}
          <p>
            Redaction revalidated:{" "}
            {stage.revalidated ? "yes" : "not applicable / not approved"}
          </p>
          {stage.breakdown.pii_detection === "FAILED" && (
            <p className="muted">
              PII detected: this control failed compliance. Detector
              unavailability is reported as UNKNOWN.
            </p>
          )}
          {stage.findings.length > 0 && (
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
    setBusy(true);
    setMessage("");
    setResult(null);
    setRated(false);
    try {
      setResult(
        await request<Result>("/api/governance/generate", "POST", {
          text,
          ...(sourceReview ? { source_review_id: sourceReview } : {}),
        }),
      );
    } catch (error) {
      setMessage(String(error));
    } finally {
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
      <form className="panel prompt-panel" onSubmit={run}>
        <h2>What would you like to explore?</h2>
        <textarea
          aria-label="User prompt"
          value={text}
          maxLength={12000}
          required
          onChange={(event) => setText(event.target.value)}
        />
        <div className="toolbar">
          <span className="muted">
            Only approved content reaches the configured model.
          </span>
          <button className="primary" disabled={busy}>
            {busy ? "Inspecting…" : "Run governed request"}{" "}
            <ArrowUpRight size={16} />
          </button>
        </div>
        <div className="samples">
          {[
            "Safe prompt",
            "Synthetic secret",
            "Synthetic PII",
            "Fixture moderation",
            "Fixture failure",
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
                    "[MODERATION_FLAG]",
                    "[MODERATION_UNAVAILABLE]",
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
          <div className="result-banner">
            <ShieldCheck />
            <div>
              <strong>Final decision: {result.decision}</strong>
              <p>
                Policy {result.policy_name || result.policy_id.slice(0, 8)} · v
                {result.policy_version} · {result.duration_ms} ms
              </p>
            </div>
            <Badge
              value={
                result.provider_mode === "fixture"
                  ? "LOCAL TEST FIXTURE"
                  : "LIVE PROVIDER MODE"
              }
            />
          </div>
          <div className="inspection-grid">
            <Inspection stage={result.input} title="01 · Input inspection" />
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
              <Badge value={result.provider_mode} />
            </section>
            <Inspection stage={result.output} title="03 · Output inspection" />
          </div>
          <section className="panel">
            <h2>Safe response</h2>
            <p className="response">
              {result.safe_response ||
                "Response withheld. No unvalidated model content was released."}
            </p>
            <small>Request {result.request_id}</small>
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
          <h1>Policy simulator</h1>
          <p>Evaluate a draft without calling the generation provider.</p>
        </div>
      </div>
      <DataState
        loading={policies.loading}
        error={policies.error}
        reload={policies.reload}
      />
      <Notice message={message} />
      <form
        className="panel"
        onSubmit={async (event) => {
          event.preventDefault();
          setBusy(true);
          setResult(null);
          try {
            setResult(
              await request(`/api/policies/${id}/simulate`, "POST", { text }),
            );
            setMessage("");
          } catch (error) {
            setMessage(String(error));
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Search policies
          <input
            value={policySearch}
            onChange={(event) => {
              setPolicySearch(event.target.value);
              setPolicyOffset(0);
              setId("");
            }}
          />
        </label>
        <div className="pagination">
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
        </div>
        <label>
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
        </label>
        <label>
          Sample prompt
          <textarea
            required
            maxLength={12000}
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
        </label>
        <button className="primary" disabled={busy}>
          Simulate policy
        </button>
      </form>
      {result && <Inspection stage={result} title="Simulation results" />}
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
function Records({ kind }: { kind: "history" | "reviews" | "reports" }) {
  const [offset, setOffset] = useState(0),
    [auditCategory, setAuditCategory] = useState("policy"),
    [retainedPolicyId, setRetainedPolicyId] = useState(""),
    [message, setMessage] = useState(""),
    [details, setDetails] = useState<RecordData | null>(null),
    [busy, setBusy] = useState(false),
    [reason, setReason] = useState(""),
    [assignee, setAssignee] = useState(""),
    [startDate, setStartDate] = useState(""),
    [endDate, setEndDate] = useState(""),
    [exportOffset, setExportOffset] = useState(0);
  const exportKeys = useRef<Record<string, string>>({});
  const identity = useApi<RecordData>("/api/settings");
  const canReview = ["Admin", "Reviewer"].includes(String(identity.data?.role));
  const canExport = ["Admin", "Auditor"].includes(String(identity.data?.role));
  const path =
    kind === "history"
      ? "/api/audit/executions"
      : kind === "reviews"
        ? "/api/reviews"
        : "/api/audit/events";
  const { data, error, loading, reload } = useApi<RecordData[]>(
    `${path}?offset=${offset}&limit=20${kind === "reports" ? `&category=${auditCategory}` : ""}`,
  );
  const exports = useApi<
    RecordData[] | { count: number; average: number | null }
  >(
    kind === "reports"
      ? `/api/reports/exports?limit=20&offset=${exportOffset}`
      : "/api/feedback/summary",
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
        {kind === "reports" && canExport && (
          <div className="actions">
            {["json", "csv"].map((format) => (
              <button
                className="primary"
                key={format}
                disabled={busy}
                onClick={async () => {
                  if (busy) return;
                  setBusy(true);
                  try {
                    const payload = {
                      format,
                      ...(startDate ? { start_date: startDate } : {}),
                      ...(endDate ? { end_date: endDate } : {}),
                    };
                    const signature = JSON.stringify(payload);
                    const key = (exportKeys.current[signature] ||=
                      crypto.randomUUID());
                    const report = await request<RecordData>(
                      "/api/reports/export",
                      "POST",
                      { ...payload, idempotency_key: key },
                    );
                    if (report.state === "COMPLETED")
                      delete exportKeys.current[signature];
                    setMessage(`ADLS export: ${report.status}`);
                    void exports.reload();
                    void reload();
                  } catch (error) {
                    setMessage(String(error));
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Export {format.toUpperCase()}
              </button>
            ))}
          </div>
        )}
      </div>
      <Notice message={message} />
      {kind === "reports" && (
        <section className="panel">
          <h2>Export window</h2>
          <p>
            Exports include all audit categories within the selected window.
          </p>
          <p>
            Default: last 90 days. Maximum: 366 days, 10,000 records and 5 MB
            with default settings. Check history after an uncertain result.
          </p>
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
          {!canExport && (
            <p>Admin or Auditor access is required to export reports.</p>
          )}
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
              <p role="status">No events in this history yet.</p>
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
                <th>Status / event</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {data?.map((row) => (
                <tr key={String(row.id)}>
                  <td className="mono">{String(row.id).slice(0, 8)}</td>
                  <td>{String(row.created).slice(0, 19)}</td>
                  <td>
                    <Badge
                      value={String(row.decision || row.status || row.action)}
                    />
                  </td>
                  <td>
                    <div className="actions">
                      <button
                        onClick={async () => {
                          if (kind !== "reviews") {
                            setDetails(row);
                            return;
                          }
                          try {
                            const detail = await request<RecordData>(
                              `/api/reviews/${row.id}`,
                            );
                            setDetails(detail);
                            const assignment =
                              detail.assignment as RecordData | null;
                            setAssignee(
                              String(assignment?.assigned_reviewer || ""),
                            );
                          } catch (error) {
                            setMessage(String(error));
                          }
                        }}
                      >
                        Inspect metadata
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
                              try {
                                await request(
                                  `/api/reviews/${row.id}/${operation}`,
                                  "POST",
                                  { reason },
                                );
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
            <textarea
              maxLength={1000}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </label>
          <p>
            Approval never releases held content. The author must revise and
            resubmit through every current gate.
          </p>
        </section>
      )}
      {kind === "history" && exports.data && !Array.isArray(exports.data) && (
        <section className="panel">
          <h2>Decision feedback</h2>
          <p>
            {exports.data.count} ratings · Average{" "}
            {exports.data.average ?? "No ratings"}
          </p>
        </section>
      )}
      {details && (
        <section className="panel">
          <div className="panel-heading">
            <h2>Record metadata</h2>
            <button onClick={() => setDetails(null)}>Close</button>
          </div>
          {kind === "reviews" && (
            <>
              <p>
                Held content is not retained. Inspect execution findings and the
                decision history below.
              </p>
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
                      try {
                        await request(
                          `/api/reviews/${details.id}/assignment`,
                          "PUT",
                          { assigned_reviewer: assignee, reason },
                        );
                        setMessage("Review assignment recorded.");
                        setDetails(await request(`/api/reviews/${details.id}`));
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
                ["Admin", "Developer", "Policy Owner"].includes(
                  String(identity.data?.role),
                ) && (
                  <NavLink
                    className="button"
                    to={`/playground?review=${details.id}`}
                  >
                    Submit revised text for reinspection
                  </NavLink>
                )}
            </>
          )}
          <pre>
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
          </pre>
        </section>
      )}
      {kind === "reports" && (
        <section className="panel">
          <h2>Export attempts</h2>
          <DataState
            loading={exports.loading}
            error={exports.error}
            reload={exports.reload}
          />
          {Array.isArray(exports.data) &&
            exports.data.map((report) => (
              <div className="detector" key={String(report.id)}>
                <span>
                  {String(report.id).slice(0, 8)} ·{" "}
                  {String(report.state || report.status)} ·{" "}
                  {String(report.error_code || "")}
                </span>
                {canExport &&
                  Boolean(report.state) &&
                  report.state !== "COMPLETED" && (
                    <button
                      disabled={busy}
                      onClick={async () => {
                        if (
                          !confirm(
                            "Check existing storage evidence and retry a missing object within the attempt limit? This may access ADLS.",
                          )
                        )
                          return;
                        setBusy(true);
                        try {
                          const recovered = await request<RecordData>(
                            `/api/reports/exports/${report.id}/reconcile`,
                            "POST",
                          );
                          setMessage(`Recovery: ${recovered.state}`);
                          await exports.reload();
                          await reload();
                        } catch (error) {
                          setMessage(String(error));
                        } finally {
                          setBusy(false);
                        }
                      }}
                    >
                      Reconcile / recover
                    </button>
                  )}
              </div>
            ))}
          <div className="pagination">
            <button
              disabled={!exportOffset || exports.loading}
              onClick={() => setExportOffset(Math.max(0, exportOffset - 20))}
            >
              Previous exports
            </button>
            <span>Page {exportOffset / 20 + 1}</span>
            <button
              disabled={
                exports.loading ||
                !Array.isArray(exports.data) ||
                exports.data.length < 20
              }
              onClick={() => setExportOffset(exportOffset + 20)}
            >
              Next exports
            </button>
          </div>
          <pre>{JSON.stringify(exports.data, null, 2)}</pre>
        </section>
      )}
    </>
  );
}
// Identify fixture execution prominently across every dashboard screen.
function EnvironmentBanner() {
  const { data, error } = useApi<RecordData>("/api/settings");
  if (error) return <Notice message={error} />;
  if (!data) return null;
  return (
    <div className="environment-banner">
      <ShieldCheck size={15} />
      {data.provider_mode === "fixture"
        ? "DETERMINISTIC LOCAL FIXTURES · Generation and moderation are simulated test dependencies."
        : "LIVE PROVIDER MODE · Required cloud inspections fail closed when unavailable."}{" "}
      <span>PII: {String(data.pii_mode)}</span>
    </div>
  );
}

// Display truthful configuration and live database diagnostics without secrets.
function SessionManager() {
  const [offset, setOffset] = useState(0),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  const sessions = useApi<
    {
      id: string;
      actor: string;
      expires: string;
      revoked: boolean;
      expired: boolean;
    }[]
  >(`/api/auth/sessions?limit=20&offset=${offset}`);
  return (
    <section className="panel">
      <h2>Workspace sessions</h2>
      <p>
        Revocation ends the selected session. Provisioned credentials can still
        create new sessions until an operator disables or rotates them.
      </p>
      <Notice message={message} />
      <DataState {...sessions} empty={sessions.data?.length === 0} />
      {sessions.data?.map((session) => (
        <div className="detector" key={session.id}>
          <span>
            {session.actor} · expires {session.expires} ·{" "}
            {session.revoked
              ? "Revoked"
              : session.expired
                ? "Expired"
                : "Active"}
          </span>
          <button
            disabled={busy || session.revoked || session.expired}
            onClick={async () => {
              if (!confirm(`Revoke this session for ${session.actor}?`)) return;
              setBusy(true);
              try {
                await request(
                  `/api/auth/sessions/${session.id}/revoke`,
                  "POST",
                );
                setMessage("Session revoked.");
                await sessions.reload();
              } catch (error) {
                setMessage(String(error));
              } finally {
                setBusy(false);
              }
            }}
          >
            Revoke session
          </button>
        </div>
      ))}
      <div className="pagination">
        <button
          disabled={!offset || sessions.loading}
          onClick={() => setOffset(Math.max(0, offset - 20))}
        >
          Previous sessions
        </button>
        <span>Page {offset / 20 + 1}</span>
        <button
          disabled={
            sessions.loading || !sessions.data || sessions.data.length < 20
          }
          onClick={() => setOffset(offset + 20)}
        >
          Next sessions
        </button>
        <button onClick={() => void sessions.reload()}>Refresh sessions</button>
      </div>
    </section>
  );
}

function Configuration() {
  const { data, error, loading, reload } = useApi<RecordData>("/api/settings");
  const consumption = useApi<RecordData>("/api/usage");
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">WORKSPACE CONFIGURATION</span>
          <h1>Settings & diagnostics</h1>
          <p>
            Configuration presence does not imply successful cloud connectivity.
          </p>
        </div>
        <button
          onClick={() => {
            void reload();
            void consumption.reload();
          }}
        >
          Refresh diagnostics
        </button>
      </div>
      <DataState {...{ loading, error, reload }} />
      {data && ["Admin", "Auditor"].includes(String(data.role)) && (
        <section className="panel">
          <h2>Inference consumption</h2>
          <DataState
            loading={consumption.loading}
            error={consumption.error}
            reload={consumption.reload}
          />
          <pre>{JSON.stringify(consumption.data, null, 2)}</pre>
        </section>
      )}
      {data?.role === "Admin" && <SessionManager />}
      <section className="panel">
        {data &&
          Object.entries(data).map(([key, value]) => (
            <div className="detector" key={key}>
              <strong>{key.replaceAll("_", " ")}</strong>
              <span>{String(value)}</span>
            </div>
          ))}
        <div className="note">
          This demonstration uses local bearer credentials. Configure providers
          on the server through environment variables.
        </div>
      </section>
    </>
  );
}
// Require a provisioned local credential before loading tenant-owned screens.
export function App() {
  const [authenticated, setAuthenticated] = useState(Boolean(getToken())),
    [token, setToken] = useState(""),
    [error, setError] = useState(""),
    [loggingIn, setLoggingIn] = useState(false);
  useEffect(() => {
    const ended = () => {
      setAuthenticated(false);
      setError("Session expired or revoked. Sign in again.");
    };
    window.addEventListener("governance-session-ended", ended);
    return () => window.removeEventListener("governance-session-ended", ended);
  }, []);
  if (!authenticated)
    return (
      <div className="login">
        <div className="login-brand">
          <ShieldCheck size={38} />
          <h1>Governance Studio</h1>
          <p>A trusted checkpoint for enterprise AI.</p>
        </div>
        <form
          className="panel"
          onSubmit={async (event) => {
            event.preventDefault();
            if (loggingIn) return;
            setLoggingIn(true);
            sessionStorage.setItem("governance-token", token);
            try {
              const session = await request<{ access_token: string }>(
                "/api/auth/session",
                "POST",
              );
              sessionStorage.setItem("governance-token", session.access_token);
              setToken("");
              setError("");
              setAuthenticated(true);
              setToken("");
            } catch (error) {
              sessionStorage.removeItem("governance-token");
              setError(String(error));
            } finally {
              setLoggingIn(false);
            }
          }}
        >
          <span className="eyebrow">LOCAL DEMONSTRATION ACCESS</span>
          <h2>Sign in to your workspace</h2>
          <p>Use a token provisioned with the local setup script.</p>
          <label>
            Access token
            <input
              type="password"
              required
              value={token}
              onChange={(event) => setToken(event.target.value)}
              autoComplete="off"
            />
          </label>
          <Notice message={error} />
          <button className="primary" disabled={loggingIn}>
            Connect workspace <ChevronRight size={16} />
          </button>
          <small>Roles and tenant access are enforced by the server.</small>
        </form>
      </div>
    );
  return (
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
            Workspace <ChevronRight size={13} /> <strong>AI Governance</strong>
          </div>
          <div className="header-right">
            <span className="local-pill">
              <i />
              Governed workspace
            </span>
            <button
              title="Sign out"
              onClick={async () => {
                try {
                  await request("/api/auth/logout", "POST");
                } catch (error) {
                  setError(
                    `Signed out on this device. Server revocation was not confirmed: ${String(error)}. The server session remains valid until expiry or administrator revocation.`,
                  );
                }
                sessionStorage.removeItem("governance-token");
                setAuthenticated(false);
              }}
            >
              <LogOut size={17} />
            </button>
            <span className="avatar">GV</span>
          </div>
        </header>
        <main>
          <Notice message={error} />
          <EnvironmentBanner />
          <Notice message={error} />
          <React.Suspense
            fallback={<div className="skeleton" aria-label="Loading page" />}
          >
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/policies" element={<Policies />} />
              <Route path="/policies/new" element={<Editor key="new" />} />
              <Route path="/policies/:id" element={<Editor key="existing" />} />
              <Route path="/simulator" element={<Simulator />} />
              <Route path="/playground" element={<Playground />} />
              <Route
                path="/history"
                element={<Records key="history" kind="history" />}
              />
              <Route
                path="/reviews"
                element={<Records key="reviews" kind="reviews" />}
              />
              <Route path="/analytics" element={<Overview analytics />} />
              <Route
                path="/reports"
                element={<Records key="reports" kind="reports" />}
              />
              <Route path="/settings" element={<Configuration />} />
              <Route path="*" element={<p>Page not found.</p>} />
            </Routes>
          </React.Suspense>
          <footer>
            <ShieldCheck size={14} /> Governance signals are heuristic controls,
            not legal compliance certification.
          </footer>
        </main>
      </div>
    </BrowserRouter>
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
