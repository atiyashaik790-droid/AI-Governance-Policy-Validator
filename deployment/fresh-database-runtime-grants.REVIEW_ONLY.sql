-- REVIEW ONLY. NO AUTHORIZATION. Never run against the source database.
SET XACT_ABORT ON;
DECLARE @explicit_approval bit = 0;
IF @explicit_approval <> 1 THROW 51000, 'Fresh database grants not approved', 1;
IF DB_NAME() <> N'sqldb-gpv-demo-v008-20261108' THROW 51000, 'Wrong database', 1;
IF (SELECT COUNT(*) FROM dbo.alembic_version) <> 1
 OR NOT EXISTS (SELECT 1 FROM dbo.alembic_version WHERE version_num=N'008')
 THROW 51000, 'Revision 008 required', 1;
DECLARE @confirmed_sid varbinary(85) = CONVERT(varbinary(16), CONVERT(uniqueidentifier, N'f7bacace-698a-4968-8add-cba221319a17')); -- Current Graph-verified MI client ID; never the object ID.
IF @confirmed_sid IS NULL OR NOT EXISTS (SELECT 1 FROM sys.database_principals
 WHERE name=N'app-governance-validator-atiya-1026' AND type='E' AND sid=@confirmed_sid)
 THROW 51000, 'New contained identity must be provisioned and verified first', 1;
IF NOT EXISTS (SELECT 1 FROM sys.database_principals
 WHERE name=N'governance_validator_web_runtime' AND type='R' AND is_fixed_role=0)
 THROW 51000, 'Reviewed custom runtime role must be provisioned first', 1;
