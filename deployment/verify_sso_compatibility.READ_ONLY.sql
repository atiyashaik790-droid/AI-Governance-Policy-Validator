-- READ ONLY. Run under an authorized identity against the exact existing database.
-- No grants, migrations, credential operations, business-row reads or resource changes.
-- Schema absence and lack of metadata visibility must be distinguished by an operator.
DECLARE @expected_database sysname=N'sqldb-governance-validator-dev';
DECLARE @sso_enabled bit=0; -- Reviewed rollout intention; change only in this query text.
IF DB_NAME()<>@expected_database THROW 51000,'Wrong database; stop',1;
SELECT DB_NAME() AS database_name, USER_NAME() AS database_principal,
       SCHEMA_NAME() AS default_schema, SYSUTCDATETIME() AS observed_utc,
       SERVERPROPERTY('EngineEdition') AS engine_edition;
IF OBJECT_ID(N'dbo.alembic_version',N'U') IS NULL
    THROW 51000,'Alembic history missing or not visible; stop',1;
SELECT version_num FROM dbo.alembic_version;
DECLARE @revision varchar(32);
SELECT @revision=CASE WHEN COUNT(*)=1 THEN MAX(version_num) ELSE NULL END FROM dbo.alembic_version;
SELECT @revision AS observed_revision,
       CASE WHEN @revision IN ('004','005') THEN 'SUPPORTED_REVIEWED_REVISION' ELSE 'STOP' END AS compatibility;
WITH expected(table_name,minimum_revision) AS (VALUES
(N'active_policy_assignments',N'004'),
(N'audit_events',N'004'),
(N'demo_sessions',N'004'),
(N'evaluation_exports',N'004'),
(N'export_jobs',N'004'),
(N'feedback_records',N'004'),
(N'human_review_cases',N'004'),
(N'inference_rate_buckets',N'004'),
(N'inference_usage',N'004'),
(N'policies',N'004'),
(N'policy_versions',N'004'),
(N'review_assignments',N'004'),
(N'review_notes',N'004'),
(N'sso_memberships',N'005'),
(N'sso_sessions',N'005'),
(N'sso_transactions',N'005'),
(N'validation_executions',N'004'))
SELECT e.*,CASE WHEN minimum_revision<=@revision THEN 1 ELSE 0 END AS required_now,
       CASE WHEN OBJECT_ID(N'dbo.'+table_name,N'U') IS NULL THEN 'MISSING_OR_NOT_VISIBLE' ELSE 'PRESENT' END AS object_status,
       HAS_PERMS_BY_NAME(N'dbo.'+table_name,'OBJECT','VIEW DEFINITION') AS can_view_definition
