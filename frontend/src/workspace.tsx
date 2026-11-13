import React, { useCallback, useContext, useEffect, useRef, useState } from "react";
import { ApiError, request } from "./api";

export type WorkspaceState = {
  mode: "LEGACY" | "MULTI";
  multi_policy_available: boolean;
  set_revision: number | null;
  active_policy_count: number;
};
export type Assignment = { policy_id: string; version_id: string; version: number; active: boolean };
export type Page<T> = { items: T[]; total: number; offset: number; limit: number; set_revision?: number };
type Workspace = {
  data: WorkspaceState | null;
  loading: boolean;
  error: string;
  busy: boolean;
  reload: () => Promise<void>;
  mutate: (path: string, body: unknown) => Promise<void>;
};
const Context = React.createContext<Workspace | null>(null);

export function workspaceError(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 412 || error.status === 428)
      return "Workspace changed. Refresh the workspace, review the published version pins, and submit again.";
    if (error.status === 403) return "Your role does not permit this action, or session verification failed. Refresh your session.";
    if (error.status === 503) return "Multi-policy functionality is unavailable. Check schema readiness and diagnostics before retrying.";
    if (error.message === "TRANSITION_BUSY") return "An active or unreconciled request prevents mode changes. Wait for completion or ask an administrator to reconcile it.";
    if (error.message === "USE_API_V2" || error.message === "WORKSPACE_MODE_CONFLICT") return "Workspace mode changed. Refresh and review the current assignments before submitting again.";
  }
  return String(error);
}

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const [data, setData] = useState<WorkspaceState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const inFlight = useRef(false);
  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError("");
    try {
      const state = await request<WorkspaceState>("/api/v2/workspace/policy-state", "GET", undefined, { signal });
      if (!["LEGACY", "MULTI"].includes(state.mode) || typeof state.multi_policy_available !== "boolean" ||
          typeof state.active_policy_count !== "number" || (state.multi_policy_available && !Number.isInteger(state.set_revision)))
        throw new Error("Workspace state could not be verified. Refresh before running governance.");
      if (!signal?.aborted) setData(state);
    } catch (error) {
      if (signal?.aborted) return;
      if (error instanceof ApiError && error.status === 404) {
        setData({ mode: "LEGACY", multi_policy_available: false, set_revision: null, active_policy_count: 0 });
      } else {
        setData(null);
        setError(workspaceError(error));
      }
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);
  const reload = useCallback(() => load(), [load]);
  async function mutate(path: string, body: unknown) {
    if (inFlight.current) throw new Error("A workspace change is already in progress.");
    if (!data?.multi_policy_available || data.set_revision === null) throw new Error("Schema 006 is required for multi-policy management.");
    inFlight.current = true;
    setBusy(true);
    try {
      await request(path, "PUT", body, { headers: { "If-Match": `"${data.set_revision}"` } });
      await reload();
    } catch (error) {
      await reload();
      throw new Error(workspaceError(error));
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }
  return <Context.Provider value={{ data, loading, error, busy, reload, mutate }}>{children}</Context.Provider>;
}

export function useWorkspace() {
  const workspace = useContext(Context);
  if (!workspace) throw new Error("An authenticated workspace is required");
  return workspace;
}

export function WorkspaceStatus({ role }: { role?: string }) {
  const { data, loading, error, busy, reload, mutate } = useWorkspace();
  const [message, setMessage] = useState("");
  return <section className="panel" aria-label="Workspace policy mode">
    <div className="panel-heading"><h2>Workspace policy mode</h2><button disabled={loading || busy} onClick={() => void reload()}>Refresh workspace</button></div>
    {loading && <p role="status">Checking workspace policy mode…</p>}
    {error && <p role="alert">{error}</p>}
    {message && <p role="status">{message}</p>}
    {data && <>
      <p><strong>{data.mode}</strong> · {data.active_policy_count} active {data.active_policy_count === 1 ? "policy" : "policies"}</p>
      {!data.multi_policy_available && <p>Legacy policy enforcement is available. Multi-policy management requires schema 006.</p>}
      {data.multi_policy_available && data.mode === "LEGACY" && role === "Admin" && <button disabled={busy || loading} onClick={async () => {
        if (!confirm("Select MULTI mode? Existing legacy activation will not be carried over. Choose and activate explicit published versions.")) return;
        try { await mutate("/api/v2/workspace/policy-mode", { mode: "MULTI", seed_legacy_assignment: false }); setMessage("MULTI mode selected. Activate published versions independently."); }
        catch (error) { setMessage(workspaceError(error)); }
      }}>Enable MULTI mode</button>}
      {data.mode === "MULTI" && <p>Every active published pin is evaluated. To return to LEGACY, deactivate other policies and choose an explicit published version from its History.</p>}
      {role && role !== "Admin" && data.multi_policy_available && <p>Only Admin users can change workspace mode or policy assignments.</p>}
    </>}
  </section>;
}

