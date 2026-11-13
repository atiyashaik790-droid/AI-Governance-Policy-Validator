BEGIN TRANSACTION;

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

GO

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

GO

CREATE INDEX ix_sso_transactions_expires ON sso_transactions (expires);

GO

CREATE TABLE sso_sessions (
    id VARCHAR(64) NOT NULL, 
    membership_id VARCHAR(36) NOT NULL, 
    expires VARCHAR(40) NOT NULL, 
    revoked INTEGER NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(membership_id) REFERENCES sso_memberships (id)
);

GO

CREATE INDEX ix_sso_sessions_expires ON sso_sessions (expires);

GO

UPDATE alembic_version SET version_num='005' WHERE alembic_version.version_num = '004';

GO

COMMIT;

GO

