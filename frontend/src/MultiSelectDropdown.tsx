import { useEffect, useId, useRef, useState } from "react";

export function MultiSelectDropdown({
  label,
  options,
  selected,
  available,
  unsupportedExplanation,
  allLabel,
  disabled = false,
  onChange,
}: {
  label: string;
  options: string[];
  selected: string[];
  available?: string[];
  unsupportedExplanation?: string;
  allLabel: string;
  disabled?: boolean;
  onChange: (values: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [showUnsupported, setShowUnsupported] = useState(false);
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
  const hiddenSelected = selected.filter((option) => !options.includes(option));
  const visible = options.filter((option) => option.toLowerCase().includes(search.trim().toLowerCase()))
    .sort((left, right) => Number(available !== undefined && !available.includes(left)) - Number(available !== undefined && !available.includes(right)));
  const supported = visible.filter((option) => available === undefined || available.includes(option));
  const unsupported = visible.filter((option) => available !== undefined && !available.includes(option));
  const allSupported = options.filter((option) => available === undefined || available.includes(option));
  const everySupportedSelected = allSupported.length > 0 && allSupported.every((option) => selected.includes(option)) && selected.length === allSupported.length;
  const names: Record<string, string> = {
    EMAIL_ADDRESS: "Email Address", PHONE_NUMBER: "Phone Number", CREDIT_CARD: "Credit Card Number",
    IN_AADHAAR: "Aadhaar Number", IN_PAN: "PAN Card Number", IBAN_CODE: "Bank Account / IBAN",
    PERSON: "Person Name", IP_ADDRESS: "IP Address", US_SSN: "US Social Security Number",
  };
  const display = (value: string) => names[value] || value.replaceAll("_", " ").replaceAll("/", " / ");
  function renderOption(value: string) {
    const unavailable = available !== undefined && !available.includes(value);
    const checked = selected.includes(value);
    return <label className="checkbox" key={value}>
      <input type="checkbox" checked={checked} disabled={unavailable && !checked} onChange={(event) => onChange(event.target.checked ? [...selected, value] : selected.filter((item) => item !== value))} />
      <span>{display(value)}{unavailable ? " (unavailable)" : ""}</span>
    </label>;
  }
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
            ? everySupportedSelected
              ? available === undefined ? `All ${allSupported.length} categories selected` : `All ${allSupported.length} supported entities selected`
              : `${selected.length} selected: ${selected.join(", ")}`
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
            {supported.map(renderOption)}
            {unsupported.length > 0 && <button type="button" className="unsupported-toggle" aria-expanded={showUnsupported} onClick={() => setShowUnsupported(!showUnsupported)}>{showUnsupported ? "Hide" : "Show"} unsupported detectors ({unsupported.length})</button>}
            {showUnsupported && unsupported.length > 0 && unsupportedExplanation && <p className="muted">{unsupportedExplanation}</p>}
            {showUnsupported && unsupported.map(renderOption)}
            {hiddenSelected.length > 0 && <p className="muted">Saved selections outside the main list</p>}
            {hiddenSelected.filter((option) => option.toLowerCase().includes(search.trim().toLowerCase())).map(renderOption)}
            {!visible.length && <p role="status">No matching options.</p>}
          </div>
          <div className="multi-select-footer">
            <button type="button" onClick={() => onChange(allSupported)}>Select All</button>
            <button type="button" onClick={() => onChange([])} disabled={!selected.length}>Clear Selection</button>
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
