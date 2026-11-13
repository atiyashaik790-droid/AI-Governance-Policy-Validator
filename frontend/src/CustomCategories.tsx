export type CustomCategory = {
  id: string; name: string; description: string; enabled: boolean;
  action: "BLOCK" | "REDACT" | "HUMAN_REVIEW";
  detection: "keyword" | "regex"; values: string[];
};

export function CustomCategories({ categories, admin, onChange }: {
  categories: CustomCategory[]; admin: boolean; onChange: (categories: CustomCategory[]) => void;
}) {
  function update(index: number, change: Partial<CustomCategory>) {
    onChange(categories.map((category, i) => i === index ? { ...category, ...change } : category));
  }
  return <section aria-label="Custom rule categories">
    <h2>Custom rule categories</h2>
    {!admin && <p>Only Admin users can configure custom categories.</p>}
    {categories.map((category, index) => <fieldset className="rule" key={category.id} disabled={!admin}>
      <label className="checkbox"><input type="checkbox" checked={category.enabled}
        onChange={event => update(index, { enabled: event.target.checked })} /><strong>{category.name || "Custom category"}</strong></label>
      <label>Category name<input required maxLength={120} value={category.name}
        onChange={event => update(index, { name: event.target.value })} /></label>
      <label>Category description<textarea maxLength={1000} value={category.description}
        onChange={event => update(index, { description: event.target.value })} /></label>
      <label>Category action<select value={category.action}
        onChange={event => update(index, { action: event.target.value as CustomCategory["action"] })}>
        {["BLOCK", "REDACT", "HUMAN_REVIEW"].map(action => <option key={action}>{action}</option>)}
      </select></label>
      <label>Detection method<select value={category.detection}
        onChange={event => update(index, { detection: event.target.value as CustomCategory["detection"] })}>
        <option value="keyword">Keyword / phrase</option><option value="regex">Safe regex</option>
      </select></label>
      <label>Patterns (one per line)<textarea required value={category.values.join("\n")}
        onChange={event => update(index, { values: event.target.value.split("\n") })} /></label>
      <p>Case insensitive. Up to 10 patterns of 200 characters. Regex supports literals, character classes, anchors and quantifiers; groups, alternatives and backreferences are unavailable. Repetition counts are limited to 1000. Inspection timeouts block release.</p>
      {admin && <button type="button" onClick={() => onChange(categories.filter((_, i) => i !== index))}>Remove category</button>}
    </fieldset>)}
    {admin && <button type="button" disabled={categories.length >= 20} onClick={() => onChange([...categories, {
      id: crypto.randomUUID(), name: "", description: "", enabled: true, action: "BLOCK", detection: "keyword", values: [""],
    }])}>Add custom category</button>}
  </section>;
}
