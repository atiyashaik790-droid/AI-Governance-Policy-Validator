-- SELECT-only verification. Run as the actual runtime account, never dbo/EXECUTE AS.
SELECT DB_NAME() AS database_name, USER_NAME() AS database_principal,
       SCHEMA_NAME() AS default_schema;
-- Expected: exact database; approved runtime UPN (not dbo); dbo default schema.
SELECT r.role_name, IS_ROLEMEMBER(r.role_name) AS is_member
FROM (VALUES ('governance_validator_runtime'), ('db_owner'), ('db_ddladmin'),
             ('db_securityadmin'), ('db_accessadmin'), ('db_datareader'),
             ('db_datawriter'), ('db_backupoperator')) r(role_name);
-- Expected: runtime role 1; other listed roles 0. NULL is inconclusive.
SELECT p.permission_name,
       HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', p.permission_name) AS has_permission
FROM (VALUES ('CONNECT'), ('CONTROL'), ('CREATE TABLE'), ('ALTER ANY USER'),
             ('ALTER ANY ROLE'), ('ALTER ANY SCHEMA'), ('VIEW DEFINITION'),
             ('IMPERSONATE ANY USER'), ('SELECT'), ('INSERT'), ('UPDATE'), ('DELETE')) p(permission_name);
-- Expected: CONNECT 1, everything else 0; object grants are evaluated separately below.
SELECT p.permission_name,
       HAS_PERMS_BY_NAME('dbo', 'SCHEMA', p.permission_name) AS has_permission
FROM (VALUES ('CONTROL'), ('ALTER'), ('REFERENCES'), ('SELECT'), ('INSERT'),
             ('UPDATE'), ('DELETE'), ('VIEW DEFINITION')) p(permission_name);
-- Expected: all 0; no blanket schema access.
SELECT t.table_name, p.permission_name,
       CASE WHEN p.permission_name = 'VIEW DEFINITION' THEN NULL
            WHEN p.permission_name IN ('SELECT', 'INSERT') THEN 1
            WHEN p.permission_name = 'UPDATE' AND t.table_name IN
                 ('policies','active_policy_assignments','human_review_cases','evaluation_exports') THEN 1
            WHEN p.permission_name = 'DELETE' AND t.table_name = 'policies' THEN 1
            ELSE 0 END AS expected_permission,
       HAS_PERMS_BY_NAME('dbo.' + t.table_name, 'OBJECT', p.permission_name) AS actual_permission
FROM (VALUES ('policies'), ('policy_versions'), ('active_policy_assignments'), ('audit_events'),
             ('validation_executions'), ('human_review_cases'), ('feedback_records'), ('evaluation_exports')) t(table_name)
CROSS JOIN (VALUES ('SELECT'), ('INSERT'), ('UPDATE'), ('DELETE'), ('ALTER'),
                   ('CONTROL'), ('REFERENCES'), ('TAKE OWNERSHIP'), ('VIEW DEFINITION')) p(permission_name)
ORDER BY t.table_name, p.permission_name;
-- Expected: every actual permission equals expected, except VIEW DEFINITION can be
-- implied by an object permission and is informational; no explicit grant is needed.
-- NULL on these SELECT-visible application objects is inconclusive, not a pass.
SELECT p.permission_name,
       HAS_PERMS_BY_NAME('dbo.alembic_version', 'OBJECT', p.permission_name) AS has_permission
FROM (VALUES ('SELECT'), ('INSERT'), ('UPDATE'), ('DELETE'), ('ALTER'), ('CONTROL')) p(permission_name);
-- No permission may be 1. NULL can mean hidden metadata and needs the admin audit.
SELECT * FROM fn_my_permissions(NULL, 'DATABASE');
SELECT * FROM fn_my_permissions('dbo', 'SCHEMA');
-- Administrator must separately audit group-derived access, public permissions,
-- ownership, explicit grants/denials and any other role memberships before acceptance.
