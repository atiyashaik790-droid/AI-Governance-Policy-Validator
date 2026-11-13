import { useCallback, useEffect, useState } from "react";
import { request } from "./api";

type Category = {
  id: string; name: string; description: string; builtin: boolean; enabled: boolean;
  action: "BLOCK" | "REDACT" | "HUMAN_REVIEW";
  detection: "keyword" | "regex" | "builtin";
  values: string[]; revision: number; policy_ids: string[];
};
type Policy = { id: string; name: string; status: string };
type CategoryPage = { items: Category[]; total: number; offset: number; limit: number };
type Draft = { name: string; description: string; enabled: boolean; action: Category["action"];
  detection: "keyword" | "regex"; values: string };
const emptyDraft: Draft = { name: "", description: "", enabled: true, action: "BLOCK", detection: "keyword", values: "" };

export function CategoryManagement({ role }: { role: string }) {
  const [page, setPage] = useState<CategoryPage | null>(null);
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [search, setSearch] = useState("");
  const [enabled, setEnabled] = useState("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Category | null>(null);
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [policyId, setPolicyId] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const admin = role === "Admin";

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const query = new URLSearchParams({ offset: String(offset), limit: "20", search });
      if (enabled) query.set("enabled", enabled);
      const [categories, availablePolicies] = await Promise.all([
        request<CategoryPage>(`/api/categories?${query}`),
        request<Policy[]>("/api/policies?limit=100"),
      ]);
      setPage(categories); setPolicies(availablePolicies);
      setSelected(current => current ? categories.items.find(item => item.id === current.id) || null : null);
    } catch (failure) { setError((failure as Error).message); }
    finally { setLoading(false); }
  }, [offset, search, enabled]);
  useEffect(() => { void load(); }, [load]);

  function edit(category: Category) {
    setSelected(category);
    setPolicyId("");
    setDraft({ name: category.name, description: category.description, enabled: category.enabled,
      action: category.action, detection: category.detection === "builtin" ? "keyword" : category.detection,
      values: category.values.join("\n") });
    setNotice(""); setError("");
  }
  function update(change: Partial<Draft>) { setDraft(current => ({ ...current, ...change })); }
  async function save() {
    setBusy(true); setError(""); setNotice("");
    try {
      const body = { ...draft, values: draft.values.split("\n").map(value => value.trim()).filter(Boolean) };
      const result = selected
        ? await request<Category>(`/api/categories/${selected.id}`, "PUT", body, { headers: { "If-Match": `"${selected.revision}"` } })
        : await request<Category>("/api/categories", "POST", body);
      setSelected(result); setNotice(selected ? "Category updated." : "Category created.");
      await load();
    } catch (failure) { setError((failure as Error).message); }
    finally { setBusy(false); }
  }
  async function remove() {
    if (!selected || !window.confirm(`Delete category ${selected.name}?`)) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await request(`/api/categories/${selected.id}`, "DELETE", undefined,
        { headers: { "If-Match": `"${selected.revision}"` } });
      setSelected(null); setDraft(emptyDraft); setNotice("Category deleted."); await load();
    } catch (failure) { setError((failure as Error).message); }
    finally { setBusy(false); }
  }
  async function association(target: string, assign: boolean) {
    if (!selected) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const updated = await request<Category>(`/api/categories/${selected.id}/policies/${target}`, assign ? "PUT" : "DELETE");
      setSelected(updated); setPolicyId(""); setNotice(assign ? "Policy assigned. Publish its updated draft to activate the rule." : "Policy unassigned.");
      await load();
    } catch (failure) { setError((failure as Error).message); }
    finally { setBusy(false); }
  }

  return <div className="category-page">
    <div className="page-heading"><div><h1>Governance category management</h1>
      <p>Organize controls and assign supported detectors to draft policies.</p></div>
      {admin && <button className="primary" onClick={() => { setSelected(null); setDraft(emptyDraft); setNotice(""); }}>New category</button>}
    </div>
    {error && <p role="alert">{error} <button onClick={() => void load()}>Retry</button></p>}
    {notice && <p role="status">{notice}</p>}
    <div className="toolbar"><label>Search categories<input value={search} onChange={event => { setOffset(0); setSearch(event.target.value); }} /></label>
      <label>Status<select value={enabled} onChange={event => { setOffset(0); setEnabled(event.target.value); }}>
        <option value="">All</option><option value="true">Enabled</option><option value="false">Disabled</option>
      </select></label></div>
    {loading ? <div className="skeleton" aria-label="Loading categories" /> : <div className="table-wrap"><table>
      <thead><tr><th>Category</th><th>Detector</th><th>Status</th><th>Policies</th><th>Action</th></tr></thead>
      <tbody>{page?.items.map(category => <tr key={category.id}>
        <td><strong>{category.name}</strong><small>{category.builtin ? "Built-in" : "Custom"}</small></td>
        <td>{category.detection}</td><td>{category.enabled ? "Enabled" : "Disabled"}</td>
        <td>{category.policy_ids.length}</td><td><button onClick={() => edit(category)}>View</button></td>
      </tr>)}</tbody>
    </table>{!page?.items.length && <p>No categories found.</p>}</div>}
    <div className="pagination"><button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous</button>
      <span>{page ? `${page.total} categories` : ""}</span>
      <button disabled={!page || offset + 20 >= page.total} onClick={() => setOffset(offset + 20)}>Next</button></div>
    {(selected || admin) && <section className="panel category-editor">
      <h2>{selected ? selected.name : "New custom category"}</h2>
      {selected?.builtin && <p>Built-in controls are protected. Assign them to draft policies below.</p>}
      <div className="category-form">
        <label>Name<input value={draft.name} disabled={!admin || !!selected?.builtin || busy} onChange={event => update({ name: event.target.value })} /></label>
        <label>Description<textarea value={draft.description} disabled={!admin || !!selected?.builtin || busy} onChange={event => update({ description: event.target.value })} /></label>
        {!selected?.builtin && <><label>Detector<select value={draft.detection} disabled={!admin || busy} onChange={event => update({ detection: event.target.value as Draft["detection"] })}>
          <option value="keyword">Keyword / phrase</option><option value="regex">Safe regex</option></select></label>
          <label>Action<select value={draft.action} disabled={!admin || busy} onChange={event => update({ action: event.target.value as Draft["action"] })}>
            <option>BLOCK</option><option>REDACT</option><option>HUMAN_REVIEW</option></select></label>
          <label>Patterns, one per line<textarea value={draft.values} disabled={!admin || busy} onChange={event => update({ values: event.target.value })} /></label>
          <label className="checkbox"><input type="checkbox" checked={draft.enabled} disabled={!admin || busy}
            onChange={event => update({ enabled: event.target.checked })} />Enabled</label></>}
      </div>
      {admin && !selected?.builtin && <div className="toolbar"><button className="primary" disabled={busy || !draft.name.trim() || !draft.values.trim()} onClick={() => void save()}>{selected ? "Save category" : "Create category"}</button>
        {selected && <button disabled={busy || selected.policy_ids.length > 0} onClick={() => void remove()}>Delete category</button>}</div>}
      {selected && <div><h3>Associated policies</h3>
        {selected.policy_ids.length === 0 ? <p>No policies assigned.</p> : <ul>{selected.policy_ids.map(id => <li key={id}>
          {policies.find(policy => policy.id === id)?.name || id}
          {admin && <button disabled={busy || policies.find(policy => policy.id === id)?.status !== "DRAFT"} onClick={() => void association(id, false)}>Unassign</button>}
        </li>)}</ul>}
        {admin && <div className="toolbar"><label>Assign draft policy<select value={policyId} disabled={busy} onChange={event => setPolicyId(event.target.value)}>
          <option value="">Choose a draft policy</option>{policies.filter(policy => policy.status === "DRAFT" && !selected.policy_ids.includes(policy.id)).map(policy => <option value={policy.id} key={policy.id}>{policy.name}</option>)}
        </select></label><button disabled={!policyId || busy} onClick={() => void association(policyId, true)}>Assign policy</button></div>}
      </div>}
    </section>}
  </div>;
}
