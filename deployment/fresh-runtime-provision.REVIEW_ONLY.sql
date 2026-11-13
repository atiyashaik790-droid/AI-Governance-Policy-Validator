-- REVIEW ONLY; not approved or executed. Exact persistent replacement DB only.
-- Graph verified principal object ID: 600447fe-5fea-4801-9033-ab4aafc474cc
-- Graph verified MI client ID/SID: f7bacace-698a-4968-8add-cba221319a17
-- Explicit SID mapping uses the service principal CLIENT ID, not its object ID.
SET XACT_ABORT ON;
DECLARE @explicit_approval bit = 0;
IF @explicit_approval <> 1 THROW 51000, 'Runtime provisioning not approved', 1;
IF DB_NAME() <> N'sqldb-gpv-demo-v008-20261108' THROW 51000, 'Wrong database', 1;
IF (SELECT COUNT(*) FROM dbo.alembic_version) <> 1
 OR NOT EXISTS (SELECT 1 FROM dbo.alembic_version WHERE version_num=N'008')
 THROW 51000, 'Revision 008 required', 1;
IF DATABASE_PRINCIPAL_ID(N'app-governance-validator-atiya-1026') IS NOT NULL
 OR DATABASE_PRINCIPAL_ID(N'governance_validator_web_runtime') IS NOT NULL
 THROW 51000, 'Existing principal or role requires read-only reconciliation first', 1;
DECLARE @client_id uniqueidentifier = N'f7bacace-698a-4968-8add-cba221319a17';
DECLARE @sid_hex varchar(34) = CONVERT(varchar(34), CONVERT(varbinary(16), @client_id), 1);
DECLARE @create_user nvarchar(max) = N'CREATE USER [app-governance-validator-atiya-1026] WITH SID = ' + @sid_hex + N', TYPE = E;';
BEGIN TRY
 BEGIN TRANSACTION;
 EXEC sys.sp_executesql @create_user;
 CREATE ROLE [governance_validator_web_runtime] AUTHORIZATION dbo;
 GRANT CONNECT TO [app-governance-validator-atiya-1026];
 ALTER ROLE [governance_validator_web_runtime] ADD MEMBER [app-governance-validator-atiya-1026];
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
-- Verify effective database/object rights under EXECUTE AS USER with guaranteed REVERT.
-- Catalog impersonation proves effective SQL rights, not a hosted managed-identity sign-in.
-- Any unexpected inherited broad privilege or ownership is a failure; do not add grants to hide it.
-- No sequences are required; model UUIDs are generated in the application.
-- No schema-wide DML, ALTER/CONTROL or fixed database role is granted.
