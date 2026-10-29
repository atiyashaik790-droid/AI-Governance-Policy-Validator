"""Tenant-scoped pagination on disposable SQLite and connection-free MSSQL compilation."""

import re
from unittest.mock import Mock

import pytest
from sqlalchemy.dialects import mssql

from app.main import app, get_database, list_records, serialize
from app.models import Audit, Execution, Export, Policy, Review
from app.schemas import PolicyDocument
from app.security import Identity


@pytest.mark.parametrize("model", [Policy, Audit, Execution, Review, Export])
@pytest.mark.parametrize("offset_fetch", [False, True], ids=["row_number", "offset_fetch"])
def test_mssql_pagination_ordering(model, offset_fetch):
    database = Mock()
    database.scalars.return_value = []
    assert list_records(database, Identity("fixture", "one", "Admin"), model, 2, 3) == []
    statement = database.scalars.call_args.args[0]
    dialect = mssql.dialect()
    dialect._supports_offset_fetch = offset_fetch
    sql = str(statement.compile(dialect=dialect, compile_kwargs={"literal_binds": True}))
    table = model.__tablename__
    expected = f"{table}.created DESC, {table}.id" if hasattr(model, "created") else f"{table}.id DESC"
    if offset_fetch:
        ordering = re.search(r"ORDER BY (.*?)\s+OFFSET", sql).group(1)
        assert "OFFSET 2 ROWS" in sql and "FETCH FIRST 3 ROWS ONLY" in sql
    else:
        ordering = re.search(r"ROW_NUMBER\(\) OVER \(ORDER BY ([^)]+)\)", sql).group(1)
        assert "mssql_rn > 2" in sql and "mssql_rn <= 3 + 2" in sql
    assert ordering == expected
    assert f"{table}.tenant = 'one'" in sql


@pytest.mark.parametrize("model,endpoint", [(Policy, "/api/policies"), (Audit, "/api/audit/events")])
def test_pagination_empty_dataset(client, model, endpoint):
    for offset in (0, 1, 20):
        response = client.get(endpoint, params={"offset": offset, "limit": 2})
        assert response.status_code == 200 and response.json() == []


@pytest.mark.parametrize("model,endpoint", [(Policy, "/api/policies"), (Audit, "/api/audit/events")])
def test_pagination_multiple_records_and_tenant_isolation(client, model, endpoint):
    def identifier(number):
        return f"00000000-0000-0000-0000-{number:012d}"

    def record(number, tenant, created):
        if model is Policy:
            return Policy(
                id=identifier(number),
                tenant=tenant,
                name="Synthetic pagination",
                draft=PolicyDocument(name="Synthetic pagination").model_dump_json(),
            )
        return Audit(id=identifier(number), tenant=tenant, actor="fixture", action="fixture", resource="fixture", created=created)

    dependency = app.dependency_overrides[get_database]()
    session = next(dependency)
    try:
        rows = [
            record(number, "one", created)
            for number, created in (
                (1, "2026-10-29T12:00:00+00:00"),
                (2, "2026-10-28T12:00:00+00:00"),
                (3, "2026-10-29T12:00:00+00:00"),
                (4, "2026-10-27T12:00:00+00:00"),
            )
        ]
        session.add_all(rows + [record(99, "two", "2026-10-30T12:00:00+00:00")])
        session.flush()
        expected = {row.id: serialize(row) for row in rows}
        session.commit()
    finally:
        dependency.close()
    order = [4, 3, 2, 1] if model is Policy else [1, 3, 2, 4]
    ordered_rows = [expected[identifier(number)] for number in order]
    for offset, limit in ((0, 2), (2, 2), (1, 2), (3, 2), (4, 2), (20, 2), (0, 1), (0, 100)):
        response = client.get(endpoint, params={"offset": offset, "limit": limit})
        assert response.status_code == 200
        assert response.json() == ordered_rows[offset : offset + limit]
    # Repeating tied timestamps produces the same page, ordered by ascending ID.
    assert client.get(endpoint, params={"offset": 0, "limit": 2}).json() == ordered_rows[:2]
    client.headers["Authorization"] = "Bearer foreign"
    response = client.get(endpoint, params={"offset": 0, "limit": 100})
    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [identifier(99)]
    assert all(row["tenant"] == "two" for row in response.json())
