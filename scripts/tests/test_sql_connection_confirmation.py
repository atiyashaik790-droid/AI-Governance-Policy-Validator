from contextlib import contextmanager
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sql_connection_confirmation import confirm


class Engine:
    def __init__(self, failures):
        self.failures = list(failures)
        self.calls = self.disposed = 0

    @contextmanager
    def connect(self):
        self.calls += 1
        if self.failures:
            error = self.failures.pop(0)
            if error:
                raise error
        yield self

    def execute(self, statement):
        assert str(statement) == "SELECT 1"
        return self

    def scalar_one(self):
        return 1

    def dispose(self):
        self.disposed += 1


def test_transient_recovery_is_bounded_and_sanitized():
    events = []
    engine = Engine([Exception("08S01", "secret token and server")])
    assert confirm(engine, events.append)
    assert engine.calls == 2 and engine.disposed == 1
    assert events[0]["sqlstates"] == ["08S01"]
    assert "secret" not in str(events)


def test_persistent_disconnect_stops():
    engine = Engine([Exception("08S01"), Exception("08S01")])
    assert not confirm(engine, lambda _: None)
    assert engine.calls == 2 and engine.disposed == 1


def test_permission_and_tls_failures_are_not_retried():
    for error in (Exception("42000", "permission (229)"),
                  Exception("TLS certificate invalid")):
        engine = Engine([error])
        assert not confirm(engine, lambda _: None)
        assert engine.calls == 1 and engine.disposed == 0
