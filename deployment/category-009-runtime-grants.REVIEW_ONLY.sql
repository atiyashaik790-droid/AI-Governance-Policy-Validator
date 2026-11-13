SET XACT_ABORT ON;
IF DB_NAME() <> 'sqldb-gpv-demo-v008-20261108'
    THROW 51000, 'Unexpected database target', 1;
IF (SELECT COUNT(*) FROM dbo.alembic_version) <> 1
    OR (SELECT TOP (1) version_num FROM dbo.alembic_version) <> '009'
    THROW 51000, 'Revision 009 is required', 1;
IF DATABASE_PRINCIPAL_ID('governance_validator_web_runtime') IS NULL
    THROW 51000, 'Existing runtime role is required', 1;

BEGIN TRANSACTION;
GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.governance_categories TO [governance_validator_web_runtime];
GRANT SELECT, INSERT, DELETE ON dbo.policy_categories TO [governance_validator_web_runtime];
GRANT VIEW DEFINITION ON dbo.governance_categories TO [governance_validator_web_runtime];
GRANT VIEW DEFINITION ON dbo.policy_categories TO [governance_validator_web_runtime];
COMMIT TRANSACTION;
