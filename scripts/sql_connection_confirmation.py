"""Bounded operator-only transport diagnosis. Never substitutes for /ready.

No writes, TLS changes, timeout changes or automatic execution. Call only after
exact-target/identity checks. Two SELECT 1 attempts at most, on fresh checkouts;
the existing driver's connect/query timeouts continue to bound each operation.
"""

import time

from sqlalchemy import text

from sql_diagnostics import classify


def confirm(engine, record, clock=time.time):
    for attempt in (1, 2):
        started = clock()
        stage = "connect"
        acquired = None
        try:
            with engine.connect() as connection:
                acquired = clock()
                stage = "select"
                if connection.execute(text("SELECT 1")).scalar_one() != 1:
                    raise RuntimeError("Unexpected transport probe result")
            record({"event": "sql.transport_probe", "attempt": attempt,
                    "stage": "complete", "outcome": "PASS",
                    "started_epoch": started, "finished_epoch": clock(),
                    "checkout_seconds": acquired - started,
                    "connection_use_seconds": clock() - acquired})
            return True
        except Exception as error:
            diagnostic = classify(error, stage)
            record({"event": "sql.transport_probe", "attempt": attempt,
                    "stage": stage, "outcome": "FAIL",
                    "started_epoch": started, "finished_epoch": clock(),
                    "checkout_seconds": None if acquired is None else acquired - started,
                    "connection_use_seconds": None if acquired is None else clock() - acquired,
                    "category": diagnostic["category"],
                    "sqlstates": diagnostic["sqlstates"]})
            if diagnostic["category"] != "SQL_TRANSPORT_FAILURE" or attempt == 2:
                return False
            # Recover only this isolated read-only probe. Never replay a write,
            # migration, reveal or readiness transaction after ambiguous failure.
            engine.dispose()
    return False
