-- REVIEW ONLY. Run only after an approved 008 -> 011 upgrade, as the migration operator.
-- Grants the existing runtime role exactly the object rights the application checks
-- (backend/app/schema_compatibility.py) on the tables created by revisions 009 and 011.
-- Revision 010 only adds a nullable column to audit_events; the existing INSERT grant covers it.
SET XACT_ABORT ON;
IF DB_NAME() <> 'sqldb-gpv-demo-v008-20261108'
    THROW 51000, 'Unexpected database target', 1;
IF (SELECT COUNT(*) FROM dbo.alembic_version) <> 1
    OR (SELECT TOP (1) version_num FROM dbo.alembic_version) <> '011'
    THROW 51000, 'Revision 011 is required', 1;
IF DATABASE_PRINCIPAL_ID('governance_validator_web_runtime') IS NULL
    THROW 51000, 'Existing runtime role is required', 1;

BEGIN TRANSACTION;
GRANT SELECT, INSERT, UPDATE, DELETE ON dbo.governance_categories TO [governance_validator_web_runtime];
GRANT SELECT, INSERT, DELETE ON dbo.policy_categories TO [governance_validator_web_runtime];
GRANT SELECT, INSERT, UPDATE ON dbo.chat_conversations TO [governance_validator_web_runtime];
GRANT SELECT, INSERT ON dbo.chat_messages TO [governance_validator_web_runtime];
GRANT VIEW DEFINITION ON dbo.governance_categories TO [governance_validator_web_runtime];
GRANT VIEW DEFINITION ON dbo.policy_categories TO [governance_validator_web_runtime];
GRANT VIEW DEFINITION ON dbo.chat_conversations TO [governance_validator_web_runtime];
GRANT VIEW DEFINITION ON dbo.chat_messages TO [governance_validator_web_runtime];
COMMIT TRANSACTION;

-- Read-back (SELECT only):
SELECT o.name AS object_name, p.permission_name
FROM sys.database_permissions AS p
JOIN sys.objects AS o ON o.object_id = p.major_id
WHERE p.grantee_principal_id = DATABASE_PRINCIPAL_ID('governance_validator_web_runtime')
  AND o.name IN ('governance_categories', 'policy_categories', 'chat_conversations', 'chat_messages')
ORDER BY o.name, p.permission_name;
