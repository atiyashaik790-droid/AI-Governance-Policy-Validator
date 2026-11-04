"""Static migration and MSSQL compilation checks: no engines, DDL execution or migrations."""

import ast
from pathlib import Path

import sqlalchemy as sa
from alembic.ddl.base import AddColumn
from alembic.runtime.migration import MigrationContext
from sqlalchemy.dialects import mssql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.models import Base

VERSIONS = Path(__file__).resolve().parents[1] / "migrations" / "versions"


def migration(revision):
    return ast.parse(next(VERSIONS.glob(f"{revision}_*.py")).read_text())


def operation_calls(tree, name):
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "op"
        and node.func.attr == name
    ]


def test_linear_revision_chain():
    for revision, parent in [("001", None), ("002", "001"), ("003", "002"), ("004", "003")]:
        values = {node.targets[0].id: ast.literal_eval(node.value) for node in migration(revision).body if isinstance(node, ast.Assign)}
        assert values["revision"] == revision
        assert values["down_revision"] == parent


def test_foundation_dependencies_and_expected_objects():
    created = set()
    calls = operation_calls(migration("001"), "create_table")
    for call in calls:
        name = ast.literal_eval(call.args[0])
        for argument in call.args[1:]:
            if isinstance(argument, ast.Call) and argument.func.attr == "ForeignKeyConstraint":
                for target in ast.literal_eval(argument.args[1]):
                    assert target.split(".")[0] in created
        created.add(name)
    added = {ast.literal_eval(call.args[0]) for call in operation_calls(migration("004"), "create_table")}
    assert created.isdisjoint(added)
    assert created | added == set(Base.metadata.tables)
    assert len(calls) == 8
    assert len(operation_calls(migration("001"), "create_index")) == 9
    assert sum(len(table.foreign_key_constraints) for table in Base.metadata.tables.values()) == 7


def test_concurrency_columns_match_fresh_baseline():
    tables = {ast.literal_eval(call.args[0]): call for call in operation_calls(migration("001"), "create_table")}

    def columns(table):
        return {ast.literal_eval(arg.args[0]) for arg in tables[table].args[1:] if isinstance(arg, ast.Call) and arg.func.attr == "Column"}

    assert "row_version" in columns("policies")
    assert "row_version" not in columns("human_review_cases")
    guarded = [node for node in ast.walk(migration("002")) if isinstance(node, ast.If)]
    assert len(guarded) == 1 and isinstance(guarded[0].test.ops[0], ast.NotIn)
    assert len(operation_calls(guarded[0], "add_column")) == 1
    addition = operation_calls(migration("003"), "add_column")
    assert len(addition) == 1 and ast.literal_eval(addition[0].args[0]) == "human_review_cases"


def test_mssql_ddl_compiles_without_executing():
    dialect = mssql.dialect(deprecate_large_types=True)
    for table in Base.metadata.sorted_tables:
        compiled = str(CreateTable(table).compile(dialect=dialect))
        assert "CREATE TABLE" in compiled
        for index in table.indexes:
            assert "CREATE INDEX" in str(CreateIndex(index).compile(dialect=dialect))
    column = sa.Column("row_version", sa.Integer(), nullable=False, server_default="1")
    sa.Table("human_review_cases", sa.MetaData(), column)
    addition = AddColumn("human_review_cases", column)
    sql = str(addition.compile(dialect=dialect))
    assert "ALTER TABLE human_review_cases ADD row_version INTEGER NOT NULL DEFAULT '1'" in sql
    assert MigrationContext.configure(dialect=dialect).impl.transactional_ddl is True


def test_no_destructive_upgrade_operations():
    for revision in ("001", "002", "003"):
        tree = migration(revision)
        upgrade = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "upgrade")
        for node in ast.walk(upgrade):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                if node.func.value.id == "op":
                    assert node.func.attr in {"create_table", "create_index", "f", "get_bind", "add_column"}
        downgrade = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "downgrade")
        assert any(isinstance(node, ast.Raise) for node in ast.walk(downgrade))