FROM expected e ORDER BY table_name;
WITH expected(table_name,column_name,expected_length,expected_nullable) AS (VALUES
(N'audit_events',N'id',36,0),
(N'audit_events',N'tenant',80,0),
(N'audit_events',N'actor',80,0),
(N'audit_events',N'action',80,0),
(N'audit_events',N'resource',80,0),
(N'audit_events',N'created',40,0),
(N'demo_sessions',N'id',64,0),
(N'demo_sessions',N'tenant',80,0),
(N'demo_sessions',N'actor',100,0),
(N'demo_sessions',N'role',30,0),
(N'demo_sessions',N'credential_hash',64,0),
(N'demo_sessions',N'expires',40,0),
(N'demo_sessions',N'revoked',NULL,0),
(N'demo_sessions',N'created',40,0),
(N'evaluation_exports',N'id',36,0),
(N'evaluation_exports',N'tenant',80,0),
(N'evaluation_exports',N'status',20,0),
(N'evaluation_exports',N'path',300,0),
(N'evaluation_exports',N'created',40,0),
(N'inference_rate_buckets',N'id',64,0),
(N'inference_rate_buckets',N'used',NULL,0),
(N'inference_rate_buckets',N'expires',40,0),
(N'inference_usage',N'id',36,0),
(N'inference_usage',N'tenant',80,0),
(N'inference_usage',N'actor',100,0),
(N'inference_usage',N'status',30,0),
(N'inference_usage',N'expires',40,0),
(N'inference_usage',N'created',40,0),
(N'inference_usage',N'finished',40,1),
(N'inference_usage',N'prompt_tokens',NULL,1),
(N'inference_usage',N'completion_tokens',NULL,1),
(N'policies',N'id',36,0),
(N'policies',N'tenant',80,0),
(N'policies',N'name',120,0),
(N'policies',N'draft',NULL,0),
(N'policies',N'status',20,0),
(N'policies',N'enabled',NULL,0),
(N'policies',N'revision',NULL,0),
(N'policies',N'row_version',NULL,0),
(N'sso_memberships',N'id',36,0),
(N'sso_memberships',N'directory_tenant',36,0),
(N'sso_memberships',N'object_id',36,0),
(N'sso_memberships',N'tenant',80,0),
(N'sso_memberships',N'actor',80,0),
(N'sso_memberships',N'role',30,0),
(N'sso_memberships',N'enabled',NULL,0),
(N'sso_transactions',N'id',64,0),
(N'sso_transactions',N'binding_hash',64,0),
(N'sso_transactions',N'nonce',100,0),
(N'sso_transactions',N'verifier',128,0),
(N'sso_transactions',N'return_path',500,0),
(N'sso_transactions',N'expires',40,0),
(N'sso_transactions',N'consumed',NULL,0),
(N'validation_executions',N'id',36,0),
(N'validation_executions',N'tenant',80,0),
(N'validation_executions',N'actor',80,0),
(N'validation_executions',N'policy_id',36,0),
(N'validation_executions',N'version',NULL,0),
(N'validation_executions',N'model',120,0),
(N'validation_executions',N'decision',20,0),
(N'validation_executions',N'metadata_json',NULL,0),
(N'validation_executions',N'created',40,0),
(N'export_jobs',N'id',36,0),
(N'export_jobs',N'tenant',80,0),
(N'export_jobs',N'idempotency_key',100,0),
(N'export_jobs',N'request_hash',64,0),
(N'export_jobs',N'content_hash',64,0),
(N'export_jobs',N'content',NULL,0),
(N'export_jobs',N'state',20,0),
(N'export_jobs',N'attempts',NULL,0),
(N'export_jobs',N'lease_until',40,0),
(N'export_jobs',N'error_code',50,0),
(N'export_jobs',N'created',40,0),
(N'export_jobs',N'updated',40,0),
(N'feedback_records',N'id',36,0),
(N'feedback_records',N'tenant',80,0),
(N'feedback_records',N'execution_id',36,0),
(N'feedback_records',N'rating',NULL,0),
(N'human_review_cases',N'id',36,0),
(N'human_review_cases',N'tenant',80,0),
(N'human_review_cases',N'execution_id',36,0),
(N'human_review_cases',N'status',40,0),
(N'human_review_cases',N'created',40,0),
(N'human_review_cases',N'row_version',NULL,0),
(N'policy_versions',N'id',36,0),
(N'policy_versions',N'policy_id',36,0),
(N'policy_versions',N'tenant',80,0),
(N'policy_versions',N'number',NULL,0),
(N'policy_versions',N'document',NULL,0),
(N'policy_versions',N'created',40,0),
(N'sso_sessions',N'id',64,0),
(N'sso_sessions',N'membership_id',36,0),
(N'sso_sessions',N'expires',40,0),
(N'sso_sessions',N'revoked',NULL,0),
(N'active_policy_assignments',N'tenant',80,0),
(N'active_policy_assignments',N'version_id',36,0),
(N'review_assignments',N'id',36,0),
(N'review_assignments',N'tenant',80,0),
(N'review_assignments',N'assigned_reviewer',100,0),
(N'review_assignments',N'reason',1000,0),
(N'review_assignments',N'updated',40,0),
(N'review_notes',N'id',36,0),
(N'review_notes',N'review_id',36,0),
(N'review_notes',N'tenant',80,0),
(N'review_notes',N'actor',100,0),
(N'review_notes',N'action',40,0),
(N'review_notes',N'reason',1000,0),
(N'review_notes',N'created',40,0))
SELECT e.*,ty.name AS actual_type,c.max_length AS actual_bytes,c.is_nullable AS actual_nullable,
       CASE WHEN c.column_id IS NULL THEN 'MISSING_OR_NOT_VISIBLE'
            WHEN c.is_nullable<>e.expected_nullable THEN 'NULLABILITY_MISMATCH'
            WHEN e.expected_length IS NOT NULL AND
              (CASE WHEN ty.name IN ('nvarchar','nchar') THEN c.max_length/2 ELSE c.max_length END)<>e.expected_length
              THEN 'LENGTH_MISMATCH' ELSE 'REVIEW_TYPE_AND_VERSION' END AS column_status
