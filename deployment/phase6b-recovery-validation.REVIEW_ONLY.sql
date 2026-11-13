-- PROPOSAL ONLY. Never executed during Phase 6B.
-- Run only on the exact isolated restore destination after approval B.
IF DB_NAME() <> N'sqldb-gpv-pitr-20261106-b1'
    THROW 51000, 'Restore destination mismatch; no validation allowed', 1;
SELECT DB_NAME() AS database_name, USER_NAME() AS executing_user,
       DATABASEPROPERTYEX(DB_NAME(), 'Collation') AS database_collation;
SELECT version_num FROM dbo.alembic_version;
SELECT N'audit_events' AS object_name, COUNT_BIG(*) AS records FROM dbo.audit_events
UNION ALL SELECT N'policy_versions', COUNT_BIG(*) FROM dbo.policy_versions
UNION ALL SELECT N'human_review_cases', COUNT_BIG(*) FROM dbo.human_review_cases;
SELECT COUNT_BIG(*) AS invalid_version_tenants FROM dbo.policy_versions v
LEFT JOIN dbo.policies p ON p.id=v.policy_id AND p.tenant=v.tenant WHERE p.id IS NULL;
SELECT COUNT_BIG(*) AS invalid_review_links FROM dbo.human_review_cases r
LEFT JOIN dbo.validation_executions e ON e.id=r.execution_id AND e.tenant=r.tenant WHERE e.id IS NULL;
SELECT name, is_disabled, is_not_trusted FROM sys.foreign_keys
WHERE is_disabled=1 OR is_not_trusted=1;
SELECT name, is_disabled, is_not_trusted FROM sys.check_constraints
WHERE is_disabled=1 OR is_not_trusted=1;
SELECT OBJECT_NAME(parent_id) AS object_name, name, is_disabled
FROM sys.triggers WHERE is_ms_shipped=0;
SELECT OBJECT_NAME(object_id) AS object_name, name, is_disabled, is_hypothetical, has_filter
FROM sys.indexes WHERE object_id IN
 (SELECT object_id FROM sys.tables WHERE schema_id=SCHEMA_ID(N'dbo'));
IF OBJECT_ID(N'dbo.review_protected_content',N'U') IS NOT NULL
BEGIN
 SELECT COUNT_BIG(*) AS retained_encrypted_rows,
        SUM(CASE WHEN expires_at<=DATEDIFF_BIG(SECOND,'1970-01-01',SYSUTCDATETIME()) THEN 1 ELSE 0 END) AS expired_rows
 FROM dbo.review_protected_content;
 SELECT name, TYPE_NAME(user_type_id) AS data_type, max_length, is_nullable
 FROM sys.columns WHERE object_id=OBJECT_ID(N'dbo.review_protected_content');
END;
-- Integrity work is confined to the restored database; no application is started.
DBCC CHECKDB WITH NO_INFOMSGS;
DBCC CHECKCONSTRAINTS WITH ALL_CONSTRAINTS;
-- No plaintext, ciphertext, cookie, session identifiers or credentials selected.
-- Preserve a separate approved known-record hash manifest; counts alone are insufficient.
