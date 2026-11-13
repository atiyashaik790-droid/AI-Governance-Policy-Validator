# AI Playground document uploads

Authenticated users with the existing governance roles (Admin, Developer, Policy
Owner) can attach one PDF, DOCX or UTF-8 TXT file. The picker displays filename,
type and byte size and supports replacement and removal. Prompt-only requests
retain their existing endpoints and behavior. Reading, extraction/inspection and
completion/error states appear in the Playground.

The browser sends base64 JSON to `POST /api/governance/generate-document` or
`POST /api/v2/governance/generate-document`. MULTI requires the existing strong
workspace `If-Match` validator. SSO, CSRF and server-side roles apply unchanged.
No client-supplied extracted text or tenant is accepted. Extraction is limited to
five attempts per user/tenant/minute (or the lower configured governance limit),
including invalid files. Existing governance reservations, quotas, captured pins,
fencing and deadlines still apply after extraction.

Limits:

- File: 1–262,144 bytes (256 KiB); JSON request body: 400,000 bytes.
- Extracted text: 10,000 characters; prompt plus full extracted text and generated
  boundaries: 12,000 characters. Nothing is truncated to fit.
- PDF: 1–20 pages; 2 MiB decoded page-content budget. Every page needs text.
- DOCX: 128 ZIP entries, 2 MiB total expansion, 512 KiB per entry and 100:1 maximum
  compression ratio. XML DTDs/entities, duplicate/unsafe paths, encryption and
  unsafe compression methods are rejected; archive entries are never unpacked.
- Extraction: two workers per API process; five-second wall deadline, three CPU
  seconds, 256 MiB address-space limit, no core dumps or file writes. Worker
  failure, cancellation, parse warnings or incomplete extraction release nothing.

Parsing is isolated in a short-lived Python worker using memory-only pipes;
raw files never go to disk and no temporary-file cleanup is required. Worker
errors and stderr cannot expose source text to server logs. Audit data includes
only file type, byte count, extracted-character count and the existing sanitized
governance evidence. Filenames, raw files, extracted text and matched strings
are excluded. The worker receives no provider credentials or application secrets.

The full prompt and document pass through the existing LEGACY or MULTI engine,
including built-in and custom categories. BLOCK/HUMAN_REVIEW prevent generation;
REDACT uses existing reinspection. Output inspection, a maximum of one generation
dispatch and reservation fencing are unchanged. A mode/revision change during
extraction is checked again by governance admission.

Supported content is deliberately text-only. Images (including mixed text/image
PDFs), blank PDF pages, PDF forms/annotations/actions/attachments, DOCX drawings,
fields, macros, embedded objects and external relationships are rejected. DOCX
body, tables, headers, footers, comments and notes contribute their stored text.
There is no OCR, external-content loading, macro execution or layout guarantee.
Complex or unusually compressed valid documents can be rejected by safety limits.

Runtime: Linux/POSIX resource limits and the pinned `pypdf==6.21.4` dependency are
required. No database migration is needed. This feature has local validation only.
