### Revision 006 metadata delta from 005

- Added `execution_policy_evidence`: `tenant` VARCHAR(80) NOT NULL, `execution_id` VARCHAR(36) NOT NULL, `policy_id` VARCHAR(36) NOT NULL, `version_id` VARCHAR(36) NOT NULL, `set_revision` BIGINT NOT NULL, `document_sha256` CHAR(64) NOT NULL, `effective_decision` VARCHAR(12) NOT NULL, `inspection_status` VARCHAR(16) NOT NULL, `evidence_json` TEXT NOT NULL, `created_at` DATETIME NOT NULL.
- `policies`: index inventory changed; exact definitions in `metadata-contracts.json`.
- `policy_versions`: index inventory changed; exact definitions in `metadata-contracts.json`.
- `validation_executions.policy_id`: {"nullable": false, "primary_key": false, "server_default": null, "type": "VARCHAR(36)"} → {"nullable": true, "primary_key": false, "server_default": null, "type": "VARCHAR(36)"}.
- `validation_executions.version`: {"nullable": false, "primary_key": false, "server_default": null, "type": "INTEGER"} → {"nullable": true, "primary_key": false, "server_default": null, "type": "INTEGER"}.
- `validation_executions.execution_mode`: null → {"nullable": false, "primary_key": false, "server_default": "LEGACY", "type": "VARCHAR(6)"}.
- `validation_executions`: index inventory changed; exact definitions in `metadata-contracts.json`.
- `validation_executions`: constraint inventory changed; exact definitions in `metadata-contracts.json`.
- Added `workspace_policy_assignment_events`: `id` VARCHAR(36) NOT NULL, `tenant` VARCHAR(80) NOT NULL, `set_revision` BIGINT NOT NULL, `event_ordinal` INTEGER NOT NULL, `event_type` VARCHAR(16) NOT NULL, `policy_id` VARCHAR(36) NULL, `old_version_id` VARCHAR(36) NULL, `new_version_id` VARCHAR(36) NULL, `old_active` BOOLEAN NULL, `new_active` BOOLEAN NULL, `old_mode` VARCHAR(6) NULL, `new_mode` VARCHAR(6) NULL, `actor` VARCHAR(80) NOT NULL, `created_at` DATETIME NOT NULL.
- Added `workspace_policy_assignments`: `tenant` VARCHAR(80) NOT NULL, `policy_id` VARCHAR(36) NOT NULL, `version_id` VARCHAR(36) NOT NULL, `active` BOOLEAN NOT NULL, `changed_revision` BIGINT NOT NULL, `updated_at` DATETIME NOT NULL, `updated_by` VARCHAR(80) NOT NULL.
- Added `workspace_policy_states`: `tenant` VARCHAR(80) NOT NULL, `mode` VARCHAR(6) NOT NULL, `set_revision` BIGINT NOT NULL, `updated_at` DATETIME NOT NULL, `updated_by` VARCHAR(80) NOT NULL.

### Revision 007 metadata delta from 006

- `human_review_cases`: index inventory changed; exact definitions in `metadata-contracts.json`.
- Added `review_protected_content`: `tenant` VARCHAR(80) NOT NULL, `review_id` VARCHAR(36) NOT NULL, `content_kind` VARCHAR(20) NOT NULL, `format_version` INTEGER NOT NULL, `key_id` VARCHAR(64) NOT NULL, `nonce` BLOB NOT NULL, `ciphertext` BLOB NOT NULL, `created_at` BIGINT NOT NULL, `expires_at` BIGINT NOT NULL.
