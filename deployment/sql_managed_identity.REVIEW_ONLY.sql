-- REVIEW ONLY. No migrations or existing-principal changes. Requires specific approval.
-- Replace the client/application UUID AFTER verifying it belongs to the approved Web App object ID.
-- Application SQL SIDs use client ID; token oid pinning still uses the principal object ID.
SET XACT_ABORT ON;
IF DB_NAME() <> N'sqldb-governance-validator-dev'
    THROW 51000, 'Wrong target database; stopped.', 1;
IF HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'CONTROL') <> 1
    THROW 51000, 'Approved database administrator required.', 1;
IF (SELECT COUNT(*) FROM dbo.alembic_version) <> 1
   OR NOT EXISTS (SELECT 1 FROM dbo.alembic_version WHERE version_num = '003')
    THROW 51000, 'Expected revision 003; no migrations allowed.', 1;
DECLARE @expected_client_id uniqueidentifier = TRY_CONVERT(uniqueidentifier, 'REPLACE_WITH_NEW_WEB_APP_CLIENT_ID');
IF @expected_client_id IS NULL THROW 51000, 'Supply reviewed system-assigned client ID.', 1;
IF DATABASE_PRINCIPAL_ID(N'app-governance-validator-atiya-1026') IS NOT NULL
   OR DATABASE_PRINCIPAL_ID(N'governance_validator_web_runtime') IS NOT NULL
    THROW 51000, 'Principal/role already exists; review separately, do not retry.', 1;
BEGIN TRY
    BEGIN TRANSACTION;
    CREATE USER [app-governance-validator-atiya-1026] FROM EXTERNAL PROVIDER;
    IF NOT EXISTS (SELECT 1 FROM sys.database_principals
                   WHERE name = N'app-governance-validator-atiya-1026'
                   AND type = 'E' AND CONVERT(uniqueidentifier, sid) = @expected_client_id)
        THROW 51000, 'Resolved identity mismatch; stopped.', 1;
    CREATE ROLE [governance_validator_web_runtime] AUTHORIZATION dbo;
    GRANT CONNECT TO [governance_validator_web_runtime];
    GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.policies TO [governance_validator_web_runtime];
    GRANT SELECT, INSERT ON dbo.policy_versions TO [governance_validator_web_runtime];
    GRANT SELECT, INSERT, UPDATE ON dbo.active_policy_assignments TO [governance_validator_web_runtime];
    GRANT SELECT, INSERT ON dbo.audit_events TO [governance_validator_web_runtime];
    GRANT SELECT, INSERT ON dbo.validation_executions TO [governance_validator_web_runtime];
    GRANT SELECT, INSERT, UPDATE ON dbo.human_review_cases TO [governance_validator_web_runtime];
    GRANT SELECT, INSERT ON dbo.feedback_records TO [governance_validator_web_runtime];
    GRANT SELECT, INSERT, UPDATE ON dbo.evaluation_exports TO [governance_validator_web_runtime];
    ALTER ROLE [governance_validator_web_runtime] ADD MEMBER [app-governance-validator-atiya-1026];
    COMMIT;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK;
    THROW;
END CATCH;
-- No DDL privileges, fixed database roles or alembic_version permissions are granted.
