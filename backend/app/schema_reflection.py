"""Per-verification SQL Server key metadata; no cross-check or request cache."""
from sqlalchemy import text


class BatchedKeys:
    """Keep SQLAlchemy column reflection; fetch PK/index/FK rows in two reads.

    The contract verifier still compares every key and checks live permissions,
    trigger/constraint trust and disabled/filtered indexes on every invocation.
    """

    def __init__(self, connection, inspector):
        self.inspector = inspector
        self.primary, self.indexes, self.foreign = {}, {}, {}
        rows = connection.execute(text("""
SELECT t.name AS table_name, i.name AS index_name, i.is_primary_key,
       i.is_unique, c.name AS column_name, ic.key_ordinal,
       ic.is_included_column, ic.index_column_id
FROM sys.tables t
JOIN sys.schemas s ON s.schema_id=t.schema_id
JOIN sys.indexes i ON i.object_id=t.object_id AND i.type<>0
JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id
JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id
WHERE s.name='dbo'
ORDER BY t.name,i.index_id,ic.key_ordinal,ic.index_column_id
""")).mappings()
        indexes = {}
        for row in rows:
            name = row["table_name"]
            if row["is_primary_key"]:
                if row["key_ordinal"] > 0 and not row["is_included_column"]:
                    self.primary.setdefault(name, []).append(row["column_name"])
                continue
            key = (name, row["index_name"])
            if key not in indexes:
                indexes[key] = {"name": row["index_name"], "unique": bool(row["is_unique"]),
                                "column_names": [], "include_columns": []}
                self.indexes.setdefault(name, []).append(indexes[key])
            if row["is_included_column"]:
                indexes[key]["include_columns"].append(row["column_name"])
            elif row["key_ordinal"] > 0:
                indexes[key]["column_names"].append(row["column_name"])
        rows = connection.execute(text("""
SELECT t.name AS table_name, fk.name AS constraint_name,
       c.name AS column_name, rs.name AS referred_schema,
       rt.name AS referred_table, rc.name AS referred_column,
       fk.delete_referential_action_desc AS delete_action
FROM sys.foreign_keys fk
JOIN sys.tables t ON t.object_id=fk.parent_object_id
JOIN sys.schemas s ON s.schema_id=t.schema_id
JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id=fk.object_id
JOIN sys.columns c ON c.object_id=t.object_id AND c.column_id=fkc.parent_column_id
JOIN sys.tables rt ON rt.object_id=fk.referenced_object_id
JOIN sys.schemas rs ON rs.schema_id=rt.schema_id
JOIN sys.columns rc ON rc.object_id=rt.object_id AND rc.column_id=fkc.referenced_column_id
WHERE s.name='dbo'
ORDER BY t.name,fk.object_id,fkc.constraint_column_id
""")).mappings()
        foreign = {}
        for row in rows:
            key = (row["table_name"], row["constraint_name"])
            if key not in foreign:
                foreign[key] = {"name": row["constraint_name"], "constrained_columns": [],
                                "referred_columns": [], "referred_schema": row["referred_schema"],
                                "referred_table": row["referred_table"],
                                "options": {"ondelete": row["delete_action"]}}
                self.foreign.setdefault(row["table_name"], []).append(foreign[key])
            foreign[key]["constrained_columns"].append(row["column_name"])
            foreign[key]["referred_columns"].append(row["referred_column"])

    def __getattr__(self, name):
        return getattr(self.inspector, name)

    def get_pk_constraint(self, name, schema):
        assert schema == "dbo"
        return {"constrained_columns": self.primary.get(name, [])}

    def get_indexes(self, name, schema):
        assert schema == "dbo"
        return self.indexes.get(name, [])

    def get_foreign_keys(self, name, schema):
        assert schema == "dbo"
        return self.foreign.get(name, [])
