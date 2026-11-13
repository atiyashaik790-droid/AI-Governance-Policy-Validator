"""Revision 006 mappings, isolated from the frozen 005 runtime mappings.

Importing this module never changes Base.metadata or connects to a database.
Legacy ORM INSERTs on 006 receive execution_mode from its server default.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Column, DateTime, ForeignKeyConstraint,
    Index, Integer, MetaData, String, Table, UniqueConstraint, UnicodeText, event, CHAR,
)
from sqlalchemy.dialects import mssql
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement
from sqlalchemy.orm import DeclarativeBase

from .models import Base, new_id, prevent_history_mutation

MULTI_TABLES = frozenset({
    "workspace_policy_states", "workspace_policy_assignments",
    "workspace_policy_assignment_events", "execution_policy_evidence",
})
MULTI_HISTORY = ("workspace_policy_assignment_events", "execution_policy_evidence")
EXECUTION_SHAPE = """execution_mode IN ('LEGACY','MULTI') AND (
 (execution_mode = 'LEGACY' AND policy_id IS NOT NULL AND version IS NOT NULL AND version >= 1)
 OR (execution_mode = 'MULTI' AND policy_id IS NULL AND version IS NULL))"""
EVENT_SHAPE = """(
 event_type IN ('INITIALIZE','SET_MODE') AND policy_id IS NULL
 AND old_version_id IS NULL AND new_version_id IS NULL
 AND old_active IS NULL AND new_active IS NULL
 AND new_mode IS NOT NULL AND new_mode IN ('LEGACY','MULTI')
 AND ((event_type = 'INITIALIZE' AND old_mode IS NULL)
 OR (event_type = 'SET_MODE' AND old_mode IS NOT NULL
 AND old_mode IN ('LEGACY','MULTI') AND old_mode <> new_mode))
) OR (
 event_type IN ('ACTIVATE','DEACTIVATE','REPIN') AND policy_id IS NOT NULL
 AND new_version_id IS NOT NULL AND new_active IS NOT NULL
 AND old_mode IS NULL AND new_mode IS NULL
 AND ((event_type = 'ACTIVATE' AND new_active = 1
       AND ((old_version_id IS NULL AND old_active IS NULL)
            OR (old_version_id IS NOT NULL AND old_active IS NOT NULL AND old_active = 0)))
 OR (event_type = 'DEACTIVATE' AND old_version_id IS NOT NULL
     AND old_active IS NOT NULL AND old_active = 1 AND new_active = 0
     AND old_version_id = new_version_id)
 OR (event_type = 'REPIN' AND old_version_id IS NOT NULL
     AND old_active IS NOT NULL AND old_active = 1 AND new_active = 1
     AND old_version_id <> new_version_id))
)"""


def utc_naive():
    """DATETIME2 stores UTC without an offset; serializers add UTC explicitly."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class MultiPolicyBase(DeclarativeBase):
    metadata = MetaData()


for _table in Base.metadata.tables.values():
    _table.to_metadata(MultiPolicyBase.metadata)

metadata = MultiPolicyBase.metadata
for _name, _columns, _index in (
    ("policies", ("tenant", "id"), "ux_policies_tenant_id"),
    ("policy_versions", ("tenant", "policy_id", "id"), "ux_policy_versions_tenant_policy_id"),
    ("validation_executions", ("tenant", "id"), "ux_validation_executions_tenant_id"),
):
    if not any(index.name == _index for index in metadata.tables[_name].indexes):
        Index(_index, *[metadata.tables[_name].c[c] for c in _columns], unique=True)

_execution = metadata.tables["validation_executions"]
_execution.c.policy_id.nullable = True
_execution.c.version.nullable = True
_execution.append_column(Column("execution_mode", String(6), nullable=False, server_default="LEGACY", default="LEGACY"))
_execution.append_constraint(CheckConstraint(EXECUTION_SHAPE, name="ck_execution_mode_identity"))

_timestamp = DateTime().with_variant(mssql.DATETIME2(precision=7), "mssql")
_json = UnicodeText().with_variant(mssql.NVARCHAR(None), "mssql")


class UtcNow(FunctionElement):
    inherit_cache = True


@compiles(UtcNow)
def compile_utc_default(element, compiler, **kwargs):
    return "CURRENT_TIMESTAMP"


@compiles(UtcNow, "mssql")
def compile_utc_mssql(element, compiler, **kwargs):
    return "SYSUTCDATETIME()"


def timestamp(name):
    return Column(name, _timestamp, nullable=False, default=utc_naive, server_default=UtcNow())


class Execution006(MultiPolicyBase):
    __table__ = _execution


class WorkspacePolicyState(MultiPolicyBase):
    __table__ = Table(
        "workspace_policy_states", metadata,
        Column("tenant", String(80), primary_key=True),
        Column("mode", String(6), nullable=False, default="LEGACY", server_default="LEGACY"),
        Column("set_revision", BigInteger, nullable=False, default=1, server_default="1"),
        timestamp("updated_at"),
        Column("updated_by", String(80), nullable=False),
        CheckConstraint("mode IN ('LEGACY','MULTI')", name="ck_wps_mode"),
        CheckConstraint("set_revision >= 1", name="ck_wps_revision"),
    )