FROM expected e LEFT JOIN sys.columns c ON c.object_id=OBJECT_ID(N'dbo.'+e.table_name) AND c.name=e.column_name
LEFT JOIN sys.types ty ON c.user_type_id=ty.user_type_id ORDER BY table_name,column_name;
WITH actual AS (
SELECT t.name AS table_name,i.name AS index_name,i.is_unique,i.is_primary_key,i.is_unique_constraint,i.is_disabled,i.has_filter,
       STRING_AGG(CONVERT(nvarchar(max),c.name),N',') WITHIN GROUP (ORDER BY ic.key_ordinal) AS key_columns
FROM sys.tables t JOIN sys.schemas s ON t.schema_id=s.schema_id
JOIN sys.indexes i ON i.object_id=t.object_id
JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id AND ic.key_ordinal>0
JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id
WHERE s.name=N'dbo' GROUP BY t.name,i.name,i.is_unique,i.is_primary_key,i.is_unique_constraint,i.is_disabled,i.has_filter
), expected(table_name,index_name,key_columns,is_unique) AS (VALUES
(N'audit_events',NULL,N'id',1),
(N'audit_events',N'ix_audit_events_tenant',N'tenant',0),
(N'demo_sessions',NULL,N'id',1),
(N'demo_sessions',N'ix_demo_sessions_expires',N'expires',0),
(N'demo_sessions',N'ix_demo_sessions_tenant',N'tenant',0),
(N'evaluation_exports',NULL,N'id',1),
(N'evaluation_exports',N'ix_evaluation_exports_tenant',N'tenant',0),
(N'inference_rate_buckets',NULL,N'id',1),
(N'inference_rate_buckets',N'ix_inference_rate_buckets_expires',N'expires',0),
(N'inference_usage',NULL,N'id',1),
(N'inference_usage',N'ix_inference_usage_expires',N'expires',0),
(N'inference_usage',N'ix_inference_usage_tenant',N'tenant',0),
(N'inference_usage',N'ix_inference_usage_actor',N'actor',0),
(N'policies',NULL,N'id',1),
(N'policies',N'ix_policies_tenant',N'tenant',0),
(N'sso_memberships',NULL,N'id',1),
(N'sso_memberships',NULL,N'tenant,actor',1),
(N'sso_memberships',NULL,N'directory_tenant,object_id',1),
(N'sso_transactions',NULL,N'id',1),
(N'sso_transactions',N'ix_sso_transactions_expires',N'expires',0),
(N'validation_executions',NULL,N'id',1),
(N'validation_executions',N'ix_validation_executions_decision',N'decision',0),
(N'validation_executions',N'ix_validation_executions_tenant',N'tenant',0),
(N'validation_executions',N'ix_execution_tenant_created',N'tenant,created,id',0),
(N'export_jobs',NULL,N'id',1),
(N'export_jobs',NULL,N'tenant,idempotency_key',1),
(N'export_jobs',N'ix_export_jobs_tenant',N'tenant',0),
(N'export_jobs',N'ix_export_jobs_state',N'state',0),
(N'feedback_records',NULL,N'id',1),
(N'feedback_records',N'ix_feedback_records_tenant',N'tenant',0),
(N'human_review_cases',NULL,N'id',1),
(N'human_review_cases',N'ix_human_review_cases_tenant',N'tenant',0),
(N'policy_versions',NULL,N'id',1),
(N'policy_versions',NULL,N'policy_id,number',1),
(N'policy_versions',N'ix_policy_versions_tenant',N'tenant',0),
(N'policy_versions',N'ix_policy_versions_policy_id',N'policy_id',0),
(N'sso_sessions',NULL,N'id',1),
(N'sso_sessions',N'ix_sso_sessions_expires',N'expires',0),
(N'active_policy_assignments',NULL,N'tenant',1),
(N'review_assignments',NULL,N'id',1),
(N'review_assignments',N'ix_review_assignments_tenant',N'tenant',0),
(N'review_notes',NULL,N'id',1),
(N'review_notes',N'ix_review_notes_tenant',N'tenant',0),
(N'review_notes',N'ix_review_notes_review_id',N'review_id',0))
SELECT e.*,a.index_name AS actual_name,a.is_primary_key,a.is_unique_constraint,a.is_disabled,a.has_filter,
CASE WHEN a.index_name IS NULL THEN 'MISSING_OR_NOT_VISIBLE' ELSE 'PRESENT_REVIEW_FLAGS' END AS index_status
FROM expected e OUTER APPLY(SELECT TOP(1) * FROM actual a WHERE a.table_name=e.table_name AND a.key_columns=e.key_columns
AND a.is_unique=e.is_unique AND (e.index_name IS NULL OR a.index_name=e.index_name)) a
ORDER BY e.table_name,e.key_columns;
SELECT t.name AS table_name,fk.name,fk.is_disabled,fk.is_not_trusted,
       c.name AS column_name,rt.name AS referenced_table,rc.name AS referenced_column,
       fk.delete_referential_action_desc,fk.update_referential_action_desc
