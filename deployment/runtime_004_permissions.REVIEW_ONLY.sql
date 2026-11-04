-- REVIEW ONLY. Applies no migrations. Execute only after explicit permission-change approval.
-- Existing approved runtime role only; do not create principals or grant database-wide access.
SET XACT_ABORT ON;
IF DB_NAME() <> N'sqldb-governance-validator-dev'
    THROW 51000, 'Wrong database; stopped.', 1;
IF NOT EXISTS (SELECT 1 FROM dbo.alembic_version WHERE version_num = '004')
    THROW 51000, 'Reviewed migration 004 must be applied first.', 1;
IF DATABASE_PRINCIPAL_ID(N'governance_validator_web_runtime') IS NULL
    THROW 51000, 'Expected existing role absent; inspect the actual approved role.', 1;
BEGIN TRANSACTION;
GRANT SELECT ON dbo.alembic_version TO [governance_validator_web_runtime];
GRANT SELECT, INSERT, UPDATE ON dbo.demo_sessions TO [governance_validator_web_runtime];
GRANT SELECT, INSERT, UPDATE ON dbo.inference_rate_buckets TO [governance_validator_web_runtime];
GRANT SELECT, INSERT, UPDATE ON dbo.inference_usage TO [governance_validator_web_runtime];
GRANT SELECT, INSERT, UPDATE ON dbo.export_jobs TO [governance_validator_web_runtime];
GRANT SELECT, INSERT, UPDATE ON dbo.review_assignments TO [governance_validator_web_runtime];
GRANT SELECT, INSERT ON dbo.review_notes TO [governance_validator_web_runtime];
COMMIT;
-- No DELETE, ALTER, CONTROL, role membership or existing history-write grants are added.