BEGIN TRY
 BEGIN TRANSACTION;
 GRANT SELECT, INSERT, UPDATE, DELETE ON OBJECT::dbo.[policies] TO [governance_validator_web_runtime];
 GRANT VIEW DEFINITION ON OBJECT::dbo.[policies] TO [governance_validator_web_runtime];
 GRANT SELECT, INSERT ON OBJECT::dbo.[policy_versions] TO [governance_validator_web_runtime];
 GRANT VIEW DEFINITION ON OBJECT::dbo.[policy_versions] TO [governance_validator_web_runtime];
 GRANT SELECT, INSERT, UPDATE ON OBJECT::dbo.[active_policy_assignments] TO [governance_validator_web_runtime];
 GRANT VIEW DEFINITION ON OBJECT::dbo.[active_policy_assignments] TO [governance_validator_web_runtime];
 GRANT SELECT, INSERT ON OBJECT::dbo.[audit_events] TO [governance_validator_web_runtime];
 GRANT VIEW DEFINITION ON OBJECT::dbo.[audit_events] TO [governance_validator_web_runtime];
 GRANT SELECT, INSERT ON OBJECT::dbo.[validation_executions] TO [governance_validator_web_runtime];
 GRANT VIEW DEFINITION ON OBJECT::dbo.[validation_executions] TO [governance_validator_web_runtime];
 GRANT SELECT, INSERT, UPDATE ON OBJECT::dbo.[human_review_cases] TO [governance_validator_web_runtime];
 GRANT VIEW DEFINITION ON OBJECT::dbo.[human_review_cases] TO [governance_validator_web_runtime];
 GRANT SELECT, INSERT ON OBJECT::dbo.[feedback_records] TO [governance_validator_web_runtime];
 GRANT VIEW DEFINITION ON OBJECT::dbo.[feedback_records] TO [governance_validator_web_runtime];
 GRANT SELECT, INSERT, UPDATE ON OBJECT::dbo.[evaluation_exports] TO [governance_validator_web_runtime];
 GRANT VIEW DEFINITION ON OBJECT::dbo.[evaluation_exports] TO [governance_validator_web_runtime];
 GRANT SELECT ON OBJECT::dbo.[alembic_version] TO [governance_validator_web_runtime];
 GRANT VIEW DEFINITION ON OBJECT::dbo.[alembic_version] TO [governance_validator_web_runtime];
 GRANT SELECT, INSERT, UPDATE ON OBJECT::dbo.[demo_sessions] TO [governance_validator_web_runtime];
 GRANT VIEW DEFINITION ON OBJECT::dbo.[demo_sessions] TO [governance_validator_web_runtime];
 GRANT SELECT, INSERT, UPDATE ON OBJECT::dbo.[inference_rate_buckets] TO [governance_validator_web_runtime];
 GRANT VIEW DEFINITION ON OBJECT::dbo.[inference_rate_buckets] TO [governance_validator_web_runtime];
 GRANT SELECT, INSERT, UPDATE ON OBJECT::dbo.[inference_usage] TO [governance_validator_web_runtime];
 GRANT VIEW DEFINITION ON OBJECT::dbo.[inference_usage] TO [governance_validator_web_runtime];
 GRANT SELECT, INSERT, UPDATE ON OBJECT::dbo.[export_jobs] TO [governance_validator_web_runtime];
 GRANT VIEW DEFINITION ON OBJECT::dbo.[export_jobs] TO [governance_validator_web_runtime];
 GRANT SELECT, INSERT, UPDATE ON OBJECT::dbo.[review_assignments] TO [governance_validator_web_runtime];
 GRANT VIEW DEFINITION ON OBJECT::dbo.[review_assignments] TO [governance_validator_web_runtime];
 GRANT SELECT, INSERT ON OBJECT::dbo.[review_notes] TO [governance_validator_web_runtime];
 GRANT VIEW DEFINITION ON OBJECT::dbo.[review_notes] TO [governance_validator_web_runtime];
 GRANT SELECT ON OBJECT::dbo.[sso_memberships] TO [governance_validator_web_runtime];
 GRANT VIEW DEFINITION ON OBJECT::dbo.[sso_memberships] TO [governance_validator_web_runtime];
 GRANT SELECT, INSERT, UPDATE ON OBJECT::dbo.[sso_transactions] TO [governance_validator_web_runtime];
 GRANT VIEW DEFINITION ON OBJECT::dbo.[sso_transactions] TO [governance_validator_web_runtime];
 GRANT SELECT, INSERT, UPDATE ON OBJECT::dbo.[sso_sessions] TO [governance_validator_web_runtime];
 GRANT VIEW DEFINITION ON OBJECT::dbo.[sso_sessions] TO [governance_validator_web_runtime];
 GRANT SELECT, INSERT, UPDATE ON OBJECT::dbo.[workspace_policy_states] TO [governance_validator_web_runtime];
 GRANT VIEW DEFINITION ON OBJECT::dbo.[workspace_policy_states] TO [governance_validator_web_runtime];
 GRANT SELECT, INSERT, UPDATE ON OBJECT::dbo.[workspace_policy_assignments] TO [governance_validator_web_runtime];
 GRANT VIEW DEFINITION ON OBJECT::dbo.[workspace_policy_assignments] TO [governance_validator_web_runtime];
 GRANT SELECT, INSERT ON OBJECT::dbo.[workspace_policy_assignment_events] TO [governance_validator_web_runtime];
 GRANT VIEW DEFINITION ON OBJECT::dbo.[workspace_policy_assignment_events] TO [governance_validator_web_runtime];
 GRANT SELECT, INSERT ON OBJECT::dbo.[execution_policy_evidence] TO [governance_validator_web_runtime];
 GRANT VIEW DEFINITION ON OBJECT::dbo.[execution_policy_evidence] TO [governance_validator_web_runtime];
 GRANT SELECT, INSERT, DELETE ON OBJECT::dbo.[review_protected_content] TO [governance_validator_web_runtime];
 GRANT VIEW DEFINITION ON OBJECT::dbo.[review_protected_content] TO [governance_validator_web_runtime];
 DENY UPDATE, DELETE ON OBJECT::dbo.validation_executions TO [governance_validator_web_runtime];
 COMMIT;
END TRY
BEGIN CATCH
 IF @@TRANCOUNT > 0 ROLLBACK;
 THROW;
END CATCH;
-- Then verify actual role membership and effective permissions using runtime identity.
-- Grants do not prove absence of inherited privileges; reject broad roles/ownership.
