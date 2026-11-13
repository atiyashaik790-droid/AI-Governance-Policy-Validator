import { UsageConsumption } from "./UsageConsumption";
import { NavLink } from "react-router-dom";
import { ArrowUpRight, ShieldCheck } from "lucide-react";
import { useApi, Badge, DataState } from "./main";
import type { Summary } from "./main";
import { useWorkspace } from "./workspace";
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

export default function Overview({
  analytics = false,
  role = "",
}: {
  analytics?: boolean;
  role?: string;
}) {
  const workspace = useWorkspace();
  const versioned = workspace.data?.multi_policy_available === true;
  const { data: source, error, loading, reload } = useApi<Summary & { request_count?: number; active_policy_count?: number }>(
    versioned ? "/api/v2/analytics/overview" : "/api/analytics/overview",
  );
  const data = source && versioned ? { ...source, total_validations: source.request_count || 0,
    active_policies: source.active_policy_count || 0 } : source;
  const compliance = data?.compliance;
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
      {analytics && ["Admin", "Auditor"].includes(role) && <UsageConsumption />}
      <DataState {...{ loading, error, reload }} />
      {data?.window && (
        <p className="muted">
          Reporting window: {data.window.start} through{" "}
          {data.window.end_exclusive} (exclusive). Request counts and analytics use this same reporting window.
        </p>
      )}
      {data && (
        <>
          <div className="metrics">
            {[
              [
                "Total validations",
                data.total_validations,
                "Inspected requests in this reporting window",
              ],
              [
                "Active policies",
                data.active_policies,
                versioned ? "Current active published-version assignments" : `${data.total_policies} policies in your workspace`,
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
                  <p>Persisted evidence of configured control execution</p>
                </div>
                <span className="badge">LIVE DATA</span>
              </div>
              <p className="muted" title="Applicable weights are 30% secrets, 25% PII, 25% moderation and 20% configured rules. Known satisfied or detected results earn weight; unknown or withheld results earn zero. Disabled controls are excluded. Weights are pooled across requests. This measures evidenced control execution, not regulatory certification or detector accuracy.">
                {compliance?.score == null ? "Insufficient data for a score" : `${compliance.score}% control evidence coverage`}
                {compliance && ` · ${compliance.scored_requests} scored requests · ${compliance.incomplete_inspections} incomplete inspections`}
              </p>
              {compliance?.trends.length ? (
                <div className="chart">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={compliance.trends}>
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
                  Insufficient data: run a validation with persisted control evidence.
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
            <h2>Violation categories</h2>
            <p>Confirmed findings per request, inspection stage and category; duplicate policy detections count once.</p>
            {compliance?.findings_available ? (
              <div className="chart">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={Object.entries(compliance.violations).map(([category, count]) => ({
                      category: ({ secret_detection: "Secrets", pii_detection: "PII", moderation: "Moderation", blocked_keywords: "Keywords", custom: "Other rules" } as Record<string, string>)[category] || category,
                      count,
                    }))}
                  >
                    <CartesianGrid vertical={false} />
                    <XAxis dataKey="category" tick={{ fontSize: 11 }} />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Bar dataKey="count" fill="#7c3aed" radius={[5, 5, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="empty">{data.total_validations ? "Finding evidence unavailable for this reporting window." : "No validations in this reporting window."}</div>
            )}
          </section>
        </>
      )}
    </>
  );
}
