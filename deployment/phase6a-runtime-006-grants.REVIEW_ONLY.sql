-- PHASE 6A PROPOSAL ONLY. NOT AUTHORIZED, NOT EXECUTED.
-- Apply only after separately approved migration 006 and exact identity review.
-- Coordinate object visibility/DML within the approved maintenance boundary.
SET XACT_ABORT ON;
DECLARE @explicit_approval bit = 0; -- Operator may change only under fresh approval.
IF @explicit_approval <> 1 THROW 51000, 'Permission change not approved', 1;
IF DB_NAME() <> N'sqldb-governance-validator-dev' THROW 51000, 'Wrong database', 1;
IF (SELECT COUNT(*) FROM dbo.alembic_version) <> 1
 OR NOT EXISTS (SELECT 1 FROM dbo.alembic_version WHERE version_num=N'006')
 THROW 51000, 'Wrong migration boundary', 1;
DECLARE @confirmed_runtime_client_id uniqueidentifier =
 TRY_CONVERT(uniqueidentifier, N'REPLACE_WITH_RECONFIRMED_CONTAINED_MI_CLIENT_ID');
IF @confirmed_runtime_client_id IS NULL THROW 51000, 'Identity confirmation required', 1;
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name=N'app-governance-validator-atiya-1026'
 AND type='E' AND DATALENGTH(sid)=16 AND TRY_CONVERT(uniqueidentifier,sid)=@confirmed_runtime_client_id)
 THROW 51000, 'Contained runtime identity mismatch', 1;
IF NOT EXISTS (SELECT 1 FROM sys.database_role_members rm
 JOIN sys.database_principals r ON r.principal_id=rm.role_principal_id
 JOIN sys.database_principals m ON m.principal_id=rm.member_principal_id
 WHERE r.name=N'governance_validator_web_runtime' AND r.type='R' AND r.is_fixed_role=0
 AND m.name=N'app-governance-validator-atiya-1026')
 THROW 51000, 'Existing role membership required', 1;
IF OBJECT_ID(N'dbo.workspace_policy_states',N'U') IS NULL THROW 51000, 'Required table absent', 1;
IF OBJECT_ID(N'dbo.workspace_policy_assignments',N'U') IS NULL THROW 51000, 'Required table absent', 1;
IF OBJECT_ID(N'dbo.workspace_policy_assignment_events',N'U') IS NULL THROW 51000, 'Required table absent', 1;
IF OBJECT_ID(N'dbo.execution_policy_evidence',N'U') IS NULL THROW 51000, 'Required table absent', 1;
BEGIN TRY
 BEGIN TRANSACTION;
 GRANT SELECT, INSERT, UPDATE ON OBJECT::dbo.workspace_policy_states TO [governance_validator_web_runtime];
 GRANT VIEW DEFINITION ON OBJECT::dbo.workspace_policy_states TO [governance_validator_web_runtime];
 GRANT SELECT, INSERT, UPDATE ON OBJECT::dbo.workspace_policy_assignments TO [governance_validator_web_runtime];
 GRANT VIEW DEFINITION ON OBJECT::dbo.workspace_policy_assignments TO [governance_validator_web_runtime];
 GRANT SELECT, INSERT ON OBJECT::dbo.workspace_policy_assignment_events TO [governance_validator_web_runtime];
 GRANT VIEW DEFINITION ON OBJECT::dbo.workspace_policy_assignment_events TO [governance_validator_web_runtime];
 GRANT SELECT, INSERT ON OBJECT::dbo.execution_policy_evidence TO [governance_validator_web_runtime];
 GRANT VIEW DEFINITION ON OBJECT::dbo.execution_policy_evidence TO [governance_validator_web_runtime];
 COMMIT;
END TRY
BEGIN CATCH
 IF @@TRANCOUNT > 0 ROLLBACK;
 THROW;
END CATCH;
-- No identity creation, broad roles, schema-wide grants or DDL granted to runtime.
-- No automatic REVOKE rollback: preserve cleanup/access to retained 007 content.
