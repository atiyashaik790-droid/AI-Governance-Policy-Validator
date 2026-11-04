import { NavLink } from "react-router-dom";
import { ArrowUpRight, ShieldCheck } from "lucide-react";
import { useApi, Badge, DataState } from "./main";
import type { Summary } from "./main";
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
}: {
  analytics?: boolean;
}) {
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
      {data?.window && (
        <p className="muted">
          Reporting window: {data.window.start} through{" "}
          {data.window.end_exclusive} (exclusive). Trend: latest{" "}
          {data.trend_sample_limit || 100} executions; each score uses the
          lowest inspected stage.
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
