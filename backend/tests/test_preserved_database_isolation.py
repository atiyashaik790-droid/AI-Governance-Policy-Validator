"""Automated tests must never open the preserved demo database for writes."""

import sqlite3
from pathlib import Path

import pytest


def test_preserved_database_write_is_blocked():
    preserved = Path(__file__).resolve().parents[2] / "private/demo-preserved/offline.db"
    with pytest.raises(RuntimeError, match="cannot write"):
        sqlite3.connect(preserved)


def test_disposable_database_remains_writable(tmp_path):
    with sqlite3.connect(tmp_path / "test.db") as database:
        database.execute("CREATE TABLE evidence (id INTEGER PRIMARY KEY)")
        database.execute("INSERT INTO evidence (id) VALUES (1)")
        assert database.execute("SELECT COUNT(*) FROM evidence").fetchone()[0] == 1
