"""Sanitized inclusive stage timings; never emit SQL, parameters or identities."""
from contextlib import contextmanager
from contextvars import ContextVar
import json
import logging
import time

from sqlalchemy import event

correlation = ContextVar("stage_correlation", default=None)
logger = logging.getLogger("governance.stages")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
logger.propagate = False


@contextmanager
def stage(name, db=None, deadline=None):
    started = time.monotonic()
    stats = {"event": "governance.stage", "stage": name, "outcome": "error"}
    connection = None
    query_started = None
    query_seconds = 0
    query_count = 0
    catalog_count = 0

    def before(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_started, query_count, catalog_count
        query_started = time.monotonic()
        query_count += 1
        if any(value in statement.lower() for value in ("sys.", "information_schema", "sqlite_master", "pragma ")):
            catalog_count += 1

    def after(*args):
        nonlocal query_started, query_seconds
        if query_started is not None:
            query_seconds += time.monotonic() - query_started
            query_started = None

    try:
        if db is not None:
            connection = db.connection()
            stats["connection_acquire_ms"] = round((time.monotonic() - started) * 1000, 3)
            event.listen(connection, "before_cursor_execute", before)
            event.listen(connection, "after_cursor_execute", after)
        yield
        stats["outcome"] = "ok"
    finally:
        if query_started is not None:
            query_seconds += time.monotonic() - query_started
        if connection is not None:
            event.remove(connection, "before_cursor_execute", before)
            event.remove(connection, "after_cursor_execute", after)
        stats["duration_ms"] = round((time.monotonic() - started) * 1000, 3)
        if db is not None:
            stats.update(sql_count=query_count, catalog_count=catalog_count,
                         sql_ms=round(query_seconds * 1000, 3))
        if deadline is not None:
            stats["deadline_remaining_ms"] = round((deadline - time.monotonic()) * 1000, 3)
        if correlation.get() is not None:
            stats["correlation_id"] = correlation.get()
        logger.info(json.dumps(stats))
