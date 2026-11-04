import { useEffect, useId, useRef, useState } from "react";

export function MultiSelectDropdown({
  label,
  options,
  selected,
  available,
  allLabel,
  disabled = false,
  onChange,
}: {
  label: string;
  options: string[];
  selected: string[];
  available?: string[];
  allLabel: string;
  disabled?: boolean;
  onChange: (values: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const searchInput = useRef<HTMLInputElement>(null);
  const panelId = useId();
  useEffect(() => {
    if (!open) return;
    searchInput.current?.focus();
    function outside(event: MouseEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", outside);
    return () => document.removeEventListener("mousedown", outside);
  }, [open]);
  const expanded = open && !disabled;
  const visible = options.filter((option) =>
    option.toLowerCase().includes(search.trim().toLowerCase()),
  );
  return (
    <div
      className="multi-select"
      ref={root}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node))
          setOpen(false);
      }}
      onKeyDown={(event) => {
        if (event.key === "Escape" && expanded) {
          event.preventDefault();
          event.stopPropagation();
          setOpen(false);
          trigger.current?.focus();
        }
      }}
    >
      <span className="multi-select-label">{label}</span>
      <button
        type="button"
        className="multi-select-trigger"
        ref={trigger}
        disabled={disabled}
        aria-label={label}
        aria-expanded={expanded}
        aria-controls={expanded ? panelId : undefined}
        onClick={() => {
          setSearch("");
          setOpen(!open);
        }}
      >
        <span>
          {selected.length
            ? `${selected.length} selected: ${selected.join(", ")}`
            : allLabel}
        </span>
        <span aria-hidden="true">{expanded ? "▴" : "▾"}</span>
      </button>
      {expanded && (
        <div className="multi-select-panel" id={panelId}>
          <input
            ref={searchInput}
            type="search"
            aria-label={`Search ${label}`}
            placeholder="Search options…"
            value={search}
            onKeyDown={(event) => {
              if (event.key === "Enter") event.preventDefault();
            }}
            onChange={(event) => setSearch(event.target.value)}
          />
          <div
            className="multi-select-options"
            role="group"
            aria-label={`${label} options`}
          >
            {visible.map((value) => {
              const unavailable =
                available !== undefined && !available.includes(value);
              const checked = selected.includes(value);
              return (
                <label className="checkbox" key={value}>
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={unavailable && !checked}
                    onChange={(event) =>
                      onChange(
                        event.target.checked
                          ? [...selected, value]
                          : selected.filter((item) => item !== value),
                      )
                    }
                  />
                  <span>
                    {value}
                    {unavailable ? " (unavailable)" : ""}
                  </span>
                </label>
              );
            })}
            {!visible.length && <p role="status">No matching options.</p>}
          </div>
          <div className="multi-select-footer">
            <button
              type="button"
              onClick={() => onChange([])}
              disabled={!selected.length}
            >
              Use all (default)
            </button>
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                trigger.current?.focus();
              }}
            >
              Done
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
