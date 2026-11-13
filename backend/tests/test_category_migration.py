"""Revision 009 initializes categories and preserves existing audit history."""

import json
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schema_compatibility import inspect_schema
from test_multi_policy_phase_b import fixture_engine, migrate


def test_empty_database_initializes_builtins_and_associations(tmp_path):
    database_path = tmp_path / "category-009.db"
    migrate(database_path, "009")
    engine = fixture_engine(database_path)
    with Session(engine) as db:
        assert inspect_schema(db, require_sso=True)["revision"] == "009"
        assert db.scalar(text("SELECT COUNT(*) FROM governance_categories WHERE builtin=1 AND tenant='*'")) == 8
        assert db.scalar(text("SELECT COUNT(*) FROM policy_categories")) == 0
    engine.dispose()


def test_revision_008_data_survives_additive_category_migration(tmp_path):
    database_path = tmp_path / "upgrade-009.db"
    migrate(database_path, "008")
    engine = fixture_engine(database_path)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO audit_events (id, tenant, actor, action, resource, created) "
                "VALUES ('synthetic-1','tenant-1','admin','test.marker','none','2026-11-10T00:00:00Z')"
            )
        )
    engine.dispose()
    migrate(database_path, "009")
    engine = fixture_engine(database_path)
    with Session(engine) as db:
        assert db.scalar(text("SELECT COUNT(*) FROM audit_events WHERE id='synthetic-1'")) == 1
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == "009"
    engine.dispose()


def test_revision_009_backfills_embedded_draft_rules_without_changing_versions(tmp_path):
    database_path = tmp_path / "embedded-009.db"
    migrate(database_path, "008")
    engine = fixture_engine(database_path)
    document = {
        "name": "Legacy",
        "custom_categories": [
            {"id": "finance", "name": "Finance", "action": "BLOCK", "detection": "keyword", "values": ["private finance"]}
        ],
    }
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO policies (id, tenant, name, draft, status, enabled, revision, row_version) "
                "VALUES ('legacy-policy','one','Legacy',:draft,'DRAFT',1,1,1)"
            ),
            {"draft": json.dumps(document)},
        )
    engine.dispose()
    migrate(database_path, "009")
    engine = fixture_engine(database_path)
    with Session(engine) as db:
        category_id = db.scalar(text("SELECT id FROM governance_categories WHERE tenant='one'"))
        assert category_id and category_id != "finance"
        assert db.scalar(text("SELECT COUNT(*) FROM policy_categories WHERE policy_id='legacy-policy'")) == 1
        migrated = json.loads(db.scalar(text("SELECT draft FROM policies WHERE id='legacy-policy'")))
        assert migrated["custom_categories"][0]["id"] == category_id
        assert db.scalar(text("SELECT row_version FROM policies WHERE id='legacy-policy'")) == 2
    engine.dispose()
