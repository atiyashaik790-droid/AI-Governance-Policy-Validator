"""First-pass synchronization with real disposable 008 cleanup; no cloud calls."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import sys
import threading
import time
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

from app import database, protected_reviews as secure
from app.config import settings
import test_multi_policy_phase_b as phase_b

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/tests"))
from phase6b_sql_package_probe import assert_cleanup_healthy  # noqa: E402


@pytest.fixture
def health():
    health = secure.CleanupHealth()
    engine = object()
    health.start(engine)
    yield health, engine, SimpleNamespace(health=health)
    health.stop()


def test_first_success_is_required(health):
    state, engine, module = health
    with pytest.raises(AssertionError, match="did not complete"):
        assert_cleanup_healthy(module, engine, timeout=0)
    assert state.success_at is None
    state.record(engine, True)
    assert_cleanup_healthy(module, engine, timeout=0)


def test_failed_first_pass_completes_but_never_becomes_healthy(health):
    state, engine, module = health
    state.record(engine, False)
    assert state.wait_for_first_pass(engine, 0)
    assert state.success_at is None
    with pytest.raises(AssertionError):
        assert_cleanup_healthy(module, engine, timeout=0)


@pytest.mark.parametrize("failure", ["foreign", "stopped", "stale", "restart"])
def test_wrong_stopped_stale_or_restarted_worker_fails_closed(health, failure):
    state, engine, module = health
    state.record(engine, True)
    if failure == "foreign":
        engine = object()
    elif failure == "stopped":
        state.stop()
    elif failure == "stale":
        state.success_at = time.monotonic() - secure.MAX_HEARTBEAT_AGE - 1
    else:
        state.start(engine)
    with pytest.raises(AssertionError):
        assert_cleanup_healthy(module, engine, timeout=0)


def test_foreign_record_cannot_signal_completion(health):
    state, engine, _ = health
    state.record(object(), True)
    assert not state.wait_for_first_pass(engine, 0)
    assert not state.healthy(engine)


def test_stop_wakes_waiter_without_health(health):
    state, engine, _ = health
    with ThreadPoolExecutor() as pool:
        waiter = pool.submit(state.wait_for_first_pass, engine, 5)
        state.stop()
        assert waiter.result(timeout=1) is False
    assert not state.healthy(engine)


@pytest.mark.parametrize("denied", [False, True])
def test_real_008_worker_with_slow_or_denied_sql(tmp_path, monkeypatch, denied):
    path = tmp_path / "cleanup008.db"
    phase_b.migrate(path, "008")
    engine = phase_b.fixture_engine(path)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(database, "SessionLocal", factory)
    monkeypatch.setattr(settings, "review_capture_enabled", True)
    monkeypatch.setattr(settings, "review_cleanup_enabled", True)
    entered, release = threading.Event(), threading.Event()

    @event.listens_for(engine, "before_cursor_execute")
    def first_sql(conn, cursor, statement, parameters, context, executemany):
        if not entered.is_set():
            entered.set()
            assert release.wait(10)
            if denied:
                raise PermissionError("synthetic SQL permission denial")

    app = FastAPI(lifespan=secure.lifespan)
    try:
        with TestClient(app):
            assert entered.wait(5)
            if not denied:
                # Reproduce the exact retry-5 polling window with real SQL held
                # in flight. It cannot distinguish slow startup from failure.
                for _ in range(100):
                    if secure.health.healthy(engine):
                        break
                    time.sleep(0.02)
                with pytest.raises(AssertionError):
                    assert secure.health.healthy(engine)
            assert secure.health.success_at is None
            release.set()
            if denied:
                with pytest.raises(AssertionError):
                    assert_cleanup_healthy(secure, engine, timeout=5)
                assert secure.health.wait_for_first_pass(engine, 0)
                assert not secure.health.healthy(engine)
            else:
                assert_cleanup_healthy(secure, engine, timeout=5)
        assert not secure.health.healthy(engine)
    finally:
        release.set()
        engine.dispose()
