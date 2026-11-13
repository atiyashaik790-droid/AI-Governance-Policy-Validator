import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(PATH))
from sql_expiry_control import Expiry, tick


@pytest.mark.parametrize("scenario", ["hang", "crash", "delete_failure", "expired", "inventory_present", "arm_present", "logging_failure"])
def test_failure_scenarios(scenario):
    created = datetime(2026, 11, 7, tzinfo=timezone.utc)
    policy = Expiry("exact-test-target", created)
    events, deletes = [], []
    clock = created + timedelta(hours=5 if scenario == "expired" else 3)

    def stop():
        if scenario in {"hang", "crash"}:
            raise TimeoutError("bounded process termination failed")

    def delete(target):
        deletes.append(target)
        if scenario == "delete_failure" and len(deletes) == 1:
            raise RuntimeError("synthetic failure")

    def record(event):
        if scenario == "logging_failure":
            raise OSError("disk full")
        events.append(event)

    args = dict(now=lambda: clock, stop_test=stop, delete=delete,
                arm_absent=lambda _: scenario != "arm_present" and not (scenario == "delete_failure" and len(deletes) == 1),
                inventory_absent=lambda _: scenario != "inventory_present", record=record)
    result = tick(policy, **args)
    assert deletes == [policy.resource_id]
    if scenario in {"inventory_present", "arm_present", "delete_failure"}:
        assert result == "UNCONFIRMED"
    elif scenario == "expired":
        assert result == "DELETED_LATE"
        assert events[0]["event"] == "LIMIT_BREACH"
    else:
        assert result == "DELETED"
    if scenario == "delete_failure":
        assert tick(policy, **args) == "DELETED"


def test_wait_and_clock_jump():
    created = datetime(2026, 11, 7, tzinfo=timezone.utc)
    policy = Expiry("target", created)
    assert tick(policy, now=lambda: created, stop_test=None, delete=None,
                arm_absent=None, inventory_absent=None, record=None) == "WAIT"
    with pytest.raises(ValueError):
        tick(policy, now=lambda: created - timedelta(seconds=1), stop_test=None,
             delete=None, arm_absent=None, inventory_absent=None, record=None)
    with pytest.raises(ValueError):
        Expiry("target", created, lifetime=timedelta(hours=5))


def test_creation_blocked_before_any_side_effect():
    tree = ast.parse((PATH / "phase6b_approval_a.py").read_text())
    create = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "create")
    module = ast.Module(body=[create], type_ignores=[])
    namespace = {}
    exec(compile(module, "creation-guard", "exec"), namespace)
    with pytest.raises(RuntimeError, match="TEMPORARY_SQL_CREATION_BLOCKED"):
        namespace["create"]()
