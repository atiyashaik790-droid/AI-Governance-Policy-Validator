"""Full 008 verifier with batched SQL Server key rows; no native/cloud SQL."""
from types import SimpleNamespace
import copy

import pytest
from fastapi import HTTPException
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects import mssql

from app import schema_compatibility as compatibility
from app.schema_manifests import metadata_for_revision


def catalog(revision="008"):
    indexes, foreign = [], []
    for name, table in metadata_for_revision(revision).tables.items():
        keys = [("pk_" + name, list(table.primary_key.columns.keys()), [], True, True)]
        keys += [(i.name, list(i.columns.keys()), list(i.dialect_options["mssql"].get("include") or []), bool(i.unique), False) for i in table.indexes]
        keys += [(u.name or f"uq_{name}_{number}", list(u.columns.keys()), [], True, False) for number, u in enumerate(table.constraints) if isinstance(u, UniqueConstraint)]
        for index, columns, included, unique, primary in keys:
            for ordinal, column in enumerate(columns + included, 1):
                indexes.append(dict(table_name=name, index_name=index, is_primary_key=primary,
                                    is_unique=unique, column_name=column, key_ordinal=ordinal if column in columns else 0,
                                    is_included_column=column in included, index_column_id=ordinal))
        for number, fk in enumerate(table.foreign_key_constraints):
            for element in fk.elements:
                foreign.append(dict(table_name=name, constraint_name=fk.name or f"fk_{name}_{number}",
                                    column_name=element.parent.name, referred_schema="dbo",
                                    referred_table=element.column.table.name, referred_column=element.column.name,
                                    delete_action="NO_ACTION"))
    return indexes, foreign


class CatalogConnection:
    dialect = mssql.dialect()

    def __init__(self, fault=None, revision="008"):
        self.revision = revision
        self.indexes, self.foreign = catalog(revision)
        self.fault, self.batch_reads = fault, 0

    def execute(self, sql, params=None):
        query = str(sql)
        if "JOIN sys.index_columns" in query:
            self.batch_reads += 1
            rows = copy.deepcopy(self.indexes)
            for row in rows:
                if row["table_name"] == "workspace_policy_assignments":
                    if self.fault == "primary_order" and row["is_primary_key"]:
                        row["column_name"] = "wrong"
                    if self.fault == "include" and row["is_included_column"]:
                        row["column_name"] = "wrong"
                if self.fault == "unique" and row["table_name"] == "policy_versions" and not row["is_primary_key"]:
                    row["is_unique"] = False
            if self.fault == "index":
                rows = [r for r in rows if r["index_name"] != "ix_wpa_tenant_active_policy"]
            return SimpleNamespace(mappings=lambda: rows)
        if "JOIN sys.foreign_key_columns" in query:
            self.batch_reads += 1
            rows = copy.deepcopy(self.foreign)
            for row in rows:
                if row["table_name"] == "execution_policy_evidence" and row["column_name"] == "tenant":
                    if self.fault == "tenant":
                        row["referred_column"] = "id"
                    if self.fault == "cascade":
                        row["delete_action"] = "CASCADE"
            return SimpleNamespace(mappings=lambda: rows)
        if "SELECT name, definition FROM sys.check_constraints" in query:
            table = metadata_for_revision(self.revision).tables[params["object"].split(".")[1]]
            rows = [(c.name, str(c.sqltext)) for c in table.constraints if isinstance(c, CheckConstraint) and (c._ddl_if is None or c._ddl_if.dialect == "mssql")]
            return SimpleNamespace(all=lambda: rows)
        assert query == "SELECT version_num FROM dbo.alembic_version"
        return SimpleNamespace(scalars=lambda: iter([self.revision]))

    def scalar(self, sql, params=None):
        query = str(sql)
        if "HAS_PERMS_BY_NAME('dbo.validation_executions'" in query:
            return 0
        if "HAS_PERMS_BY_NAME" in query:
            return 0 if self.fault == "grant" else 1
        if "sys.triggers" in query:
            return 0 if self.fault == "trigger" else 1
        if "sys.columns" in query:
            return 7
        if "sys.check_constraints" in query or "sys.foreign_keys" in query or "sys.indexes" in query:
            return 0
        raise AssertionError(query)


