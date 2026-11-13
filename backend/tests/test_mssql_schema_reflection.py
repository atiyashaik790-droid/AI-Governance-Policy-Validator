"""Regression for SQL Server's unsupported unique-constraint Inspector method.

No network, database creation/writes, migrations or credentials are used.
"""

from types import SimpleNamespace
from collections import defaultdict
import inspect

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects.mssql.base import MSDialect
from sqlalchemy.dialects.mssql import information_schema as catalog

from app import schema_compatibility as compatibility
from app.models import Base


def test_actual_mssql_dialect_does_not_implement_unique_constraint_reflection():
    # Real installed SQL Server dialect, not the SQLite reflection used by old mocks.
    with pytest.raises(NotImplementedError):
        MSDialect().get_unique_constraints(None, "policy_versions", schema="dbo")


def test_actual_mssql_dialect_has_no_check_constraint_reflection():
    with pytest.raises(NotImplementedError):
        MSDialect().get_check_constraints(None, "workspace_policy_states", schema="dbo")


def test_actual_mssql_column_reflection_drops_datetime2_catalog_scale():
    # Execute the installed dialect's real result conversion on a catalog row.
    row = defaultdict(lambda: None, {
        catalog.sys_columns.c.name: "updated_at",
        catalog.sys_types.c.name: "datetime2",
        catalog.sys_columns.c.scale: 7,
        catalog.sys_columns.c.precision: 27,
        catalog.sys_columns.c.is_nullable: 0,
    })

    class Connection:
        def execution_options(self, **kwargs):
            return self

        def execute(self, *args, **kwargs):
            return SimpleNamespace(mappings=lambda: [row])

    dialect = MSDialect()
    dialect.server_version_info = (16, 0)
    reflected = inspect.unwrap(MSDialect.get_columns)(dialect, Connection(), "workspace_policy_states", None, "dbo", "dbo")[0]
    assert reflected["type"].precision is None
    assert str(reflected["type"].compile(dialect=dialect)) == "DATETIME2"
    # The old exact-string comparison necessarily rejects the frozen DDL's (7).
    assert str(reflected["type"].compile(dialect=dialect)) != "DATETIME2(7)"


@pytest.mark.parametrize("revision", ["004", "005"])
@pytest.mark.parametrize("unique_state", ["present", "missing", "non_unique", "wrong_columns"])
def test_sql_server_contract_uses_backing_unique_indexes(monkeypatch, revision, unique_state):
    tables = {name: model for name, model in Base.metadata.tables.items() if revision == "005" or name not in compatibility.SSO_TABLES}
    unsupported_calls = []

    class Metadata:
        def get_table_names(self, schema):
            assert schema == "dbo"
            return [*tables, "alembic_version"]

        def get_columns(self, name, schema):
            return [{"name": c.name, "type": c.type, "nullable": c.nullable} for c in tables[name].columns]

        def get_pk_constraint(self, name, schema):
            return {"constrained_columns": list(tables[name].primary_key.columns.keys())}

        def get_indexes(self, name, schema):
            indexes = [{"name": i.name, "column_names": list(i.columns.keys()), "unique": bool(i.unique)} for i in tables[name].indexes]
            for constraint in tables[name].constraints:
                if type(constraint).__name__ != "UniqueConstraint":
                    continue
                if name == "policy_versions" and unique_state == "missing":
                    continue
                columns = list(constraint.columns.keys())
                if name == "policy_versions" and unique_state == "wrong_columns":
                    columns = ["id"]
                indexes.append(
                    {
                        "name": "SQL_generated_unique_constraint_index",
                        "column_names": columns,
                        "unique": not (name == "policy_versions" and unique_state == "non_unique"),
                    }
                )
            return indexes

        def get_unique_constraints(self, name, schema):
            unsupported_calls.append(name)
            # This reproduces the exact operation that failed on Azure SQL.
            return MSDialect().get_unique_constraints(None, name, schema=schema)

        def get_foreign_keys(self, name, schema):
            return [
                {
                    "constrained_columns": [e.parent.name for e in fk.elements],
                    "referred_schema": "dbo",
                    "referred_table": fk.referred_table.name,
                    "referred_columns": [e.column.name for e in fk.elements],
                    "options": {},
                }
                for fk in tables[name].foreign_key_constraints
            ]

    class Connection:
        dialect = SimpleNamespace(name="mssql")

        def execute(self, statement):
            assert str(statement) == "SELECT version_num FROM dbo.alembic_version"
            return SimpleNamespace(scalars=lambda: iter([revision]))

        def scalar(self, statement, params=None):
            query = str(statement)
            assert query.startswith("SELECT ")
            if "sys.indexes" in query or "sys.foreign_keys" in query:
                return 0
            if "sys.triggers" in query or "HAS_PERMS_BY_NAME" in query:
                return 1
            raise AssertionError("Unexpected query")

    monkeypatch.setattr(compatibility, "inspect", lambda connection: Metadata())
    monkeypatch.setattr(compatibility, "BatchedKeys", lambda connection, inspector: inspector)
    db = SimpleNamespace(connection=lambda: Connection())
    if unique_state == "present":
        assert compatibility.inspect_schema(db)["revision"] == revision
    else:
        with pytest.raises(HTTPException) as captured:
            compatibility.inspect_schema(db)
        assert captured.value.status_code == 503
        assert captured.value.__context__.safe_diagnostic == {"category": "UNIQUE_CONSTRAINT_MISSING", "object": "policy_versions"}
    assert unsupported_calls == []


@pytest.mark.parametrize("error,expected", [
    (compatibility.SchemaCheckError("006_PHYSICAL_TYPE_MISMATCH", "workspace_policy_states.updated_at"),
     {"category": "006_PHYSICAL_TYPE_MISMATCH", "object": "workspace_policy_states.updated_at"}),
    (RuntimeError("42000", "secret connection string and SQL parameters (229)"),
     {"category": "SCHEMA_QUERY_OR_IMPLEMENTATION_FAILURE", "sqlstate": "42000", "native_code": 229}),
])
def test_readiness_diagnostics_remain_internal_and_sanitized(monkeypatch, error, expected):
    def failing_inspector(connection):
        raise error

    monkeypatch.setattr(compatibility, "inspect", failing_inspector)
    with pytest.raises(HTTPException) as caught:
        compatibility.inspect_schema(SimpleNamespace(connection=lambda: None))
    assert caught.value.status_code == 503
    assert caught.value.detail == "Reviewed schema objects and runtime permissions are required"
    assert caught.value.safe_diagnostic == expected
    assert "secret" not in str(caught.value.safe_diagnostic)
