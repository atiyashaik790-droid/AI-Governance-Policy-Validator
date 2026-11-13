"""Read-only, bounded schema/runtime contract for the reviewed 004/005 bridge."""

from sqlalchemy import inspect, text
from fastapi import HTTPException
from .models import Base

SUPPORTED_REVISIONS = ("004", "005")
SSO_TABLES = {"sso_memberships", "sso_transactions", "sso_sessions"}
RUNTIME_PERMISSIONS = {
    "policies": ("SELECT", "INSERT", "UPDATE", "DELETE"),
    "policy_versions": ("SELECT", "INSERT"),
    "active_policy_assignments": ("SELECT", "INSERT", "UPDATE"),
    "audit_events": ("SELECT", "INSERT"),
    "validation_executions": ("SELECT", "INSERT"),
    "human_review_cases": ("SELECT", "INSERT", "UPDATE"),
    "feedback_records": ("SELECT", "INSERT"),
    "evaluation_exports": ("SELECT", "INSERT", "UPDATE"),
    "alembic_version": ("SELECT",),
    "demo_sessions": ("SELECT", "INSERT", "UPDATE"),
    "inference_rate_buckets": ("SELECT", "INSERT", "UPDATE"),
    "inference_usage": ("SELECT", "INSERT", "UPDATE"),
    "export_jobs": ("SELECT", "INSERT", "UPDATE"),
    "review_assignments": ("SELECT", "INSERT", "UPDATE"),
    "review_notes": ("SELECT", "INSERT"),
    "sso_memberships": ("SELECT",),
    "sso_transactions": ("SELECT", "INSERT", "UPDATE"),
    "sso_sessions": ("SELECT", "INSERT", "UPDATE"),
}
HISTORY_TABLES = ("audit_events", "policy_versions", "review_notes")


class SchemaCheckError(ValueError):
    def __init__(self, category, object_name=None):
        self.safe_diagnostic = {"category": category, "object": object_name}
        super().__init__(category)


def unavailable():
    return HTTPException(503, "Reviewed schema objects and runtime permissions are required")


def verify_runtime_permissions(connection, *, require_sso):
    # Evaluate every grant on every check, in one round trip. NULL and
    # missing permissions fail closed; nothing is cached across requests.
    predicates, parameters = [], {}
    for table, permissions in RUNTIME_PERMISSIONS.items():
        if table in SSO_TABLES and not require_sso:
            continue
        for permission in permissions:
            i = len(predicates)
            parameters[f"object_{i}"] = "dbo." + table
            parameters[f"permission_{i}"] = permission
            predicates.append(f"HAS_PERMS_BY_NAME(:object_{i}, 'OBJECT', :permission_{i}) = 1")
    query = "SELECT CASE WHEN " + " AND ".join(predicates) + " THEN 1 ELSE 0 END"
    if connection.scalar(text(query), parameters) != 1:
        raise SchemaCheckError("REQUIRED_EFFECTIVE_PERMISSION_MISSING")


