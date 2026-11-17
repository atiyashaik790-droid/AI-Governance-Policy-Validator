"""Strict 006-only reflection checks; legacy readiness contracts stay unchanged."""

import re
from sqlalchemy import CheckConstraint, text
from .models_multi_policy import MULTI_TABLES


def canonical_check(expression):
    """Normalize this schema's CHECK grammar, including SQL Server IN expansion.

    Unknown syntax fails closed. This is not an evaluator for user-supplied SQL.
    """
    expression = re.sub(r"\[([^\]]+)\]", r"\1", expression)
    tokens = re.findall(r"N?'(?:''|[^'])*'|>=|<=|<>|!=|[=><(),]|\d+|[A-Za-z_][A-Za-z_0-9]*", expression)
    remainder = re.sub(r"N?'(?:''|[^'])*'|>=|<=|<>|!=|[=><(),]|\d+|[A-Za-z_][A-Za-z_0-9]*|\s+", "", expression)
    if remainder:
        raise ValueError("Unrecognized CHECK syntax")
    tokens = [t[1:] if t.startswith("N'") else t if t.startswith("'") else t.lower() for t in tokens]
    position = 0

    def peek():
        return tokens[position] if position < len(tokens) else None

    def take(expected=None):
        nonlocal position
        value = peek()
        if value is None or expected is not None and value != expected:
            raise ValueError("Malformed CHECK")
        position += 1
        return value

    def combine(operator, values):
        flattened = []
        for value in values:
            flattened.extend(value[1:] if isinstance(value, tuple) and value[0] == operator else [value])
        return flattened[0] if len(flattened) == 1 else (operator, *sorted(flattened, key=repr))

    def atom():
        if peek() == "(":
            take("(")
            value = disjunction()
            take(")")
            return value
        value = take()
        if peek() == "(":
            take("(")
            args = []
            if peek() != ")":
                args.append(atom())
                while peek() == ",":
                    take(",")
                    args.append(atom())
            take(")")
            return ("call", value, *args)
        return value

    def comparison():
        left = atom()
        operation = peek()
        if operation == "is":
            take("is")
            negate = peek() == "not"
            if negate:
                take("not")
            take("null")
            return ("is_not_null" if negate else "is_null", left)
        if operation == "in":
            take("in")
            take("(")
            values = [atom()]
            while peek() == ",":
                take(",")
                values.append(atom())
            take(")")
            return combine("or", [("=", *sorted([left, v], key=repr)) for v in values])
        if operation in {"=", "<>", "!=", ">=", "<=", ">", "<"}:
            take()
            right = atom()
            operation = "<>" if operation == "!=" else operation
            operands = sorted([left, right], key=repr) if operation in {"=", "<>"} else [left, right]
            return (operation, *operands)
        return left

    def conjunction():
        values = [comparison()]
        while peek() == "and":
            take("and")
            values.append(comparison())
        return combine("and", values)

    def disjunction():
        values = [conjunction()]
        while peek() == "or":
            take("or")
            values.append(conjunction())
        return combine("or", values)

    result = disjunction()
    if position != len(tokens):
        raise ValueError("Unconsumed CHECK syntax")
    return result


def verify_details(connection, inspector, tables, schema):
    from .schema_compatibility import SchemaCheckError

    dialect = connection.dialect.name
    for name in MULTI_TABLES | {"validation_executions"}:
        table = tables[name]
        actual = {c["name"]: c for c in inspector.get_columns(name, schema=schema)}
        names = set(table.columns.keys()) if name in MULTI_TABLES else {"execution_mode", "policy_id", "version"}
        for column_name in names:
            expected = table.c[column_name]
            found = actual[column_name]
            if bool(found["nullable"]) != expected.nullable:
                raise SchemaCheckError("006_COLUMN_NULLABILITY_MISMATCH", name + "." + column_name)
            # SQLite affinities are intentionally portable. SQL Server physical
            # types must distinguish BIGINT/INT, DATETIME2 and NVARCHAR(MAX).
            if dialect == "mssql":
                expected_type = str(expected.type.compile(dialect=connection.dialect)).upper()
                actual_type = str(found["type"].compile(dialect=connection.dialect)).upper()
                # MSSQL reflection attaches the inherited database collation to
                # VARCHAR/NVARCHAR. Unspecified model collation must not make an
                # otherwise exact physical type fail readiness. Trusted tenant
                # FKs and the operator catalog gate verify reference collation.
                expected_type = re.sub(r"\s+COLLATE\s+.*$", "", expected_type)
                actual_type = re.sub(r"\s+COLLATE\s+.*$", "", actual_type)
                if expected_type == "DATETIME2(7)" and actual_type == "DATETIME2":
                    # The installed MSSQL dialect drops temporal scale in
                    # get_columns(). Verify the real catalog value, never infer 7.
                    scale = connection.scalar(text(
                        "SELECT scale FROM sys.columns WHERE object_id=OBJECT_ID(:object) "
                        "AND name=:column AND system_type_id=42"
                    ), {"object": "dbo." + name, "column": column_name})
                    actual_type = f"DATETIME2({scale})"
                if expected_type != actual_type:
                    raise SchemaCheckError("006_PHYSICAL_TYPE_MISMATCH", name + "." + column_name)
            if expected.server_default is not None:
                def normalize_default(value):
                    return re.sub(r"[\s()\[\]']", "", str(value or "")).upper()
                expected_default = expected.server_default.arg.compile(dialect=connection.dialect) if hasattr(expected.server_default.arg, "compile") else expected.server_default.arg
                if normalize_default(found.get("default")) != normalize_default(expected_default):
                    raise SchemaCheckError("006_DEFAULT_MISMATCH", name + "." + column_name)
        checks = reflected_checks(connection, inspector, name, schema)
        for constraint in table.constraints:
            if not isinstance(constraint, CheckConstraint):
                continue
            conditional = constraint._ddl_if
            if conditional is not None and conditional.dialect != dialect:
                continue
            if constraint.name not in checks or canonical_check(checks[constraint.name]) != canonical_check(str(constraint.sqltext)):
                raise SchemaCheckError("006_CHECK_MISMATCH", name + "." + constraint.name)
        if dialect == "mssql":
            invalid = connection.scalar(text("SELECT COUNT(*) FROM sys.check_constraints WHERE parent_object_id=OBJECT_ID(:object) AND (is_disabled=1 OR is_not_trusted=1)"), {"object": "dbo." + name})
            if invalid:
                raise SchemaCheckError("006_CHECK_DISABLED_OR_UNTRUSTED", name)
            indexes = {i["name"]: i for i in inspector.get_indexes(name, schema=schema)}
            for index in table.indexes:
                included = index.dialect_options["mssql"].get("include") or []
                if included and set(indexes[index.name].get("include_columns", [])) != set(included):
                    raise SchemaCheckError("006_INDEX_INCLUDE_MISMATCH", index.name)


def reflected_checks(connection, inspector, name, schema):
    """MSSQL Inspector CHECK reflection is unsupported; read exact definitions."""
    if connection.dialect.name == "mssql":
        return dict(connection.execute(text(
            "SELECT name, definition FROM sys.check_constraints "
            "WHERE parent_object_id=OBJECT_ID(:object)"
        ), {"object": schema + "." + name}).all())
    return {c["name"]: c["sqltext"] for c in inspector.get_check_constraints(name, schema=schema)}
