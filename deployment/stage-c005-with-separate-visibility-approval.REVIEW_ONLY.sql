-- REVIEW ONLY: NOT EXECUTED. Requires explicit Stage C AND separate D-visibility approval.
-- Execute as ONE batch inside a caller-owned transaction; never with autocommit.
-- This is the exact compiled 005 DDL plus guards and THREE metadata-only grants.
-- No SELECT/INSERT/UPDATE grants on new SSO tables; no membership/configuration changes.
SET XACT_ABORT ON;
SET LOCK_TIMEOUT 15000;
IF @@TRANCOUNT<>1 THROW 51000, 'Exactly one caller-owned transaction required', 1;
IF DB_NAME()<>N'sqldb-governance-validator-dev' THROW 51000, 'Wrong database', 1;
IF (SELECT COUNT(*) FROM dbo.alembic_version)<>1
 OR NOT EXISTS(SELECT 1 FROM dbo.alembic_version WHERE version_num='004')
 THROW 51000, 'Exactly clean 004 required', 1;
IF EXISTS(SELECT 1 FROM sys.tables WHERE schema_id=SCHEMA_ID('dbo')
 AND name IN ('sso_memberships','sso_transactions','sso_sessions'))
 THROW 51000, 'Partial or existing 005; stop', 1;
IF SCHEMA_NAME()<>N'dbo' THROW 51000, 'dbo default schema required', 1;
IF NOT EXISTS(SELECT 1 FROM sys.database_principals WHERE name=N'governance_validator_web_runtime' AND type='R' AND is_fixed_role=0)
 THROW 51000, 'Expected runtime role absent', 1;
IF NOT EXISTS(SELECT 1 FROM sys.database_principals WHERE name=N'app-governance-validator-atiya-1026' AND type='E'
 AND DATALENGTH(sid)=16 AND TRY_CONVERT(uniqueidentifier,sid)=CONVERT(uniqueidentifier,'f7bacace-698a-4968-8add-cba221319a17'))
 THROW 51000, 'Runtime identity SID mismatch', 1;
IF NOT EXISTS(SELECT 1 FROM sys.database_role_members m
 JOIN sys.database_principals r ON r.principal_id=m.role_principal_id
 JOIN sys.database_principals u ON u.principal_id=m.member_principal_id
 WHERE r.name=N'governance_validator_web_runtime' AND u.name=N'app-governance-validator-atiya-1026')
 THROW 51000, 'Existing runtime role membership mismatch', 1;
-- Running upgrade 004 -> 005

CREATE TABLE sso_memberships (
    id VARCHAR(36) NOT NULL, 
    directory_tenant VARCHAR(36) NOT NULL, 
    object_id VARCHAR(36) NOT NULL, 
    tenant VARCHAR(80) NOT NULL, 
    actor VARCHAR(80) NOT NULL, 
    role VARCHAR(30) NOT NULL, 
    enabled INTEGER NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (directory_tenant, object_id), 
    UNIQUE (tenant, actor)
);


CREATE TABLE sso_transactions (
    id VARCHAR(64) NOT NULL, 
    binding_hash VARCHAR(64) NOT NULL, 
    nonce VARCHAR(100) NOT NULL, 
    verifier VARCHAR(128) NOT NULL, 
    return_path VARCHAR(500) NOT NULL, 
    expires VARCHAR(40) NOT NULL, 
    consumed INTEGER NOT NULL, 
    PRIMARY KEY (id)
);


CREATE INDEX ix_sso_transactions_expires ON sso_transactions (expires);


CREATE TABLE sso_sessions (
    id VARCHAR(64) NOT NULL, 
    membership_id VARCHAR(36) NOT NULL, 
    expires VARCHAR(40) NOT NULL, 
    revoked INTEGER NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(membership_id) REFERENCES sso_memberships (id)
);


CREATE INDEX ix_sso_sessions_expires ON sso_sessions (expires);


-- SEPARATE STAGE D-VISIBILITY APPROVAL REQUIRED for these three statements.
GRANT VIEW DEFINITION ON OBJECT::dbo.sso_memberships TO [governance_validator_web_runtime];
GRANT VIEW DEFINITION ON OBJECT::dbo.sso_transactions TO [governance_validator_web_runtime];
GRANT VIEW DEFINITION ON OBJECT::dbo.sso_sessions TO [governance_validator_web_runtime];

UPDATE dbo.alembic_version SET version_num='005' WHERE version_num='004';
IF @@ROWCOUNT<>1 THROW 51000, 'Expected one revision transition', 1;