def inspect_schema(db, *, require_sso=False):
    """No writes/cache: migration, revocation of grants and drift are seen next check.

    Unversioned SQLite is allowed only for existing disposable fixture contracts.
    Azure SQL always needs exactly one readable, supported Alembic revision.
    """
    try:
        connection = db.connection()
        inspector = inspect(connection)
        dialect = connection.dialect.name
        if dialect not in {"sqlite", "mssql"}:
            raise SchemaCheckError("DATABASE_DIALECT_UNSUPPORTED")
        schema = "dbo" if dialect == "mssql" else None
        present = set(inspector.get_table_names(schema=schema))
        versioned = "alembic_version" in present
        if not versioned and dialect != "sqlite":
            raise SchemaCheckError("ALEMBIC_HISTORY_MISSING_OR_NOT_VISIBLE", "alembic_version")
        if versioned:
            rows = list(connection.execute(text("SELECT version_num FROM " + ("dbo." if schema else "") + "alembic_version")).scalars())
            if len(rows) != 1 or rows[0] not in SUPPORTED_REVISIONS:
                raise SchemaCheckError("ALEMBIC_REVISION_UNSUPPORTED_OR_AMBIGUOUS", "alembic_version")
            revision = rows[0]
        else:
            revision = "005" if SSO_TABLES <= present else "004"
        if require_sso and (revision != "005" or not versioned and dialect != "sqlite"):
            raise SchemaCheckError("SSO_REQUIRES_REVISION_005")
        expected = {n: t for n, t in Base.metadata.tables.items() if revision == "005" or n not in SSO_TABLES}
        if not set(expected) <= present:
            raise SchemaCheckError("REQUIRED_TABLE_MISSING_OR_NOT_VISIBLE", sorted(set(expected) - present)[0])
        # Partial 005 creation with a 004 marker is not a clean migration boundary.
        if revision == "004" and present & SSO_TABLES:
            raise SchemaCheckError("PARTIAL_005_OBJECTS_AT_REVISION_004")
        for name, model in expected.items():
            columns = {c["name"]: c for c in inspector.get_columns(name, schema=schema)}
            for column in model.columns:
                actual = columns.get(column.name)
                if not actual or actual["type"]._type_affinity is not column.type._type_affinity:
                    raise SchemaCheckError("COLUMN_MISSING_OR_TYPE_MISMATCH", name + "." + column.name)
                length = getattr(column.type, "length", None)
                if length and getattr(actual["type"], "length", 0) != length:
                    raise SchemaCheckError("COLUMN_LENGTH_MISMATCH", name + "." + column.name)
                if not column.nullable and actual["nullable"]:
                    raise SchemaCheckError("COLUMN_NULLABILITY_MISMATCH", name + "." + column.name)
            if inspector.get_pk_constraint(name, schema=schema)["constrained_columns"] != list(model.primary_key.columns.keys()):
                raise SchemaCheckError("PRIMARY_KEY_MISMATCH", name)
            indexes = inspector.get_indexes(name, schema=schema)
            for index in model.indexes:
                if not any(
                    i["name"] == index.name and i["column_names"] == list(index.columns.keys()) and bool(i["unique"]) == bool(index.unique)
                    for i in indexes
                ):
                    raise SchemaCheckError("REQUIRED_INDEX_MISSING_OR_MISMATCH", name + "." + index.name)
            # MSSQL has no get_unique_constraints() implementation. Its supported
            # get_indexes() reflects UNIQUE constraints through their backing indexes.
            uniques = {tuple(i["column_names"]) for i in indexes if i["unique"]}
            if dialect != "mssql":
                uniques.update(tuple(u["column_names"]) for u in inspector.get_unique_constraints(name, schema=schema))
            for constraint in model.constraints:
                if type(constraint).__name__ == "UniqueConstraint" and tuple(constraint.columns.keys()) not in uniques:
                    raise SchemaCheckError("UNIQUE_CONSTRAINT_MISSING", name)
            if dialect == "mssql":
                invalid_indexes = connection.scalar(
                    text(
                        "SELECT COUNT(*) FROM sys.indexes WHERE object_id=OBJECT_ID(:object) AND (is_disabled=1 OR is_hypothetical=1 OR has_filter=1)"
                    ),
                    {"object": "dbo." + name},
                )
                if invalid_indexes:
                    raise SchemaCheckError("DISABLED_HYPOTHETICAL_OR_FILTERED_INDEX", name)
            fks = inspector.get_foreign_keys(name, schema=schema)
            for fk in model.foreign_key_constraints:
                if not any(
                    f["constrained_columns"] == [e.parent.name for e in fk.elements]
                    and f.get("referred_schema") in (schema, None)
                    and f.get("options", {}).get("ondelete", "NO ACTION").replace("_", " ") == "NO ACTION"
                    and f["referred_table"] == fk.elements[0].column.table.name
                    and f["referred_columns"] == [e.column.name for e in fk.elements]
                    for f in fks
                ):
                    raise SchemaCheckError("FOREIGN_KEY_MISMATCH", name)
        if versioned:
            if dialect == "sqlite":
                triggers = {r[0] for r in connection.execute(text("SELECT name FROM sqlite_master WHERE type='trigger'"))}
                if not all(f"immutable_{t}_{a}" in triggers for t in HISTORY_TABLES for a in ("update", "delete")):
                    raise SchemaCheckError("HISTORY_TRIGGER_MISSING")
            else:
                for table in HISTORY_TABLES:
                    enabled = connection.scalar(
                        text("SELECT COUNT(*) FROM sys.triggers WHERE parent_id=OBJECT_ID(:object) AND name=:name AND is_disabled=0"),
                        {"object": "dbo." + table, "name": "immutable_" + table},
                    )
                    if enabled != 1:
                        raise SchemaCheckError("HISTORY_TRIGGER_MISSING_OR_DISABLED", table)
                invalid = connection.scalar(
                    text("SELECT COUNT(*) FROM sys.foreign_keys WHERE schema_id=SCHEMA_ID('dbo') AND (is_disabled=1 OR is_not_trusted=1)")
                )
                if invalid:
                    raise SchemaCheckError("DISABLED_OR_UNTRUSTED_FOREIGN_KEY")
        if dialect == "mssql":
            verify_runtime_permissions(connection, require_sso=require_sso)
        return {"revision": revision if versioned else "UNVERSIONED_LOCAL", "versioned": versioned, "sso_schema": revision == "005"}
    except Exception:
        raise unavailable() from None
