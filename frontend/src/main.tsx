import React, { useCallback, useEffect, useState } from "react";
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
  LogOut,
} from "lucide-react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  BarChart,
  Bar,
} from "recharts";
import { request, getToken } from "./api";
import "./styles.css";

type RecordData = Record<string, unknown>;
type Rule = { enabled: boolean; action: string; values?: string[] };
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
  provider_mode: string;
  policy_id: string;
  policy_version: number;
  duration_ms: number;
  request_id: string;
  provider_error?: string;
};
type Summary = {
  total_policies: number;
  active_policies: number;
  total_validations: number;
  pending_reviews: number;
  decisions: Record<string, number>;
  trends: { date: string; score: number }[];
  violations: Record<string, number>;
  contributions: Record<string, number>;
  active_policy: { id: string; version: number } | null;
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
function useApi<T>(path: string) {
  const [data, setData] = useState<T | null>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  const reload = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await request<T>(path));
    } catch (error) {
      setError(String(error));
    } finally {
      setLoading(false);
    }
  }, [path]);
  useEffect(() => {
    void reload();
  }, [reload]);
  return { data, error, loading, reload };
}
// Render an accessible status badge with consistent decision colors.
function Badge({ value }: { value: string }) {
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
function DataState({
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
function Overview({ analytics = false }: { analytics?: boolean }) {
  const { data, error, loading, reload } = useApi<Summary>(
    "/api/analytics/overview",
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">GOVERNANCE INTELLIGENCE</span>
          <h1>
            {analytics
              ? "Compliance analytics"
              : "Your governance, at a glance"}
          </h1>
          <p>Understand how your policies protect every AI interaction.</p>
        </div>
        <NavLink className="primary button" to="/playground">
          Open playground <ArrowUpRight size={16} />
        </NavLink>
      </div>
      <DataState {...{ loading, error, reload }} />
      {data && (
        <>
          <div className="metrics">
            {[
              [
                "Total validations",
                data.total_validations,
                "All inspected requests",
              ],
              [
                "Active policies",
                data.active_policies,
                `${data.total_policies} policies in your workspace`,
              ],
              [
                "Blocked requests",
                data.decisions.BLOCK,
                "Held before content release",
              ],
              [
                "Pending reviews",
                data.pending_reviews,
                "Awaiting a human decision",
              ],
            ].map(([title, value, caption], index) => (
              <div className="metric" key={String(title)}>
                <span className={`metric-icon color-${index}`}>
                  <ShieldCheck size={19} />
                </span>
                <p>{title}</p>
                <strong>{value}</strong>
                <small>{caption}</small>
              </div>
            ))}
          </div>
          <div className="chart-grid">
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Compliance score</h2>
                  <p>Weighted control results across recent inspections</p>
                </div>
                <span className="badge">LIVE DATA</span>
              </div>
              {data.trends.length ? (
                <div className="chart">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={data.trends}>
                      <defs>
                        <linearGradient id="blue" x1="0" y1="0" x2="0" y2="1">
                          <stop
                            offset="0%"
                            stopColor="#2563eb"
                            stopOpacity={0.25}
                          />
                          <stop
                            offset="100%"
                            stopColor="#2563eb"
                            stopOpacity={0}
                          />
                        </linearGradient>
                      </defs>
                      <CartesianGrid vertical={false} stroke="#edf0f5" />
                      <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                      <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                      <Tooltip />
                      <Area
                        type="monotone"
                        dataKey="score"
                        stroke="#2563eb"
                        fill="url(#blue)"
                        strokeWidth={3}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="empty">
                  Your first validation starts the trend.
                </div>
              )}
            </section>
            <section className="panel">
              <h2>Decision distribution</h2>
              <p>Actual enforcement outcomes</p>
              <div className="decision-list">
                {Object.entries(data.decisions).map(([name, count]) => (
                  <div key={name}>
                    <Badge value={name} />
                    <strong>{count}</strong>
                  </div>
                ))}
              </div>
              <div className="note">
                <ShieldCheck size={18} /> Decisions enforce policy independently
                of the score.
              </div>
            </section>
          </div>
          <section className="panel">
            <h2>
              {analytics
                ? "Control contribution totals"
                : "Violation categories"}
            </h2>
            <p>
              {analytics
                ? "Sum of satisfied control weights; this is not regulatory certification."
                : "Failed and unknown controls in persisted inspections."}
            </p>
            {Object.keys(analytics ? data.contributions : data.violations)
              .length ? (
              <div className="chart">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={Object.entries(
                      analytics ? data.contributions : data.violations,
                    ).map(([category, count]) => ({
                      category: category.replaceAll("_", " "),
                      count,
                    }))}
                  >
                    <CartesianGrid vertical={false} />
                    <XAxis dataKey="category" tick={{ fontSize: 11 }} />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="count" fill="#7c3aed" radius={[5, 5, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="empty">No violations recorded.</div>
            )}
          </section>
        </>
      )}
    </>
  );
}
// Manage policy drafts and lifecycle using backend-enforced transitions.
function Policies() {
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useApi<Policy[]>(
      `/api/policies?offset=${offset}&limit=20`,
    ),
    [search, setSearch] = useState(""),
    [status, setStatus] = useState(""),
    [message, setMessage] = useState(""),
    [versions, setVersions] = useState<RecordData[] | null>(null);
  // Confirm and execute a policy action, then refresh live data.
  async function act(policy: Policy, operation: string) {
    if (!confirm(`${operation} “${policy.name}”?`)) return;
    try {
      await request(
        `/api/policies/${policy.id}${operation === "delete" ? "" : `/${operation}`}`,
        operation === "delete" ? "DELETE" : "POST",
      );
      setMessage(`Policy ${operation} completed.`);
      await reload();
    } catch (error) {
      setMessage(String(error));
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
        <NavLink to="/policies/new" className="primary button">
          <Plus size={17} />
          Create policy
        </NavLink>
      </div>
      <Notice message={message} />
      <section className="panel">
        <div className="toolbar">
          <label className="search">
            <Search size={17} />
            <input
              placeholder="Search this page…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <select
            aria-label="Filter status"
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="">All statuses</option>
            {["DRAFT", "SUBMITTED", "APPROVED", "PUBLISHED", "ARCHIVED"].map(
              (value) => (
                <option key={value}>{value}</option>
              ),
            )}
          </select>
        </div>
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
              {data
                ?.filter(
                  (policy) =>
                    policy.name.toLowerCase().includes(search.toLowerCase()) &&
                    (!status || policy.status === status),
                )
                .map((policy) => (
                  <tr key={policy.id}>
                    <td>
                      <NavLink to={`/policies/${policy.id}`}>
                        {policy.name}
                      </NavLink>
                      <small>Draft revision {policy.revision}</small>
                    </td>
                    <td>
                      <Badge value={policy.status} />
                    </td>
                    <td>
                      <Badge value={policy.enabled ? "ENABLED" : "DISABLED"} />
                    </td>
                    <td>
                      <div className="actions">
                        <NavLink
                          className="button"
                          to={`/policies/${policy.id}`}
                        >
                          View / edit
                        </NavLink>
                        {[
                          ...(policy.status === "DRAFT"
                            ? ["submit", "delete"]
                            : []),
                          ...(policy.status === "SUBMITTED" ? ["approve"] : []),
                          ...(policy.status === "APPROVED" ? ["publish"] : []),
                          ...(policy.status === "PUBLISHED" && policy.enabled
                            ? ["activate"]
                            : []),
                          ...(policy.status !== "ARCHIVED"
                            ? [policy.enabled ? "disable" : "enable", "archive"]
                            : []),
                        ].map((operation) => (
                          <button
                            key={operation}
                            onClick={() => void act(policy, operation)}
                          >
                            {operation}
                          </button>
                        ))}
                        <button
                          onClick={async () => {
                            try {
                              setVersions(
                                await request(
                                  `/api/policies/${policy.id}/versions`,
                                ),
                              );
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
    [ready, setReady] = useState(!id);
  useEffect(() => {
    if (id)
      void request<Policy>(`/api/policies/${id}`)
        .then((policy) => {
          setDocument(JSON.parse(policy.draft));
          setReady(true);
        })
        .catch((error) => setMessage(String(error)));
  }, [id]);
  // Persist a validated draft without modifying published snapshots.
  async function save(event: React.FormEvent) {
    event.preventDefault();
    try {
      await request(
        id ? `/api/policies/${id}` : "/api/policies",
        id ? "PUT" : "POST",
        document,
      );
      navigate("/policies");
    } catch (error) {
      setMessage(String(error));
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
                  setDocument({ ...document, description: event.target.value })
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
            <button className="primary" type="submit">
              Save draft
            </button>
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
  const [text, setText] = useState(
      "Explain the benefits of data governance in simple terms.",
    ),
    [result, setResult] = useState<Result | null>(null),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  // Submit only to the backend; provider credentials never enter the browser.
  async function run(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    setResult(null);
    try {
      setResult(
        await request<Result>("/api/governance/generate", "POST", { text }),
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
                Policy {result.policy_id.slice(0, 8)} · v{result.policy_version}{" "}
                · {result.duration_ms} ms
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
              <CircleCheck className="gateway-icon" />
              <h3>
                {result.model_invoked
                  ? "Invocation attempted"
                  : "Model not invoked"}
              </h3>
              <p>
                {result.provider_error ||
                  "Input approval is required before generation."}
              </p>
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
            <div className="actions">
              <span>Rate the decision:</span>
              {[1, 2, 3, 4, 5].map((rating) => (
                <button
                  key={rating}
                  onClick={async () => {
                    try {
                      await request("/api/feedback", "POST", {
                        execution_id: result.request_id,
                        rating,
                      });
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
  const policies = useApi<Policy[]>("/api/policies"),
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
// Present paginated real records with optional review and export actions.
function Records({ kind }: { kind: "history" | "reviews" | "reports" }) {
  const [offset, setOffset] = useState(0),
    [message, setMessage] = useState(""),
    [details, setDetails] = useState<RecordData | null>(null);
  const path =
    kind === "history"
      ? "/api/audit/executions"
      : kind === "reviews"
        ? "/api/reviews"
        : "/api/audit/events";
  const { data, error, loading, reload } = useApi<RecordData[]>(
    `${path}?offset=${offset}&limit=20`,
  );
  const exports = useApi<RecordData[]>(
    kind === "reports" ? "/api/reports/exports" : "/api/feedback/summary",
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
        {kind === "reports" && (
          <div className="actions">
            {["json", "csv"].map((format) => (
              <button
                className="primary"
                key={format}
                onClick={async () => {
                  try {
                    const report = await request<RecordData>(
                      "/api/reports/export",
                      "POST",
                      { format },
                    );
                    setMessage(`ADLS export: ${report.status}`);
                    void exports.reload();
                    void reload();
                  } catch (error) {
                    setMessage(String(error));
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
      <section className="panel">
        <DataState {...{ loading, error, reload }} empty={data?.length === 0} />
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
                      <button onClick={() => setDetails(row)}>
                        Inspect metadata
                      </button>
                      {kind === "reviews" &&
                        row.status === "PENDING" &&
                        ["approve", "reject"].map((operation) => (
                          <button
                            key={operation}
                            onClick={async () => {
                              if (
                                !confirm(
                                  `${operation} review? This never releases held content.`,
                                )
                              )
                                return;
                              try {
                                await request(
                                  `/api/reviews/${row.id}/${operation}`,
                                  "POST",
                                );
                                setMessage(`Review ${operation} recorded.`);
                                await reload();
                              } catch (error) {
                                setMessage(String(error));
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
      {details && (
        <section className="panel">
          <div className="panel-heading">
            <h2>Record metadata</h2>
            <button onClick={() => setDetails(null)}>Close</button>
          </div>
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
function Configuration() {
  const { data, error, loading, reload } = useApi<RecordData>("/api/settings");
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
        <button onClick={reload}>Refresh diagnostics</button>
      </div>
      <DataState {...{ loading, error, reload }} />
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
    [error, setError] = useState("");
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
            sessionStorage.setItem("governance-token", token);
            try {
              await request("/api/settings");
              setAuthenticated(true);
              setToken("");
            } catch (error) {
              sessionStorage.removeItem("governance-token");
              setError(String(error));
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
          <button className="primary">
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
          <small>LOCAL WORKSPACE · v1.0</small>
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
              Local environment
            </span>
            <button
              title="Sign out"
              onClick={() => {
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
          <EnvironmentBanner />
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/policies" element={<Policies />} />
            <Route path="/policies/new" element={<Editor />} />
            <Route path="/policies/:id" element={<Editor />} />
            <Route path="/simulator" element={<Simulator />} />
            <Route path="/playground" element={<Playground />} />
            <Route path="/history" element={<Records kind="history" />} />
            <Route path="/reviews" element={<Records kind="reviews" />} />
            <Route path="/analytics" element={<Overview analytics />} />
            <Route path="/reports" element={<Records kind="reports" />} />
            <Route path="/settings" element={<Configuration />} />
            <Route path="*" element={<p>Page not found.</p>} />
          </Routes>
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
      <App />
    </React.StrictMode>,
  );