export function useAssignments() {
  const workspace = useWorkspace();
  const [data, setData] = useState<Record<string, Assignment>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    if (!workspace.data?.multi_policy_available || workspace.data.mode !== "MULTI") { setData({}); return; }
    setLoading(true);
    setError("");
    setData({});
    void (async () => {
      try {
        const assignments: Record<string, Assignment> = {};
        let offset = 0;
        const revision = workspace.data?.set_revision;
        while (true) {
          const page = await request<Page<Assignment>>(`/api/v2/workspace/policy-assignments?limit=100&offset=${offset}`, "GET", undefined, { signal: controller.signal });
          if (page.set_revision !== revision) throw new Error("Workspace changed while loading assignments. Refresh workspace.");
          page.items.forEach((item) => { assignments[item.policy_id] = item; });
          offset += page.items.length;
          if (offset >= page.total) break;
          if (!page.items.length) throw new Error("Assignment listing is incomplete. Refresh workspace.");
        }
        if (!controller.signal.aborted) setData(assignments);
      } catch (error) { if (!controller.signal.aborted) setError(workspaceError(error)); }
      finally { if (!controller.signal.aborted) setLoading(false); }
    })();
    return () => controller.abort();
  }, [workspace.data?.multi_policy_available, workspace.data?.mode, workspace.data?.set_revision]);
  return { data, loading, error };
}

export function AssignmentControl({ policy, assignment, role, disabled, changed }: {
  policy: { id: string; name: string; enabled: number; status: string; has_published_versions?: boolean };
  assignment?: Assignment; role: string; disabled: boolean; changed: () => Promise<void>;
}) {
  const workspace = useWorkspace();
  const [versions, setVersions] = useState<{ id: string; number: number }[] | null>(null);
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const eligible = policy.enabled && !["ARCHIVED", "DELETED"].includes(policy.status) && policy.has_published_versions;
  async function load(next: number) {
    setLoading(true);
    try {
      setVersions(await request(`/api/policies/${policy.id}/versions?limit=20&offset=${next}`));
      setOffset(next); setSelected("");
    } catch (error) { setMessage(workspaceError(error)); }
    finally { setLoading(false); }
  }
  async function change(active: boolean) {
    if (!confirm(`${active ? "Activate the explicitly selected published version of" : "Deactivate"} “${policy.name}”?`)) return;
    try {
      await workspace.mutate(`/api/v2/workspace/policy-assignments/${policy.id}`, { active, ...(active ? { version_id: selected } : {}) });
      setSelected(""); setMessage(active ? "Published version pinned and active." : "Policy deactivated."); await changed();
    } catch (error) { setSelected(""); setMessage(workspaceError(error)); await changed(); }
  }
  return <div aria-label={`Assignment for ${policy.name}`}>
    <small>{assignment?.active ? (Number.isInteger(assignment.version) ? `Active · pinned published version ${assignment.version}` : "Active · published version") : "Inactive"}</small>
    {message && <p role="status">{message}</p>}
    {role === "Admin" && <div className="actions">
      {eligible && <button disabled={disabled || loading || workspace.busy} onClick={() => void load(0)}>Choose published version</button>}
      {assignment?.active && <button disabled={disabled || workspace.busy} onClick={() => void change(false)}>Deactivate policy</button>}
      {versions && <>
        <select aria-label={`Published version for ${policy.name}`} value={selected} onChange={(event) => setSelected(event.target.value)}>
          <option value="">Select an explicit published version</option>
          {versions.map((version) => <option key={version.id} value={version.id}>Version {version.number}</option>)}
        </select>
        <button disabled={!selected || disabled || workspace.busy || loading} onClick={() => void change(true)}>Activate selected version</button>
        <button disabled={!offset || loading} onClick={() => void load(Math.max(0, offset - 20))}>Previous published versions</button>
        <button disabled={versions.length < 20 || loading} onClick={() => void load(offset + 20)}>Next published versions</button>
      </>}
    </div>}
  </div>;
}

export function normalizeRecord(row: Record<string, unknown>): Record<string, unknown> {
  return { ...row, id: row.id || row.request_id || row.review_id, created: row.created || row.timestamp };
}
