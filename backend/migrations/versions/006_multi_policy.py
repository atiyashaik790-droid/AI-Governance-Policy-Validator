"""Frozen additive multi-policy schema. Never run automatically at startup.

Only explicitly approved operator execution may target Azure SQL. SQLite execution
is supported for disposable offline fixtures, including retained review links.
"""

import json
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"

# Frozen SQL, not imported from mutable runtime models.
DDL = json.loads(r'''
{
  "mssql": {
    "parent_indexes": [
      "CREATE UNIQUE INDEX ux_policies_tenant_id ON policies (tenant, id)",
      "CREATE UNIQUE INDEX ux_policy_versions_tenant_policy_id ON policy_versions (tenant, policy_id, id)",
      "CREATE UNIQUE INDEX ux_validation_executions_tenant_id ON validation_executions (tenant, id)"
    ],
    "tables": [
      "CREATE TABLE workspace_policy_states (\n\ttenant VARCHAR(80) NOT NULL, \n\tmode VARCHAR(6) NOT NULL DEFAULT 'LEGACY', \n\tset_revision BIGINT NOT NULL DEFAULT '1', \n\tupdated_at DATETIME2(7) NOT NULL DEFAULT SYSUTCDATETIME(), \n\tupdated_by VARCHAR(80) NOT NULL, \n\tPRIMARY KEY (tenant), \n\tCONSTRAINT ck_wps_mode CHECK (mode IN ('LEGACY','MULTI')), \n\tCONSTRAINT ck_wps_revision CHECK (set_revision >= 1)\n)",
      "CREATE TABLE execution_policy_evidence (\n\ttenant VARCHAR(80) NOT NULL, \n\texecution_id VARCHAR(36) NOT NULL, \n\tpolicy_id VARCHAR(36) NOT NULL, \n\tversion_id VARCHAR(36) NOT NULL, \n\tset_revision BIGINT NOT NULL, \n\tdocument_sha256 CHAR(64) NOT NULL, \n\teffective_decision VARCHAR(12) NOT NULL, \n\tinspection_status VARCHAR(16) NOT NULL, \n\tevidence_json NVARCHAR(max) NOT NULL, \n\tcreated_at DATETIME2(7) NOT NULL DEFAULT SYSUTCDATETIME(), \n\tPRIMARY KEY (tenant, execution_id, policy_id), \n\tCONSTRAINT fk_epe_execution FOREIGN KEY(tenant, execution_id) REFERENCES validation_executions (tenant, id), \n\tCONSTRAINT fk_epe_policy FOREIGN KEY(tenant, policy_id) REFERENCES policies (tenant, id), \n\tCONSTRAINT fk_epe_version FOREIGN KEY(tenant, policy_id, version_id) REFERENCES policy_versions (tenant, policy_id, id), \n\tCONSTRAINT ck_epe_revision CHECK (set_revision >= 1), \n\tCONSTRAINT ck_epe_decision CHECK (effective_decision IN ('ALLOW','REDACT','HUMAN_REVIEW','BLOCK')), \n\tCONSTRAINT ck_epe_status CHECK (inspection_status IN ('COMPLETE','INCOMPLETE','NOT_RUN')), \n\tCONSTRAINT ck_epe_json CHECK (ISJSON(evidence_json) = 1)\n)",
      "CREATE INDEX ix_epe_tenant_policy_created ON execution_policy_evidence (tenant, policy_id, created_at, execution_id)",
      "CREATE TABLE workspace_policy_assignment_events (\n\tid VARCHAR(36) NOT NULL, \n\ttenant VARCHAR(80) NOT NULL, \n\tset_revision BIGINT NOT NULL, \n\tevent_ordinal INTEGER NOT NULL, \n\tevent_type VARCHAR(16) NOT NULL, \n\tpolicy_id VARCHAR(36) NULL, \n\told_version_id VARCHAR(36) NULL, \n\tnew_version_id VARCHAR(36) NULL, \n\told_active BIT NULL, \n\tnew_active BIT NULL, \n\told_mode VARCHAR(6) NULL, \n\tnew_mode VARCHAR(6) NULL, \n\tactor VARCHAR(80) NOT NULL, \n\tcreated_at DATETIME2(7) NOT NULL DEFAULT SYSUTCDATETIME(), \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_wpae_revision_ordinal UNIQUE (tenant, set_revision, event_ordinal), \n\tCONSTRAINT fk_wpae_workspace FOREIGN KEY(tenant) REFERENCES workspace_policy_states (tenant), \n\tCONSTRAINT fk_wpae_policy FOREIGN KEY(tenant, policy_id) REFERENCES policies (tenant, id), \n\tCONSTRAINT fk_wpae_old_version FOREIGN KEY(tenant, policy_id, old_version_id) REFERENCES policy_versions (tenant, policy_id, id), \n\tCONSTRAINT fk_wpae_new_version FOREIGN KEY(tenant, policy_id, new_version_id) REFERENCES policy_versions (tenant, policy_id, id), \n\tCONSTRAINT ck_wpae_revision CHECK (set_revision >= 1 AND event_ordinal >= 1), \n\tCONSTRAINT ck_wpae_shape CHECK ((\n event_type IN ('INITIALIZE','SET_MODE') AND policy_id IS NULL\n AND old_version_id IS NULL AND new_version_id IS NULL\n AND old_active IS NULL AND new_active IS NULL\n AND new_mode IS NOT NULL AND new_mode IN ('LEGACY','MULTI')\n AND ((event_type = 'INITIALIZE' AND old_mode IS NULL)\n OR (event_type = 'SET_MODE' AND old_mode IS NOT NULL\n AND old_mode IN ('LEGACY','MULTI') AND old_mode <> new_mode))\n) OR (\n event_type IN ('ACTIVATE','DEACTIVATE','REPIN') AND policy_id IS NOT NULL\n AND new_version_id IS NOT NULL AND new_active IS NOT NULL\n AND old_mode IS NULL AND new_mode IS NULL\n AND ((event_type = 'ACTIVATE' AND new_active = 1\n       AND ((old_version_id IS NULL AND old_active IS NULL)\n            OR (old_version_id IS NOT NULL AND old_active IS NOT NULL AND old_active = 0)))\n OR (event_type = 'DEACTIVATE' AND old_version_id IS NOT NULL\n     AND old_active IS NOT NULL AND old_active = 1 AND new_active = 0\n     AND old_version_id = new_version_id)\n OR (event_type = 'REPIN' AND old_version_id IS NOT NULL\n     AND old_active IS NOT NULL AND old_active = 1 AND new_active = 1\n     AND old_version_id <> new_version_id))\n)), \n\tCONSTRAINT ck_wpae_old_active CHECK (old_active IS NULL OR old_active IN (0,1)), \n\tCONSTRAINT ck_wpae_new_active CHECK (new_active IS NULL OR new_active IN (0,1))\n)",
      "CREATE INDEX ix_wpae_tenant_created_id ON workspace_policy_assignment_events (tenant, created_at, id)",
      "CREATE TABLE workspace_policy_assignments (\n\ttenant VARCHAR(80) NOT NULL, \n\tpolicy_id VARCHAR(36) NOT NULL, \n\tversion_id VARCHAR(36) NOT NULL, \n\tactive BIT NOT NULL, \n\tchanged_revision BIGINT NOT NULL, \n\tupdated_at DATETIME2(7) NOT NULL DEFAULT SYSUTCDATETIME(), \n\tupdated_by VARCHAR(80) NOT NULL, \n\tPRIMARY KEY (tenant, policy_id), \n\tCONSTRAINT fk_wpa_workspace FOREIGN KEY(tenant) REFERENCES workspace_policy_states (tenant), \n\tCONSTRAINT fk_wpa_policy FOREIGN KEY(tenant, policy_id) REFERENCES policies (tenant, id), \n\tCONSTRAINT fk_wpa_version FOREIGN KEY(tenant, policy_id, version_id) REFERENCES policy_versions (tenant, policy_id, id), \n\tCONSTRAINT ck_wpa_revision CHECK (changed_revision >= 1), \n\tCONSTRAINT ck_wpa_active CHECK (active IN (0,1))\n)",
      "CREATE INDEX ix_wpa_tenant_active_policy ON workspace_policy_assignments (tenant, active, policy_id) INCLUDE (version_id, changed_revision)"
    ]
  },
  "sqlite": {
    "parent_indexes": [
      "CREATE UNIQUE INDEX ux_policies_tenant_id ON policies (tenant, id)",
      "CREATE UNIQUE INDEX ux_policy_versions_tenant_policy_id ON policy_versions (tenant, policy_id, id)",
      "CREATE UNIQUE INDEX ux_validation_executions_tenant_id ON validation_executions (tenant, id)"
    ],
    "tables": [
      "CREATE TABLE workspace_policy_states (\n\ttenant VARCHAR(80) NOT NULL, \n\tmode VARCHAR(6) DEFAULT 'LEGACY' NOT NULL, \n\tset_revision BIGINT DEFAULT '1' NOT NULL, \n\tupdated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n\tupdated_by VARCHAR(80) NOT NULL, \n\tPRIMARY KEY (tenant), \n\tCONSTRAINT ck_wps_mode CHECK (mode IN ('LEGACY','MULTI')), \n\tCONSTRAINT ck_wps_revision CHECK (set_revision >= 1)\n)",
      "CREATE TABLE execution_policy_evidence (\n\ttenant VARCHAR(80) NOT NULL, \n\texecution_id VARCHAR(36) NOT NULL, \n\tpolicy_id VARCHAR(36) NOT NULL, \n\tversion_id VARCHAR(36) NOT NULL, \n\tset_revision BIGINT NOT NULL, \n\tdocument_sha256 CHAR(64) NOT NULL, \n\teffective_decision VARCHAR(12) NOT NULL, \n\tinspection_status VARCHAR(16) NOT NULL, \n\tevidence_json TEXT NOT NULL, \n\tcreated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n\tPRIMARY KEY (tenant, execution_id, policy_id), \n\tCONSTRAINT fk_epe_execution FOREIGN KEY(tenant, execution_id) REFERENCES validation_executions (tenant, id), \n\tCONSTRAINT fk_epe_policy FOREIGN KEY(tenant, policy_id) REFERENCES policies (tenant, id), \n\tCONSTRAINT fk_epe_version FOREIGN KEY(tenant, policy_id, version_id) REFERENCES policy_versions (tenant, policy_id, id), \n\tCONSTRAINT ck_epe_revision CHECK (set_revision >= 1), \n\tCONSTRAINT ck_epe_decision CHECK (effective_decision IN ('ALLOW','REDACT','HUMAN_REVIEW','BLOCK')), \n\tCONSTRAINT ck_epe_status CHECK (inspection_status IN ('COMPLETE','INCOMPLETE','NOT_RUN')), \n\tCONSTRAINT ck_epe_json CHECK (json_valid(evidence_json) = 1)\n)",
      "CREATE INDEX ix_epe_tenant_policy_created ON execution_policy_evidence (tenant, policy_id, created_at, execution_id)",
      "CREATE TABLE workspace_policy_assignment_events (\n\tid VARCHAR(36) NOT NULL, \n\ttenant VARCHAR(80) NOT NULL, \n\tset_revision BIGINT NOT NULL, \n\tevent_ordinal INTEGER NOT NULL, \n\tevent_type VARCHAR(16) NOT NULL, \n\tpolicy_id VARCHAR(36), \n\told_version_id VARCHAR(36), \n\tnew_version_id VARCHAR(36), \n\told_active BOOLEAN, \n\tnew_active BOOLEAN, \n\told_mode VARCHAR(6), \n\tnew_mode VARCHAR(6), \n\tactor VARCHAR(80) NOT NULL, \n\tcreated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_wpae_revision_ordinal UNIQUE (tenant, set_revision, event_ordinal), \n\tCONSTRAINT fk_wpae_workspace FOREIGN KEY(tenant) REFERENCES workspace_policy_states (tenant), \n\tCONSTRAINT fk_wpae_policy FOREIGN KEY(tenant, policy_id) REFERENCES policies (tenant, id), \n\tCONSTRAINT fk_wpae_old_version FOREIGN KEY(tenant, policy_id, old_version_id) REFERENCES policy_versions (tenant, policy_id, id), \n\tCONSTRAINT fk_wpae_new_version FOREIGN KEY(tenant, policy_id, new_version_id) REFERENCES policy_versions (tenant, policy_id, id), \n\tCONSTRAINT ck_wpae_revision CHECK (set_revision >= 1 AND event_ordinal >= 1), \n\tCONSTRAINT ck_wpae_shape CHECK ((\n event_type IN ('INITIALIZE','SET_MODE') AND policy_id IS NULL\n AND old_version_id IS NULL AND new_version_id IS NULL\n AND old_active IS NULL AND new_active IS NULL\n AND new_mode IS NOT NULL AND new_mode IN ('LEGACY','MULTI')\n AND ((event_type = 'INITIALIZE' AND old_mode IS NULL)\n OR (event_type = 'SET_MODE' AND old_mode IS NOT NULL\n AND old_mode IN ('LEGACY','MULTI') AND old_mode <> new_mode))\n) OR (\n event_type IN ('ACTIVATE','DEACTIVATE','REPIN') AND policy_id IS NOT NULL\n AND new_version_id IS NOT NULL AND new_active IS NOT NULL\n AND old_mode IS NULL AND new_mode IS NULL\n AND ((event_type = 'ACTIVATE' AND new_active = 1\n       AND ((old_version_id IS NULL AND old_active IS NULL)\n            OR (old_version_id IS NOT NULL AND old_active IS NOT NULL AND old_active = 0)))\n OR (event_type = 'DEACTIVATE' AND old_version_id IS NOT NULL\n     AND old_active IS NOT NULL AND old_active = 1 AND new_active = 0\n     AND old_version_id = new_version_id)\n OR (event_type = 'REPIN' AND old_version_id IS NOT NULL\n     AND old_active IS NOT NULL AND old_active = 1 AND new_active = 1\n     AND old_version_id <> new_version_id))\n)), \n\tCONSTRAINT ck_wpae_old_active CHECK (old_active IS NULL OR old_active IN (0,1)), \n\tCONSTRAINT ck_wpae_new_active CHECK (new_active IS NULL OR new_active IN (0,1))\n)",
      "CREATE INDEX ix_wpae_tenant_created_id ON workspace_policy_assignment_events (tenant, created_at, id)",
      "CREATE TABLE workspace_policy_assignments (\n\ttenant VARCHAR(80) NOT NULL, \n\tpolicy_id VARCHAR(36) NOT NULL, \n\tversion_id VARCHAR(36) NOT NULL, \n\tactive BOOLEAN NOT NULL, \n\tchanged_revision BIGINT NOT NULL, \n\tupdated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, \n\tupdated_by VARCHAR(80) NOT NULL, \n\tPRIMARY KEY (tenant, policy_id), \n\tCONSTRAINT fk_wpa_workspace FOREIGN KEY(tenant) REFERENCES workspace_policy_states (tenant), \n\tCONSTRAINT fk_wpa_policy FOREIGN KEY(tenant, policy_id) REFERENCES policies (tenant, id), \n\tCONSTRAINT fk_wpa_version FOREIGN KEY(tenant, policy_id, version_id) REFERENCES policy_versions (tenant, policy_id, id), \n\tCONSTRAINT ck_wpa_revision CHECK (changed_revision >= 1), \n\tCONSTRAINT ck_wpa_active CHECK (active IN (0,1))\n)",
      "CREATE INDEX ix_wpa_tenant_active_policy ON workspace_policy_assignments (tenant, active, policy_id)"
    ]
  }
}
''' )

