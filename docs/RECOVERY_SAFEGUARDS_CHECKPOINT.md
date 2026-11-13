# Recovery safeguards checkpoint — BLOCKED

9 November 2026. No production key, App Service setting, Azure SQL database or deployed release was changed in this checkpoint. The existing old005 site remains healthy; prior seed and hosted new008 managed-identity proofs remain valid.

| Gate | Result | Evidence / exact gap |
|---|---|---|
| Isolated PITR restore | BLOCKED | Backup window and same-server restore capability reviewed in `RESTORE_DRILL_APPROVAL_PREPARATION.md`. Sole operator has SQL management rights, but no independent certified cleanup executor or billed-resource approval. See `SOLE_OPERATOR_RECOVERY_INVESTIGATION.md`. |
| Off-host review-key recovery | BLOCKED | Existing encrypted envelope exists, mode0600 in mode0700 directory; prior in-memory same-workstation recovery verified. Existing reports container is accessible to app MI; no Key Vault exists. Need a private approved backup destination and separately recoverable wrapping secret; verify decrypted settings in memory, print only PASS/FAIL. |
| App Service settings rollback | BLOCKED | Sole operator nominated and effective Web App config/deploy rights verified. Current old005 target, MI mode/object, key presence and absent review flags checked without secrets. Local exact-field rollback simulation passed; App Service settings response had no strong ETag and multiple inherited writer roles exist. Need enforceable exclusive writer boundary, independently recoverable encrypted baseline, and approved restoration proof. No live settings write was attempted. |
| Release/rollback compatibility | PARTIAL | Candidate, paired old005 ZIP and separate008-compatible rollback ZIP hashes verified. Old005 artifact pairs only with old005 connection; new008-only writes remain on new008. Actual deployment/rollback rehearsal blocked by above gates. |

No cutover approval request is appropriate while these gates are open. The prepared demo script remains conditional and hosted acceptance remains BLOCKED.
