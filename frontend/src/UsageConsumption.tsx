import { useApi, DataState } from "./main";

type Usage = {
  date: string; reserved_today: number; daily_limit: number; warning: boolean; warning_percent: number;
  statuses: Record<string, number>; concurrency_limit: number; user_per_minute: number; tenant_per_minute: number;
  tokens: { prompt_tokens: number | null; completion_tokens: number | null };
};
const number = (value: number | null | undefined) => value == null ? "Not recorded" : value.toLocaleString();
const COLORS: Record<string, string> = { SUCCEEDED: "#10B981", FAILED: "#F59E0B", RESERVED: "#2563EB", EXPIRED: "#7C3AED", INSPECTED: "#06B6D4" };

export function UsageConsumption() {
  const usage = useApi<Usage>("/api/usage");
  const data = usage.data;
  const statuses = Object.entries(data?.statuses || {});
  const total = statuses.reduce((sum, [, count]) => sum + count, 0);
  const percent = data && data.daily_limit > 0 ? Math.min(100, Math.max(0, data.reserved_today / data.daily_limit * 100)) : 0;
  return <section className="panel" aria-labelledby="usage-heading">
    <div className="panel-heading"><div><h2 id="usage-heading">AI Usage &amp; Consumption</h2><p>Workspace reservation limits and recorded inference activity.</p></div><button disabled={usage.loading} onClick={() => void usage.reload()}>Refresh usage</button></div>
    <DataState {...usage} />
    {!usage.loading && !usage.error && !data && <p className="empty">Usage data is not available yet.</p>}
    {data && <>
      <h3>Today’s reservations · {data.date} UTC</h3>
      <p><strong>{number(data.reserved_today)} / {number(data.daily_limit)}</strong> requests reserved today</p>
      <progress className="usage-progress" aria-label="Daily request reservations" max={100} value={percent} />
      <p className="muted">Warning threshold: {number(data.warning_percent)}% of the daily limit. Reservations include requests that may later fail or expire.</p>
      {data.warning && <p className="notice" role="alert">Daily reservation usage has reached the warning threshold. Review activity before submitting more requests.</p>}
      <h3>Retained-history inference activity</h3>
      <p className="muted">Status totals and provider-reported tokens cover all retained history, independently of today’s reservations. Token counts may be incomplete; they are not billing totals.</p>
      <div className="metrics usage-metrics">
        <div className="metric"><p>Successful inferences</p><strong>{number(data.statuses?.SUCCEEDED || 0)}</strong></div>
        <div className="metric"><p>Failed inferences</p><strong>{number(data.statuses?.FAILED || 0)}</strong></div>
        <div className="metric"><p>Recorded prompt tokens</p><strong>{number(data.tokens?.prompt_tokens)}</strong></div>
        <div className="metric"><p>Recorded completion tokens</p><strong>{number(data.tokens?.completion_tokens)}</strong></div>
      </div>
      <figure className="usage-status-chart"><figcaption>Inference status distribution · retained history</figcaption>
        {total > 0 ? statuses.map(([status, count]) => <div className="usage-status-row" key={status}>
          <span>{status.replaceAll("_", " ")}</span><meter aria-label={`${status} inference count`} min={0} max={total} value={count} style={{ accentColor: COLORS[status] || "#2563EB" }} /><strong>{number(count)}</strong>
        </div>) : <p className="empty">No inference history recorded.</p>}
      </figure>
      <h3>Request controls</h3>
      <dl className="usage-limits">
        <div><dt>Per-user requests / minute</dt><dd>{number(data.user_per_minute)}</dd></div>
        <div><dt>Per-tenant requests / minute</dt><dd>{number(data.tenant_per_minute)}</dd></div>
        <div><dt>Concurrency limit</dt><dd>{number(data.concurrency_limit)}</dd></div>
      </dl>
    </>}
  </section>;
}
