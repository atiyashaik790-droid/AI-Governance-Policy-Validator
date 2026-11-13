import { useState } from "react";
import { useApi, DataState } from "./main";
import { request } from "./api";

type WorkspaceSession = { id: string; actor?: string; expires: string; revoked: boolean; expired: boolean };
function timestamp(value: string) {
  if (value === "9999-12-31T23:59:59+00:00") return "Never (local demo)";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Not recorded" : date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}
const status = (session: WorkspaceSession) => session.revoked ? "Revoked" : session.expired ? "Expired" : "Active";
export function WorkspaceSessions({ mode = "sso" }: { mode?: "sso" | "demo" }) {
  const [offset, setOffset] = useState(0);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const sessions = useApi<WorkspaceSession[]>(`/api/${mode === "demo" ? "auth" : "sso"}/sessions?limit=20&offset=${offset}`);
  return <section className="panel" aria-labelledby="sessions-heading">
    <div className="panel-heading"><div><h2 id="sessions-heading">Sessions</h2><p>{mode === "demo" ? "Local demo sessions for this workspace." : "Microsoft Entra sessions for this workspace."}</p></div><button disabled={sessions.loading || busy} onClick={() => void sessions.reload()}>Refresh sessions</button></div>
    <p>Revocation ends the selected session. An authorized operator must disable the membership or source credential to prevent future sign-ins.</p>
    <p className="muted">Summary counts cover this page only, not all workspace sessions. Roles and creation timestamps are not provided by the current session API.</p>
    {message && <p className="notice" role="status">{message}</p>}
    <DataState {...sessions} />
    {sessions.data && <>
      <div className="metrics session-metrics">{["Active", "Expired", "Revoked"].map(label => <div className="metric" key={label}><p>{label} · this page</p><strong>{sessions.data!.filter(session => status(session) === label).length}</strong></div>)}</div>
      {!sessions.data.length ? <p className="empty">No workspace sessions on this page.</p> : <div className="table-wrap"><table>
        <caption className="sr-only">Workspace sessions on page {offset / 20 + 1}; timestamps use your local time zone</caption>
        <thead><tr><th>Account</th><th>Role</th><th>Status</th><th>Created</th><th>Expires (local time)</th><th>Action</th></tr></thead>
        <tbody>{sessions.data.map(session => <tr key={session.id}>
          <td>{session.actor || "Not recorded"}</td><td>Not recorded</td><td><span className={`session-status session-${status(session).toLowerCase()}`}>{status(session)}</span></td><td>Not recorded</td><td>{timestamp(session.expires)}</td>
          <td><button aria-label={`Revoke session for ${session.actor || "unrecorded account"}`} disabled={busy || sessions.loading || session.revoked || session.expired} onClick={async () => {
            if (!confirm(`Revoke this session for ${session.actor || "unrecorded account"}?`)) return;
            setBusy(true); setMessage("");
            try {
              await request(`/api/${mode === "demo" ? "auth" : "sso"}/sessions/${session.id}/revoke`, "POST");
              setMessage("Session revoked.");
              await sessions.reload();
            } catch (error) { setMessage(String(error)); }
            finally { setBusy(false); }
          }}>Revoke session</button></td>
        </tr>)}</tbody>
      </table></div>}
    </>}
    <div className="pagination"><button disabled={!offset || sessions.loading || busy} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous sessions</button><span>Page {offset / 20 + 1}</span><button disabled={sessions.loading || busy || !sessions.data || sessions.data.length < 20} onClick={() => setOffset(offset + 20)}>Next sessions</button></div>
  </section>;
}