EXECUTION_SHAPE = """execution_mode IN ('LEGACY','MULTI') AND (
 (execution_mode = 'LEGACY' AND policy_id IS NOT NULL AND version IS NOT NULL AND version >= 1)
 OR (execution_mode = 'MULTI' AND policy_id IS NULL AND version IS NULL))"""
HISTORY = ("workspace_policy_assignment_events", "execution_policy_evidence")


def preflight(bind):
    if bind.scalar(sa.text("SELECT COUNT(*) FROM inference_usage WHERE status='RESERVED'")):
        raise RuntimeError("006 requires drained and reconciled inference reservations")
    if bind.scalar(sa.text("SELECT COUNT(*) FROM validation_executions WHERE policy_id IS NULL OR version IS NULL OR version < 1")):
        raise RuntimeError("006 requires valid existing LEGACY execution identities")
    if bind.scalar(sa.text("SELECT COUNT(*) FROM policy_versions v LEFT JOIN policies p ON p.id=v.policy_id AND p.tenant=v.tenant WHERE p.id IS NULL")):
        raise RuntimeError("006 requires tenant-consistent published versions")
    if bind.scalar(sa.text("SELECT COUNT(*) FROM active_policy_assignments a LEFT JOIN policy_versions v ON v.id=a.version_id AND v.tenant=a.tenant WHERE v.id IS NULL")):
        raise RuntimeError("006 requires tenant-consistent legacy assignments")


