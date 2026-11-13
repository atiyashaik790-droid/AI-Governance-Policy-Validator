"""SQL Server reflection/permission fixtures; no native connection or DDL."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from sqlalchemy import CHAR, CheckConstraint, Integer, String
from sqlalchemy.dialects import mssql

from app import schema_compatibility as compatibility
from app.models_multi_policy import MultiPolicyBase
from app.models_review_content import ReviewContentBase
from app.routers import policies as routes
from app.security import Identity


@pytest.mark.parametrize("revision", ["006", "007"])
@pytest.mark.parametrize("fault", [None, "type", "default", "nullable", "check", "include", "permission", "disabled_check", "tenant_fk", "temporal_scale", "temporal_missing", "missing_table", "missing_column", "missing_trigger"])
def test_006_mssql_manifest_rejects_physical_and_integrity_drift(monkeypatch, fault, revision):
    dialect = mssql.dialect()
    compiler = dialect.ddl_compiler(dialect, None)
    tables = (MultiPolicyBase if revision == "006" else ReviewContentBase).metadata.tables

    class Metadata:
        def get_table_names(self, schema):
            return [*(name for name in tables if fault != "missing_table" or name != "execution_policy_evidence"), "alembic_version"]

        def get_columns(self, name, schema):
            result = [{"name": c.name, "type": c.type, "nullable": c.nullable,
                       "default": compiler.get_column_default_string(c)} for c in tables[name].columns]
            for item in result:
                if isinstance(item["type"].dialect_impl(dialect), mssql.DATETIME2):
                    # Real installed dialect drops temporal precision, unlike
                    # the old model-derived mock that hid this defect.
                    item["type"] = mssql.DATETIME2()
                if isinstance(item["type"], String):
                    # MSSQL dialect_impl adapts generic CHAR to VARCHAR; preserve fixed width.
                    item["type"] = (item["type"] if isinstance(item["type"], CHAR) else item["type"].dialect_impl(dialect)).copy()
                    item["type"].collation = "SQL_Latin1_General_CP1_CI_AS"
                if name == "workspace_policy_states" and item["name"] == "set_revision":
                    if fault == "type":
                        item["type"] = Integer()
                    if fault == "default":
                        item["default"] = "((2))"
                    if fault == "nullable":
                        item["nullable"] = True
            return [r for r in result if fault != "missing_column" or name != "workspace_policy_states" or r["name"] != "mode"]

        def get_pk_constraint(self, name, schema):
            return {"constrained_columns": list(tables[name].primary_key.columns.keys())}

        def get_indexes(self, name, schema):
            result = [{"name": i.name, "column_names": list(i.columns.keys()), "unique": bool(i.unique),
                       "include_columns": list(i.dialect_options["mssql"].get("include") or [])} for i in tables[name].indexes]
            for constraint in tables[name].constraints:
                if type(constraint).__name__ == "UniqueConstraint":
                    result.append({"name": constraint.name or "generated_unique", "column_names": list(constraint.columns.keys()), "unique": True})
            if fault == "include":
                for item in result:
                    if item["name"] == "ix_wpa_tenant_active_policy":
                        item["include_columns"] = []
            return result

        def get_foreign_keys(self, name, schema):
            result = []
            for fk in tables[name].foreign_key_constraints:
                if fault == "tenant_fk" and fk.name == "fk_epe_policy":
                    continue
                result.append({"constrained_columns": [e.parent.name for e in fk.elements],
                               "referred_schema": "dbo", "referred_table": fk.referred_table.name,
                               "referred_columns": [e.column.name for e in fk.elements], "options": {}})
            return result

        def get_check_constraints(self, name, schema):
            return dialect.get_check_constraints(None, name, schema=schema)

        def catalog_checks(self, name):
            result = []
            for constraint in tables[name].constraints:
                if isinstance(constraint, CheckConstraint) and (constraint._ddl_if is None or constraint._ddl_if.dialect == "mssql"):
                    definition = str(constraint.sqltext)
                    if fault == "check" and constraint.name == "ck_wpae_shape":
                        definition = "1 = 1"
                    result.append({"name": constraint.name, "sqltext": definition})
            return result

    class Connection:
        def __init__(self):
            self.dialect = dialect

        def execute(self, statement, params=None):
            if "SELECT name, definition FROM sys.check_constraints" in str(statement):
                rows = Metadata().catalog_checks(params["object"].split(".")[1])
                return SimpleNamespace(all=lambda: [(r["name"], r["sqltext"]) for r in rows])
            assert str(statement) == "SELECT version_num FROM dbo.alembic_version"
            return SimpleNamespace(scalars=lambda: iter([revision]))

        def scalar(self, statement, params=None):
            sql = str(statement)
            if "SELECT scale FROM sys.columns" in sql:
                return None if fault == "temporal_missing" else 3 if fault == "temporal_scale" else 7
            if "HAS_PERMS_BY_NAME" in sql:
                return 0 if fault == "permission" and "dbo.execution_policy_evidence" in params.values() else 1
            if "sys.triggers" in sql:
                return 0 if fault == "missing_trigger" else 1
            if "sys.check_constraints" in sql:
                return int(fault == "disabled_check")
            if "sys.indexes" in sql or "sys.foreign_keys" in sql:
                return 0
            raise AssertionError(sql)

    monkeypatch.setattr(compatibility, "inspect", lambda _: Metadata())
    monkeypatch.setattr(compatibility, "BatchedKeys", lambda connection, inspector: inspector)
    session = SimpleNamespace(connection=lambda: Connection())
    if fault is None:
        assert compatibility.inspect_schema(session, require_sso=True)["revision"] == revision
    else:
        with pytest.raises(HTTPException) as caught:
            compatibility.inspect_schema(session, require_sso=True)
        assert caught.value.status_code == 503


def test_multi_policy_list_uses_sqlserver_scalar_case(monkeypatch):
    database = Mock()
    database.execute.return_value = []
    monkeypatch.setattr(routes.policy_sets, "multi_mode", lambda *_: True)
    assert routes.get_all_policies(0, 50, "", None, None, database, Identity("admin", "one", "Admin")) == []
    sql = str(database.execute.call_args.args[0].compile(dialect=mssql.dialect(), compile_kwargs={"literal_binds": True}))
    assert sql.count("CASE WHEN (EXISTS (SELECT") == 2
    assert "workspace_policy_assignments.tenant = 'one'" in sql
    assert "active_policy_assignments" not in sql