FROM sys.foreign_keys fk JOIN sys.tables t ON fk.parent_object_id=t.object_id
JOIN sys.foreign_key_columns fc ON fk.object_id=fc.constraint_object_id
JOIN sys.columns c ON c.object_id=t.object_id AND c.column_id=fc.parent_column_id
JOIN sys.tables rt ON rt.object_id=fk.referenced_object_id
JOIN sys.columns rc ON rc.object_id=rt.object_id AND rc.column_id=fc.referenced_column_id
WHERE SCHEMA_NAME(t.schema_id)=N'dbo' ORDER BY t.name,fk.name,fc.constraint_column_id;
WITH expected(table_name,trigger_name) AS (VALUES
(N'audit_events',N'immutable_audit_events'),(N'policy_versions',N'immutable_policy_versions'),(N'review_notes',N'immutable_review_notes'))
SELECT e.*,tr.is_disabled,tr.is_instead_of_trigger,sm.definition AS reviewed_history_trigger_definition
FROM expected e LEFT JOIN sys.triggers tr ON tr.parent_id=OBJECT_ID(N'dbo.'+e.table_name) AND tr.name=e.trigger_name
LEFT JOIN sys.sql_modules sm ON sm.object_id=tr.object_id;
WITH expected(table_name,permission_name) AS (VALUES
(N'policies',N'SELECT'),
(N'policies',N'INSERT'),
(N'policies',N'UPDATE'),
(N'policies',N'DELETE'),
(N'policy_versions',N'SELECT'),
(N'policy_versions',N'INSERT'),
(N'active_policy_assignments',N'SELECT'),
(N'active_policy_assignments',N'INSERT'),
(N'active_policy_assignments',N'UPDATE'),
(N'audit_events',N'SELECT'),
(N'audit_events',N'INSERT'),
(N'validation_executions',N'SELECT'),
(N'validation_executions',N'INSERT'),
(N'human_review_cases',N'SELECT'),
(N'human_review_cases',N'INSERT'),
(N'human_review_cases',N'UPDATE'),
(N'feedback_records',N'SELECT'),
(N'feedback_records',N'INSERT'),
(N'evaluation_exports',N'SELECT'),
(N'evaluation_exports',N'INSERT'),
(N'evaluation_exports',N'UPDATE'),
(N'alembic_version',N'SELECT'),
(N'demo_sessions',N'SELECT'),
(N'demo_sessions',N'INSERT'),
(N'demo_sessions',N'UPDATE'),
(N'inference_rate_buckets',N'SELECT'),
(N'inference_rate_buckets',N'INSERT'),
(N'inference_rate_buckets',N'UPDATE'),
(N'inference_usage',N'SELECT'),
(N'inference_usage',N'INSERT'),
(N'inference_usage',N'UPDATE'),
(N'export_jobs',N'SELECT'),
(N'export_jobs',N'INSERT'),
(N'export_jobs',N'UPDATE'),
(N'review_assignments',N'SELECT'),
(N'review_assignments',N'INSERT'),
(N'review_assignments',N'UPDATE'),
(N'review_notes',N'SELECT'),
(N'review_notes',N'INSERT'),
(N'sso_memberships',N'SELECT'),
(N'sso_transactions',N'SELECT'),
(N'sso_transactions',N'INSERT'),
(N'sso_transactions',N'UPDATE'),
(N'sso_sessions',N'SELECT'),
(N'sso_sessions',N'INSERT'),
(N'sso_sessions',N'UPDATE'))
SELECT e.*,HAS_PERMS_BY_NAME(N'dbo.'+table_name,'OBJECT',permission_name) AS effective_permission,
       CASE WHEN table_name LIKE N'sso[_]%' THEN @sso_enabled ELSE 1 END AS required_for_active_mode
FROM expected e ORDER BY table_name,permission_name;
-- Run permission checks as the ACTUAL application runtime identity too.
-- Administrator permission results do not establish runtime identity permissions.
-- At 005 with SSO disabled: runtime still needs metadata visibility for all 17 tables.
-- At 004: all three SSO tables must be absent; partial creation is a STOP condition.
