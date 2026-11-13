import { useState } from "react";

export const MAX_ATTACHMENT_BYTES = 256 * 1024;
export function attachmentBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Attachment could not be read. Remove it or select it again."));
    reader.onabort = () => reject(new Error("Attachment reading was cancelled."));
    reader.onload = () => {
      const value = String(reader.result).split(",")[1];
      if (!value) reject(new Error("Attachment is empty or unreadable."));
      else resolve(value);
    };
    reader.readAsDataURL(file);
  });
}

export function AttachmentPicker({ file, disabled, onChange }: {
  file: File | null; disabled: boolean; onChange: (file: File | null) => void;
}) {
  const [error, setError] = useState("");
  return <section aria-label="Document attachment">
    <label>Attach PDF, DOCX or TXT<input type="file" accept=".pdf,.docx,.txt" disabled={disabled}
      onChange={event => {
        const next = event.target.files?.[0];
        event.target.value = "";
        if (!next) return;
        onChange(null); setError("");
        if (!/\.(pdf|docx|txt)$/i.test(next.name)) setError("Choose a PDF, DOCX or UTF-8 TXT file.");
        else if (!next.size || next.size > MAX_ATTACHMENT_BYTES) setError("File must contain 1 byte to 256 KiB.");
        else onChange(next);
      }} /></label>
    {file && <div className="rule" aria-label="Attachment preview">
      <strong>{file.name}</strong><p>Type: {file.type || file.name.split(".").pop()?.toUpperCase()} · Size: {file.size.toLocaleString()} bytes</p>
      <button type="button" disabled={disabled} onClick={() => { onChange(null); setError(""); }}>Remove attachment</button>
    </div>}
    {error && <p role="alert">{error}</p>}
    <p className="muted">Maximum 256 KiB; 10,000 extracted characters and 12,000 total with prompt and boundaries. Text-only documents; no OCR, encrypted files, embedded content or external links. Raw attachments are not retained.</p>
  </section>;
}
