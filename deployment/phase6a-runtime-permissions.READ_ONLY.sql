-- READ ONLY proposal: run using the existing application runtime principal, not an operator.
-- No impersonation, credentials, grants or writes. Identity mismatch must stop acceptance.
SELECT DB_NAME() AS database_name, USER_NAME() AS executing_database_user;
SELECT version_num FROM dbo.alembic_version;
SELECT N'workspace_policy_states.SELECT' AS requirement, HAS_PERMS_BY_NAME(N'dbo.workspace_policy_states',N'OBJECT',N'SELECT') AS allowed;
SELECT N'workspace_policy_states.INSERT' AS requirement, HAS_PERMS_BY_NAME(N'dbo.workspace_policy_states',N'OBJECT',N'INSERT') AS allowed;
SELECT N'workspace_policy_states.UPDATE' AS requirement, HAS_PERMS_BY_NAME(N'dbo.workspace_policy_states',N'OBJECT',N'UPDATE') AS allowed;
SELECT N'workspace_policy_states.VIEW DEFINITION' AS requirement, HAS_PERMS_BY_NAME(N'dbo.workspace_policy_states',N'OBJECT',N'VIEW DEFINITION') AS allowed;
SELECT N'workspace_policy_assignments.SELECT' AS requirement, HAS_PERMS_BY_NAME(N'dbo.workspace_policy_assignments',N'OBJECT',N'SELECT') AS allowed;
SELECT N'workspace_policy_assignments.INSERT' AS requirement, HAS_PERMS_BY_NAME(N'dbo.workspace_policy_assignments',N'OBJECT',N'INSERT') AS allowed;
SELECT N'workspace_policy_assignments.UPDATE' AS requirement, HAS_PERMS_BY_NAME(N'dbo.workspace_policy_assignments',N'OBJECT',N'UPDATE') AS allowed;
SELECT N'workspace_policy_assignments.VIEW DEFINITION' AS requirement, HAS_PERMS_BY_NAME(N'dbo.workspace_policy_assignments',N'OBJECT',N'VIEW DEFINITION') AS allowed;
SELECT N'workspace_policy_assignment_events.SELECT' AS requirement, HAS_PERMS_BY_NAME(N'dbo.workspace_policy_assignment_events',N'OBJECT',N'SELECT') AS allowed;
SELECT N'workspace_policy_assignment_events.INSERT' AS requirement, HAS_PERMS_BY_NAME(N'dbo.workspace_policy_assignment_events',N'OBJECT',N'INSERT') AS allowed;
SELECT N'workspace_policy_assignment_events.VIEW DEFINITION' AS requirement, HAS_PERMS_BY_NAME(N'dbo.workspace_policy_assignment_events',N'OBJECT',N'VIEW DEFINITION') AS allowed;
SELECT N'execution_policy_evidence.SELECT' AS requirement, HAS_PERMS_BY_NAME(N'dbo.execution_policy_evidence',N'OBJECT',N'SELECT') AS allowed;
SELECT N'execution_policy_evidence.INSERT' AS requirement, HAS_PERMS_BY_NAME(N'dbo.execution_policy_evidence',N'OBJECT',N'INSERT') AS allowed;
SELECT N'execution_policy_evidence.VIEW DEFINITION' AS requirement, HAS_PERMS_BY_NAME(N'dbo.execution_policy_evidence',N'OBJECT',N'VIEW DEFINITION') AS allowed;
SELECT N'review_protected_content.SELECT' AS requirement, HAS_PERMS_BY_NAME(N'dbo.review_protected_content',N'OBJECT',N'SELECT') AS allowed;
SELECT N'review_protected_content.INSERT' AS requirement, HAS_PERMS_BY_NAME(N'dbo.review_protected_content',N'OBJECT',N'INSERT') AS allowed;
SELECT N'review_protected_content.DELETE' AS requirement, HAS_PERMS_BY_NAME(N'dbo.review_protected_content',N'OBJECT',N'DELETE') AS allowed;
SELECT N'review_protected_content.VIEW DEFINITION' AS requirement, HAS_PERMS_BY_NAME(N'dbo.review_protected_content',N'OBJECT',N'VIEW DEFINITION') AS allowed;