class Columns:
    def __init__(self, revision="008"):
        self.revision = revision

    def get_table_names(self, schema):
        return [*metadata_for_revision(self.revision).tables, "alembic_version"]

    def get_columns(self, name, schema):
        return [{"name": c.name, "type": c.type, "nullable": c.nullable,
                 "default": c.server_default.arg.compile(dialect=mssql.dialect()) if c.server_default and hasattr(c.server_default.arg, "compile") else c.server_default.arg if c.server_default else None}
                for c in metadata_for_revision(self.revision).tables[name].columns]


@pytest.mark.parametrize("fault", [None, "primary_order", "index", "include", "unique", "tenant", "cascade", "grant", "trigger"])
def test_full_008_contract_with_two_key_reads(monkeypatch, fault):
    conn = CatalogConnection(fault)
    monkeypatch.setattr(compatibility, "inspect", lambda _: Columns())
    session = SimpleNamespace(connection=lambda: conn)
    if fault is None:
        assert compatibility.inspect_schema(session, require_sso=True)["revision"] == "008"
    else:
        with pytest.raises(HTTPException) as failure:
            compatibility.inspect_schema(session, require_sso=True)
        assert failure.value.status_code == 503
    assert conn.batch_reads == 2


def test_no_cache_across_verifications_and_no_hidden_permission_drift(monkeypatch):
    conn = CatalogConnection()
    monkeypatch.setattr(compatibility, "inspect", lambda _: Columns())
    session = SimpleNamespace(connection=lambda: conn)
    assert compatibility.inspect_schema(session)["revision"] == "008"
    conn.fault = "grant"
    with pytest.raises(HTTPException):
        compatibility.inspect_schema(session)
    assert conn.batch_reads == 4


def test_metadata_roundtrip_latency_model_crosses_unchanged_budget(monkeypatch):
    # A one-second cost per guarded read is a scenario, NOT an Azure measurement.
    # Installed MSSQL reflection needs >=1 PK + 2 index + 1 FK reads per table.
    # Include other verifier reads and one cached column read per table.
    conn, columns = CatalogConnection(), Columns()
    count, seen = [1], set()  # Table listing is one read.
    execute, scalar, get_columns = conn.execute, conn.scalar, columns.get_columns

    def counted_execute(*args, **kwargs):
        count[0] += 1
        return execute(*args, **kwargs)

    def counted_scalar(*args, **kwargs):
        count[0] += 1
        return scalar(*args, **kwargs)

    def counted_columns(name, schema):
        if name not in seen:
            count[0] += 1
            seen.add(name)
        return get_columns(name, schema)

    conn.execute, conn.scalar = counted_execute, counted_scalar
    columns.get_columns = counted_columns
    monkeypatch.setattr(compatibility, "inspect", lambda _: columns)
    assert compatibility.inspect_schema(SimpleNamespace(connection=lambda: conn))["revision"] == "008"
    batched = count[0]
    original_minimum = batched - 2 + 4 * len(metadata_for_revision("008").tables)
    assert (batched, original_minimum) == (71, 157)
    assert batched < 90 < original_minimum


@pytest.mark.parametrize("revision", ["004", "005", "006", "007"])
def test_batching_preserves_bridge_revision_contracts(monkeypatch, revision):
    conn = CatalogConnection(revision=revision)
    monkeypatch.setattr(compatibility, "inspect", lambda _: Columns(revision))
    result = compatibility.inspect_schema(SimpleNamespace(connection=lambda: conn), require_sso=revision != "004")
    assert result["revision"] == revision
    assert conn.batch_reads == 2
