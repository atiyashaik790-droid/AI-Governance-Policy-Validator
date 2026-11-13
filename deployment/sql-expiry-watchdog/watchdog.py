"""Review-only continuous WebJob. Standard library only; disabled by default.

An outer process kills hung passes. Every pass reloads durable state and reads
actual ARM creationDate. No automatic activation or Azure resource creation.
"""

import argparse
import base64
from datetime import datetime, timedelta, timezone
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

SUB = "25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6"
GROUP = "rg_techdemo_Atiya_Tabsum_Shaik"
SERVER = f"/subscriptions/{SUB}/resourceGroups/{GROUP}/providers/Microsoft.Sql/servers/sql-governance-validator-dev-atiya"
TARGET = SERVER + "/databases/sqldb-gpv-mig-20261106-a1"
PRINCIPAL = "600447fe-5fea-4801-9033-ab4aafc474cc"
TENANT = "4ac50105-0c66-404e-a107-7cbd8a9a6442"
API = "?api-version=2023-08-01"
UTC = timezone.utc


class SafeFailure(Exception):
    pass


def instant(value):
    value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise SafeFailure("INVALID_UTC")
    return value


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        if self.directory.is_symlink():
            raise SafeFailure("STATE_PATH_UNSAFE")
        self.directory.mkdir(parents=True, mode=0o700, exist_ok=True)

    def load(self):
        path = self.directory / "state.json"
        if path.is_symlink():
            raise SafeFailure("STATE_PATH_UNSAFE")
        return json.loads(path.read_text()) if path.exists() else {}

    def save(self, state):
        path = self.directory / "state.tmp"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(state, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(path, self.directory / "state.json")
        fd = os.open(self.directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def log(self, event, **fields):
        # Call sites provide fixed labels and parsed timestamps/status only.
        record = {"utc": datetime.now(UTC).isoformat(), "event": event, **fields}
        line = json.dumps(record, sort_keys=True)
        print(line, flush=True)
        fd = os.open(self.directory / "audit.jsonl", os.O_APPEND | os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(line + "\n")
            stream.flush()
            os.fsync(stream.fileno())


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def request(url, headers, method="GET"):
    # Do not follow ARM async Location/nextLink or forward tokens to another host.
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(Request(url, headers=headers, method=method), timeout=8) as response:
            body = response.read(2_000_001)
            if len(body) > 2_000_000:
                raise SafeFailure("RESPONSE_TOO_LARGE")
            return response.status, json.loads(body) if body else {}
    except HTTPError as error:
        # Never include response body, headers, URL credentials or raw exceptions.
        error.close()
        return error.code, {}


def identity_token():
    endpoint = os.environ.get("IDENTITY_ENDPOINT", "")
    header = os.environ.get("IDENTITY_HEADER", "")
    parsed = urlsplit(endpoint)
    try:
        address = ipaddress.ip_address(parsed.hostname or "")
    except ValueError:
        raise SafeFailure("IDENTITY_ENDPOINT_INVALID") from None
    if parsed.scheme != "http" or not (address.is_loopback or address.is_link_local) or parsed.username or parsed.password or parsed.query or parsed.fragment or not header:
        raise SafeFailure("IDENTITY_ENDPOINT_INVALID")
    status, body = request(endpoint + "?" + urlencode({"resource": "https://management.azure.com/", "api-version": "2019-08-01"}), {"X-IDENTITY-HEADER": header})
    if status != 200:
        raise SafeFailure("IDENTITY_UNAVAILABLE")
    token = body["access_token"]
    claims = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "==="))
    if claims.get("oid") != PRINCIPAL or claims.get("tid") != TENANT or claims.get("aud", "").rstrip("/") != "https://management.azure.com" or int(claims.get("exp", 0)) <= time.time() + 30:
        raise SafeFailure("IDENTITY_MISMATCH")
    # Token comes from platform-provided local MI endpoint; ARM validates it.
    return token


class Arm:
    def __init__(self):
        self.headers = {"Authorization": "Bearer " + identity_token()}

    def get(self):
        return request("https://management.azure.com" + TARGET + API, self.headers)

    def delete(self):
        # No arbitrary resource ID or method accepted from configuration.
        return request("https://management.azure.com" + TARGET + API, self.headers, "DELETE")[0]


def validate(policy):
    if policy.get("target") != TARGET or policy.get("cleanup_after_seconds") != 10800 or policy.get("maximum_lifetime_seconds") != 14400:
        raise SafeFailure("POLICY_INVALID")
    if policy.get("mode") not in {"disabled", "observe", "armed"}:
        raise SafeFailure("POLICY_INVALID")
    if policy["mode"] != "disabled":
        approval = policy.get("approval_id", "")
        if not approval.startswith("WATCHDOG-NEW-") or len(approval) > 80:
            raise SafeFailure("FRESH_APPROVAL_REQUIRED")
        begin, end = instant(policy["creation_not_before"]), instant(policy["creation_not_after"])
        if not timedelta(0) < end - begin <= timedelta(hours=1):
            raise SafeFailure("CREATION_WINDOW_INVALID")


def tick(policy, store, arm, now, permit_delete=False, inventory=None):
    validate(policy)
    if policy["mode"] == "disabled":
        store.log("DISABLED")
        return "DISABLED"
    state = store.load()
    if state and (state.get("approval_id") != policy["approval_id"] or state.get("target") != TARGET):
        raise SafeFailure("STATE_APPROVAL_MISMATCH")
    if state.get("creation_utc"):
        created = instant(state["creation_utc"])
        deadline = created + timedelta(hours=4)
        if now >= deadline and state.get("phase") != "CONFIRMED":
            store.log("LIMIT_BREACH", deadline_utc=deadline.isoformat())
    status, database = arm.get()
    if status == 404:
        if not state:
            store.log("TARGET_ABSENT_UNBOUND")
            return "UNBOUND"
        state["phase"] = "ARM_ABSENT_INVENTORY_PENDING"
        state["absence_observed_utc"] = now.isoformat()
        store.save(state)
        # Separate authenticated observer required. Never infer inventory from GET.
        if inventory is not None and inventory(TARGET) is True:
            state["phase"] = "CONFIRMED"
            state["confirmation_utc"] = now.isoformat()
            store.save(state)
            store.log("DELETION_CONFIRMED", observed_utc=now.isoformat(), late=now >= deadline)
            return "CONFIRMED"
        store.log("ARM_ABSENT_INVENTORY_PENDING")
        return "UNCONFIRMED"
    if status != 200:
        store.log("ARM_READ_FAILED", http_status=status)
        return "UNCONFIRMED"
    if state.get("phase") in {"CONFIRMED", "ARM_ABSENT_INVENTORY_PENDING"}:
        raise SafeFailure("RESOURCE_REAPPEARED")
    tags = database.get("tags", {})
    if database.get("id", "").lower() != TARGET.lower() or tags.get("purpose") != "phase6b-approval-a-synthetic" or tags.get("watchdogApproval") != policy["approval_id"]:
        raise SafeFailure("TARGET_OWNERSHIP_MISMATCH")
    created = instant(database["properties"]["creationDate"])
    if not instant(policy["creation_not_before"]) <= created <= instant(policy["creation_not_after"]) or created > now:
        raise SafeFailure("CREATION_TIME_INVALID")
    if state and state.get("creation_utc") != created.isoformat():
        raise SafeFailure("INCARNATION_MISMATCH")
    if state.get("last_seen_utc") and now < instant(state["last_seen_utc"]):
        raise SafeFailure("CLOCK_MOVED_BACKWARD")
    state.update(approval_id=policy["approval_id"], target=TARGET,
                 creation_utc=created.isoformat(), last_seen_utc=now.isoformat())
    stop = created + timedelta(hours=3)
    deadline = created + timedelta(hours=4)
    state.update(stop_utc=stop.isoformat(), deadline_utc=deadline.isoformat())
    state.setdefault("phase", "BOUND")
    # Persist binding before any DELETE, including after process restart.
    store.save(state)
    if now >= deadline:
        store.log("LIMIT_BREACH", deadline_utc=deadline.isoformat())
    if now < stop:
        store.log("HEARTBEAT", creation_utc=created.isoformat(), cleanup_utc=stop.isoformat(), deadline_utc=deadline.isoformat())
        return "WAIT"
    if policy["mode"] != "armed" or not permit_delete:
        store.log("DELETE_DISABLED")
        return "OBSERVE"
    if state.get("retry_after_utc") and now < instant(state["retry_after_utc"]):
        return "RETRY_WAIT"
    state["phase"] = "DELETE_PENDING"
    state["attempts"] = state.get("attempts", 0) + 1
    state["retry_after_utc"] = (now + timedelta(seconds=min(60, 5 * 2 ** min(state["attempts"], 4)))).isoformat()
    store.save(state)
    # Logging failure cannot prevent already-bound cleanup.
    try:
        store.log("DELETE_INTENT", attempt=state["attempts"], deadline_utc=deadline.isoformat())
    except OSError:
        pass
    result = arm.delete()
    store.log("DELETE_RESPONSE", http_status=result, attempt=state["attempts"])
    # 200/202/204 are never absence confirmation. Next pass independently GETs.
    return "DELETE_PENDING"


def run_bounded(command, timeout=25):
    """Actual subprocess deadline, not a mocked network timeout."""
    child = subprocess.Popen(command, start_new_session=True)
    try:
        return child.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        import signal
        os.killpg(child.pid, signal.SIGKILL)
        child.wait()
        return 124


def report_deadline(store):
    """Supervisor can report a known breach even if the MI/ARM child hangs."""
    try:
        state = store.load()
        if state.get("target") == TARGET and state.get("creation_utc") and state.get("phase") != "CONFIRMED":
            deadline = instant(state["creation_utc"]) + timedelta(hours=4)
            if datetime.now(UTC) >= deadline:
                store.log("LIMIT_BREACH", deadline_utc=deadline.isoformat())
    except Exception:
        print('{"event":"DEADLINE_OBSERVATION_FAILED"}', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", required=True)
    parser.add_argument("--state-dir", default="/home/data/gpv-sql-expiry-watchdog")
    parser.add_argument("--supervise", action="store_true")
    parser.add_argument("--permit-delete", action="store_true")
    args = parser.parse_args()
    store = Store(args.state_dir)
    if args.supervise:
        while True:
            report_deadline(store)
            command = [sys.executable, "-I", str(Path(__file__).resolve()), "--policy", args.policy, "--state-dir", args.state_dir]
            if args.permit_delete:
                command.append("--permit-delete")
            result = run_bounded(command)
            report_deadline(store)
            try:
                store.log("PASS_FINISHED", exit_code=result)
            except OSError:
                print('{"event":"AUDIT_STORAGE_FAILED"}', flush=True)
            time.sleep(10)
    else:
        fd = os.open(store.directory / "pass.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            policy = json.loads(Path(args.policy).read_text())
            validate(policy)
            arm = None if policy["mode"] == "disabled" else Arm()
            tick(policy, store, arm, datetime.now(UTC), args.permit_delete)
        finally:
            os.close(fd)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Never print exception messages, policy contents or managed identity data.
        print('{"event":"PASS_FAILED"}', flush=True)
        sys.exit(1)
