-- REVIEW ONLY. NOT EXECUTED. Requires explicit permission-change approval.
-- Existing role/user only. Confirm the Web App identity/client ID before filling guard.
-- This is not the Governance-Studio-SSO client ID.
SET XACT_ABORT ON;
IF DB_NAME() <> N'sqldb-governance-validator-dev'
    THROW 51000, 'Wrong database; stopped', 1;
IF (SELECT COUNT(*) FROM dbo.alembic_version) <> 1
   OR NOT EXISTS (SELECT 1 FROM dbo.alembic_version WHERE version_num=N'005')
    THROW 51000, 'Exactly reviewed revision 005 required', 1;
IF NOT EXISTS (SELECT 1 FROM sys.database_principals
               WHERE name=N'governance_validator_web_runtime' AND type='R' AND is_fixed_role=0)
    THROW 51000, 'Expected existing application runtime role absent', 1;
DECLARE @confirmed_mi_client_id uniqueidentifier =
    TRY_CONVERT(uniqueidentifier,N'REPLACE_WITH_CONFIRMED_WEB_APP_MI_CLIENT_ID');
IF @confirmed_mi_client_id IS NULL
    THROW 51000, 'Confirm existing managed identity client ID; not SSO registration ID', 1;
IF NOT EXISTS (SELECT 1 FROM sys.database_principals
               WHERE name=N'app-governance-validator-atiya-1026' AND type='E'
                 AND DATALENGTH(sid)=16
                 AND TRY_CONVERT(uniqueidentifier,sid)=@confirmed_mi_client_id)
    THROW 51000, 'Existing contained runtime user identity must match', 1;
IF NOT EXISTS (SELECT 1 FROM sys.database_role_members rm
               JOIN sys.database_principals r ON rm.role_principal_id=r.principal_id
               JOIN sys.database_principals m ON rm.member_principal_id=m.principal_id
               WHERE r.name=N'governance_validator_web_runtime'
                 AND m.name=N'app-governance-validator-atiya-1026')
    THROW 51000, 'Existing runtime role membership must be verified; do not create it here', 1;
BEGIN TRY
    BEGIN TRANSACTION;
    GRANT SELECT ON dbo.sso_memberships TO [governance_validator_web_runtime];
    GRANT SELECT, INSERT, UPDATE ON dbo.sso_transactions TO [governance_validator_web_runtime];
    GRANT SELECT, INSERT, UPDATE ON dbo.sso_sessions TO [governance_validator_web_runtime];
    COMMIT;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT>0 ROLLBACK;
    THROW;
END CATCH;
-- No membership writes, DELETE, DDL, role changes, broad database grants or new users.
-- Coordinate new-table visibility with the approved migration transaction so that
-- the compatibility readiness check does not observe 005 without metadata access.