def create_objects(dialect):
    if dialect == "sqlite":
        with op.batch_alter_table("validation_executions", recreate="always") as batch:
            batch.alter_column("policy_id", existing_type=sa.String(36), nullable=True)
            batch.alter_column("version", existing_type=sa.Integer(), nullable=True)
            batch.add_column(sa.Column("execution_mode", sa.String(6), nullable=False, server_default="LEGACY"))
            batch.create_check_constraint("ck_execution_mode_identity", EXECUTION_SHAPE)
    else:
        op.execute("IF COALESCE(SCHEMA_NAME(), '') <> 'dbo' THROW 51000, '006 requires dbo default schema', 1;")
        op.alter_column("validation_executions", "policy_id", existing_type=sa.String(36), nullable=True)
        op.alter_column("validation_executions", "version", existing_type=sa.Integer(), nullable=True)
        op.add_column("validation_executions", sa.Column("execution_mode", sa.String(6), nullable=False, server_default="LEGACY"))
        op.create_check_constraint("ck_execution_mode_identity", "validation_executions", EXECUTION_SHAPE)
    for statement in DDL[dialect]["parent_indexes"] + DDL[dialect]["tables"]:
        op.execute(statement)
    for table in HISTORY:
        if dialect == "sqlite":
            for action in ("UPDATE", "DELETE"):
                op.execute(f"CREATE TRIGGER immutable_{table}_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'Historical records are append-only'); END")
        else:
            op.execute(f"CREATE TRIGGER dbo.immutable_{table} ON dbo.{table} INSTEAD OF UPDATE, DELETE AS BEGIN SET NOCOUNT ON; THROW 51000, 'Historical records are append-only', 1; END")
    # Snapshot workspace identifiers; do not seed or change active assignments.
    op.execute("""INSERT INTO workspace_policy_states (tenant,mode,set_revision,updated_by)
        SELECT tenant,'LEGACY',1,'migration:006' FROM (
        SELECT tenant FROM policies UNION SELECT tenant FROM policy_versions
        UNION SELECT tenant FROM active_policy_assignments UNION SELECT tenant FROM validation_executions
        UNION SELECT tenant FROM audit_events UNION SELECT tenant FROM human_review_cases
        UNION SELECT tenant FROM feedback_records UNION SELECT tenant FROM evaluation_exports
        UNION SELECT tenant FROM demo_sessions UNION SELECT tenant FROM inference_usage
        UNION SELECT tenant FROM export_jobs UNION SELECT tenant FROM review_assignments
        UNION SELECT tenant FROM review_notes UNION SELECT tenant FROM sso_memberships) workspaces""")
    identifier = "lower(hex(randomblob(4)))||'-'||lower(hex(randomblob(2)))||'-4'||substr(lower(hex(randomblob(2))),2)||'-8'||substr(lower(hex(randomblob(2))),2)||'-'||lower(hex(randomblob(6)))" if dialect == "sqlite" else "CONVERT(varchar(36),NEWID())"
    op.execute(f"""INSERT INTO workspace_policy_assignment_events
        (id,tenant,set_revision,event_ordinal,event_type,new_mode,actor)
        SELECT {identifier},tenant,1,1,'INITIALIZE','LEGACY','migration:006'
        FROM workspace_policy_states""")


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect not in DDL:
        raise RuntimeError("006 supports only reviewed SQLite and SQL Server dialects")
    if not op.get_context().as_sql:
        preflight(bind)
    if dialect != "sqlite":
        create_objects(dialect)
        return
    if op.get_context().as_sql:
        raise RuntimeError("SQLite batch migration requires a disposable online fixture")
    # SQLite cannot relax nullability without rebuilding the parent table. Disable
    # FK enforcement only on this migration connection, before an explicit DDL
    # transaction; verify every retained child link before commit. No runtime path
    # disables FK checks. A crash before Alembic advances the marker fails closed.
    with op.get_context().autocommit_block():
        bind.exec_driver_sql("PRAGMA foreign_keys=OFF")
        bind.exec_driver_sql("BEGIN")
        try:
            create_objects(dialect)
            if bind.exec_driver_sql("PRAGMA foreign_key_check").fetchall():
                raise RuntimeError("006 retained foreign-key verification failed")
            bind.exec_driver_sql("COMMIT")
        except BaseException:
            bind.exec_driver_sql("ROLLBACK")
            raise
        finally:
            bind.exec_driver_sql("PRAGMA foreign_keys=ON")


def downgrade():
    raise RuntimeError("Preserve multi-policy evidence; use a reviewed 006-compatible application rollback")

