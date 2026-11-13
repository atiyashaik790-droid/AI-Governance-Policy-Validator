-- READ ONLY. Run as an existing authorized metadata-reading operator.
-- No identity switch, grants, new users, membership changes or business-row reads.
IF DB_NAME()<>N'sqldb-governance-validator-dev' THROW 51000,'Wrong database',1;
SELECT DB_NAME() AS database_name,USER_NAME() AS executing_principal;
SELECT name,type_desc,default_schema_name,DATALENGTH(sid) AS sid_bytes,
       CASE WHEN DATALENGTH(sid)=16 THEN TRY_CONVERT(uniqueidentifier,sid) END AS contained_identity_id
FROM sys.database_principals WHERE name IN
(N'app-governance-validator-atiya-1026',N'governance_validator_web_runtime');
SELECT r.name AS role_name,m.name AS member_name
FROM sys.database_role_members rm
JOIN sys.database_principals r ON rm.role_principal_id=r.principal_id
JOIN sys.database_principals m ON rm.member_principal_id=m.principal_id
WHERE m.name=N'app-governance-validator-atiya-1026';
SELECT p.name AS grantee,pe.state_desc,pe.permission_name,pe.class_desc,
       OBJECT_SCHEMA_NAME(pe.major_id) AS object_schema,OBJECT_NAME(pe.major_id) AS object_name
FROM sys.database_permissions pe JOIN sys.database_principals p ON pe.grantee_principal_id=p.principal_id
WHERE p.name IN (N'app-governance-validator-atiya-1026',N'governance_validator_web_runtime',N'public')
ORDER BY p.name,pe.class_desc,object_name,pe.permission_name;
-- Effective HAS_PERMS_BY_NAME calls in verify_sso_compatibility.READ_ONLY.sql must
-- run in the actual managed-identity SQL session to count as runtime verification.
-- This catalog inventory alone does not prove effective permissions or live mapping.