class WorkspacePolicyAssignment(MultiPolicyBase):
    __table__ = Table(
        "workspace_policy_assignments", metadata,
        Column("tenant", String(80), primary_key=True),
        Column("policy_id", String(36), primary_key=True),
        Column("version_id", String(36), nullable=False),
        Column("active", Boolean, nullable=False),
        Column("changed_revision", BigInteger, nullable=False),
        timestamp("updated_at"),
        Column("updated_by", String(80), nullable=False),
        ForeignKeyConstraint(["tenant"], ["workspace_policy_states.tenant"], name="fk_wpa_workspace"),
        ForeignKeyConstraint(["tenant", "policy_id"], ["policies.tenant", "policies.id"], name="fk_wpa_policy"),
        ForeignKeyConstraint(["tenant", "policy_id", "version_id"],
                             ["policy_versions.tenant", "policy_versions.policy_id", "policy_versions.id"], name="fk_wpa_version"),
        CheckConstraint("changed_revision >= 1", name="ck_wpa_revision"),
        CheckConstraint("active IN (0,1)", name="ck_wpa_active"),
        Index("ix_wpa_tenant_active_policy", "tenant", "active", "policy_id", mssql_include=["version_id", "changed_revision"]),
    )


class WorkspacePolicyAssignmentEvent(MultiPolicyBase):
    __table__ = Table(
        "workspace_policy_assignment_events", metadata,
        Column("id", String(36), primary_key=True, default=new_id),
        Column("tenant", String(80), nullable=False),
        Column("set_revision", BigInteger, nullable=False),
        Column("event_ordinal", Integer, nullable=False),
        Column("event_type", String(16), nullable=False),
        Column("policy_id", String(36)),
        Column("old_version_id", String(36)), Column("new_version_id", String(36)),
        Column("old_active", Boolean), Column("new_active", Boolean),
        Column("old_mode", String(6)), Column("new_mode", String(6)),
        Column("actor", String(80), nullable=False), timestamp("created_at"),
        UniqueConstraint("tenant", "set_revision", "event_ordinal", name="uq_wpae_revision_ordinal"),
        ForeignKeyConstraint(["tenant"], ["workspace_policy_states.tenant"], name="fk_wpae_workspace"),
        ForeignKeyConstraint(["tenant", "policy_id"], ["policies.tenant", "policies.id"], name="fk_wpae_policy"),
        ForeignKeyConstraint(["tenant", "policy_id", "old_version_id"],
                             ["policy_versions.tenant", "policy_versions.policy_id", "policy_versions.id"], name="fk_wpae_old_version"),
        ForeignKeyConstraint(["tenant", "policy_id", "new_version_id"],
                             ["policy_versions.tenant", "policy_versions.policy_id", "policy_versions.id"], name="fk_wpae_new_version"),
        CheckConstraint("set_revision >= 1 AND event_ordinal >= 1", name="ck_wpae_revision"),
        CheckConstraint(EVENT_SHAPE, name="ck_wpae_shape"),
        CheckConstraint("old_active IS NULL OR old_active IN (0,1)", name="ck_wpae_old_active"),
        CheckConstraint("new_active IS NULL OR new_active IN (0,1)", name="ck_wpae_new_active"),
        Index("ix_wpae_tenant_created_id", "tenant", "created_at", "id"),
    )


class ExecutionPolicyEvidence(MultiPolicyBase):
    __table__ = Table(
        "execution_policy_evidence", metadata,
        Column("tenant", String(80), primary_key=True),
        Column("execution_id", String(36), primary_key=True),
        Column("policy_id", String(36), primary_key=True),
        Column("version_id", String(36), nullable=False),
        Column("set_revision", BigInteger, nullable=False),
        Column("document_sha256", CHAR(64), nullable=False),
        Column("effective_decision", String(12), nullable=False),
        Column("inspection_status", String(16), nullable=False),
        Column("evidence_json", _json, nullable=False), timestamp("created_at"),
        ForeignKeyConstraint(["tenant", "execution_id"], ["validation_executions.tenant", "validation_executions.id"], name="fk_epe_execution"),
        ForeignKeyConstraint(["tenant", "policy_id"], ["policies.tenant", "policies.id"], name="fk_epe_policy"),
        ForeignKeyConstraint(["tenant", "policy_id", "version_id"],
                             ["policy_versions.tenant", "policy_versions.policy_id", "policy_versions.id"], name="fk_epe_version"),
        CheckConstraint("set_revision >= 1", name="ck_epe_revision"),
        CheckConstraint("effective_decision IN ('ALLOW','REDACT','HUMAN_REVIEW','BLOCK')", name="ck_epe_decision"),
        CheckConstraint("inspection_status IN ('COMPLETE','INCOMPLETE','NOT_RUN')", name="ck_epe_status"),
        CheckConstraint("json_valid(evidence_json) = 1", name="ck_epe_json").ddl_if(dialect="sqlite"),
        CheckConstraint("ISJSON(evidence_json) = 1", name="ck_epe_json").ddl_if(dialect="mssql"),
        Index("ix_epe_tenant_policy_created", "tenant", "policy_id", "created_at", "execution_id"),
    )


for _model in (WorkspacePolicyAssignmentEvent, ExecutionPolicyEvidence, Execution006):
    event.listen(_model, "before_update", prevent_history_mutation)
    event.listen(_model, "before_delete", prevent_history_mutation)
