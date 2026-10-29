-- REVIEW ONLY. Database/security mutations: execute only after explicit approval.
-- Run as the existing Entra administrator, connected directly to the named database.
-- Replace both placeholders privately with a separate, non-admin organizational USER.
SET NOCOUNT ON;
SET XACT_ABORT ON;
DECLARE @RuntimeUPN nvarchar(128) = N'<RUNTIME_ORGANIZATIONAL_UPN>';
DECLARE @RuntimeObjectId uniqueidentifier = '<RUNTIME_USER_OBJECT_ID>';
IF DB_NAME() <> N'sqldb-governance-validator-dev'
    THROW 51000, 'Wrong database; stopped.', 1;
IF @RuntimeUPN LIKE N'<%' OR LEN(@RuntimeUPN) = 0
    THROW 51000, 'Replace reviewed identity placeholders; stopped.', 1;
IF USER_NAME() <> N'dbo' OR HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'CONTROL') <> 1
    THROW 51000, 'Use the reviewed administrator context; stopped.', 1;
IF OBJECT_ID(N'dbo.alembic_version', N'U') IS NULL
    THROW 51000, 'Missing migration history; stopped.', 1;
IF (SELECT COUNT(*) FROM dbo.alembic_version) <> 1
    OR NOT EXISTS (SELECT 1 FROM dbo.alembic_version WHERE version_num = '003')
    THROW 51000, 'Unexpected migration revision; stopped.', 1;
IF EXISTS (SELECT 1 FROM sys.database_principals WHERE name IN (@RuntimeUPN, N'governance_validator_runtime'))
    THROW 51000, 'User or role already exists; review before changing existing access.', 1;
IF EXISTS (SELECT 1 FROM sys.database_principals WHERE sid = CONVERT(binary(16), @RuntimeObjectId))
    THROW 51000, 'Identity already mapped; review existing permissions first.', 1;
BEGIN TRY
    BEGIN TRANSACTION;
    DECLARE @CreateUser nvarchar(max) = N'CREATE USER ' + QUOTENAME(@RuntimeUPN)
        + N' FROM EXTERNAL PROVIDER WITH DEFAULT_SCHEMA = dbo;';
    EXEC sys.sp_executesql @CreateUser;
    IF NOT EXISTS (SELECT 1 FROM sys.database_principals
                   WHERE name = @RuntimeUPN AND type = 'E'
                     AND sid = CONVERT(binary(16), @RuntimeObjectId))
        THROW 51000, 'Resolved identity does not match the approved object ID.', 1;
    CREATE ROLE [governance_validator_runtime] AUTHORIZATION [dbo];
    GRANT CONNECT TO [governance_validator_runtime];
    GRANT SELECT, INSERT, UPDATE, DELETE ON OBJECT::dbo.policies TO [governance_validator_runtime];
    GRANT SELECT, INSERT ON OBJECT::dbo.policy_versions TO [governance_validator_runtime];
    GRANT SELECT, INSERT, UPDATE ON OBJECT::dbo.active_policy_assignments TO [governance_validator_runtime];
    GRANT SELECT, INSERT ON OBJECT::dbo.audit_events TO [governance_validator_runtime];
    GRANT SELECT, INSERT ON OBJECT::dbo.validation_executions TO [governance_validator_runtime];
    GRANT SELECT, INSERT, UPDATE ON OBJECT::dbo.human_review_cases TO [governance_validator_runtime];
    GRANT SELECT, INSERT ON OBJECT::dbo.feedback_records TO [governance_validator_runtime];
    GRANT SELECT, INSERT, UPDATE ON OBJECT::dbo.evaluation_exports TO [governance_validator_runtime];
    DECLARE @AddMember nvarchar(max) = N'ALTER ROLE [governance_validator_runtime] ADD MEMBER '
        + QUOTENAME(@RuntimeUPN) + N';';
    EXEC sys.sp_executesql @AddMember;
    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
-- No ownership transfer, broad schema grants, fixed-role membership or migrations.
