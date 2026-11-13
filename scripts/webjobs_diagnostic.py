"""Offline-testable WebJobs diagnostic and cleanup-only recovery.

The Azure CLI adapter is in webjobs_diagnostic_azure.py; neither module performs
I/O on import. Conditional configuration replacement must fail on a lost update,
never silently overwrite concurrent settings. See the integration review.
"""

from contextlib import contextmanager
from dataclasses import dataclass, field
import fcntl
import json
import math
import os
from pathlib import Path
import re
import secrets
import ssl
import stat
import time
from typing import Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

FLAG = "WEBSITE_SKIP_RUNNING_KUDUAGENT"
TARGET = (
    "/subscriptions/25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6"
    "/resourceGroups/rg_techdemo_Atiya_Tabsum_Shaik"
    "/providers/Microsoft.Web/sites/app-governance-validator-atiya-1026"
)
IDENTITY = "600447fe-5fea-4801-9033-ab4aafc474cc"
RELEASE = "1.2-ca5df7c1dc19e525"
AAD = b"gpv-webjobs-diagnostic-recovery-v1"
REPO = Path(__file__).resolve().parents[1]
SAFE_CODES = frozenset({
    "DEADLINE_EXPIRED", "TARGET_IDENTITY_MISMATCH", "TRANSIENT_HTTP",
    "HEALTH_HTTP_FAILURE", "HEALTH_BODY_MISMATCH",
    "RELEASE_REVISION_OR_READINESS_MISMATCH", "CERTIFICATE_VERIFICATION_FAILED",
    "CURRENT_STARTUP_FAILURE", "CONSECUTIVE_PAIRS_NOT_ESTABLISHED",
    "CONFIGURATION_DRIFT", "ENABLEMENT_READBACK_DRIFT", "PRE_LISTING_DRIFT",
    "WEBJOBS_LISTING_NOT_EMPTY_SUCCESS", "FLAG_CHANGED_BY_OTHER_OPERATOR",
    "NO_DIAGNOSTIC_MUTATION_INTENT", "FLAG_RESTORATION_UNVERIFIED",
    "POST_RESTORATION_DRIFT", "CAS_FAILED",
    "AZURE_CLI_AUTH_FAILURE", "AZURE_ACCOUNT_MISMATCH", "AZURE_TOKEN_IDENTITY_MISMATCH",
    "ENDPOINT_NOT_AUTHORIZED", "RESPONSE_TOO_LARGE", "AZURE_HTTP_FAILURE",
    "INVALID_AZURE_RESPONSE", "SETTINGS_RESOURCE_MISMATCH", "CONDITIONAL_WRITE_UNVERIFIED",
    "STRONG_ETAG_REQUIRED", "UNRELATED_CHANGE_FORBIDDEN", "LISTING_ALREADY_ATTEMPTED",
    "INVALID_OPERATION_ID", "RECOVERY_KEY_UNAVAILABLE", "INDEPENDENT_SUPERVISOR_UNVERIFIED",
    "LIVE_APPROVAL_AND_SUPERVISOR_REQUIRED", "INVALID_AUTHORIZATION", "EXISTING_STATE_RECOVER_ONLY",
})


class SafetyError(Exception):
    """Fixed-code failure; never include configuration or raw network text."""


class Expired(SafetyError):
    pass


class Drift(SafetyError):
    pass


class NotReady(SafetyError):
    pass


@dataclass(frozen=True)
class Snapshot:
    values: dict = field(repr=False)
    version: str


@dataclass(frozen=True)
class Response:
    status: int
    body: object


class Transport(Protocol):
    """All calls bounded; replace must provide real compare-and-swap semantics."""

    def identity(self, target, timeout): ...
    def settings(self, target, timeout) -> Snapshot: ...
    def replace(self, target, expected: Snapshot, desired: dict, timeout): ...
    def startup_lines(self, target, since, timeout) -> list[str]: ...
    def health(self, target, route, timeout) -> Response: ...
    def listing(self, target, timeout) -> Response: ...


class Clock:
    wall = staticmethod(time.time)
    mono = staticmethod(time.monotonic)
    sleep = staticmethod(time.sleep)


class Budget:
    """Absolute UTC plus monotonic cap; neither clock can extend a grant."""

    def __init__(self, clock, expires):
        self.clock, self.expires = clock, expires
        self.end_mono = clock.mono() + max(0, expires - clock.wall())

    def timeout(self, maximum=10):
        left = min(self.expires - self.clock.wall(), self.end_mono - self.clock.mono())
        if left <= 0:
            raise Expired("DEADLINE_EXPIRED")
        return min(maximum, left)

    def sleep(self, seconds):
        if self.timeout(seconds) < seconds:
            raise Expired("DEADLINE_EXPIRED")
        self.clock.sleep(seconds)
        self.timeout()

    def child(self, seconds):
        """A phase cannot reset/extend its parent's monotonic authorization."""
        phase = Budget(self.clock, min(self.expires, self.clock.wall() + seconds))
        phase.end_mono = min(phase.end_mono, self.end_mono)
        return phase


def sanitized(error):
    root = getattr(error, "reason", None) or error
    result = {
        "exception_type": type(error).__name__,
        "underlying_type": type(root).__name__,
        "errno": getattr(root, "errno", None),
        "tls_verify_code": getattr(root, "verify_code", None),
    }
    if isinstance(error, SafetyError) and error.args and error.args[0] in SAFE_CODES:
        result["code"] = error.args[0]
    if getattr(error, "route", None) in ("/health", "/ready"):
        result["route"] = error.route
    status = getattr(error, "http_status", None)
    if isinstance(status, int) and 100 <= status <= 599:
        result["http_status"] = status
    return result


def actual_startup(lines, since):
    """Only top-level, ordered current-container events count as completion."""
    from datetime import datetime

    started = probed = False
    for line in lines:
        match = re.fullmatch(r"(\d{4}-\d\d-\d\dT\S+Z)\s+(.*)", line)
        if not match:
            continue
        stamp = datetime.fromisoformat(match[1].replace("Z", "+00:00")).timestamp()
        if stamp < since:
            continue
        body = match[2]
        if re.fullmatch(r"Starting container: [\w-]+_app-governance-validator-atiya-1026\.", body):
            started, probed = True, False
        elif started and re.match(r"Site startup probe failed\b|Failed to start site\b", body):
            raise SafetyError("CURRENT_STARTUP_FAILURE")
        elif started and re.fullmatch(r"Site startup probe succeeded after [0-9.]+ seconds\.", body):
            probed = True
        elif started and probed and body == "Site started.":
            return True
    return False


class Journal:
    """Atomic encrypted state; wrapping key supplied by a durable secret store.

    The key must survive the initiating process. Never keep it only in memory or
    beside this file. An inaccessible key/journal is a recovery blocker.
    """

    def __init__(self, path, key):
        supplied = Path(path).absolute()
        for part in [supplied, *supplied.parents]:
            if part.is_symlink():
                raise SafetyError("SYMLINK_STATE_PATH")
        self.path = supplied.resolve()
        if self.path.is_relative_to(REPO):
            raise SafetyError("STATE_MUST_BE_OUTSIDE_REPOSITORY")
        if len(key) != 32:
            raise SafetyError("INVALID_JOURNAL_KEY")
        self.cipher = AESGCM(key)
        parent = self.path.parent
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        for part in [parent, *parent.parents]:
            if part.is_symlink():
                raise SafetyError("SYMLINK_STATE_PATH")
        info = parent.stat()
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise SafetyError("INSECURE_STATE_DIRECTORY")

    @contextmanager
    def lock(self):
        fd = os.open(str(self.path) + ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            os.close(fd)

    def load(self):
        fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
                raise SafetyError("INSECURE_STATE_FILE")
            raw = stream.read()
        try:
            value = json.loads(self.cipher.decrypt(raw[:12], raw[12:], AAD))
            if value["target"] != TARGET or value["flag"] != FLAG:
                raise ValueError()
            return value
        except Exception:
            raise SafetyError("INVALID_RECOVERY_JOURNAL") from None

    def save(self, value):
        nonce = secrets.token_bytes(12)
        raw = nonce + self.cipher.encrypt(nonce, json.dumps(value).encode(), AAD)
        temporary = self.path.with_name(self.path.name + "." + secrets.token_hex(8))
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)


class Diagnostic:
    def __init__(self, transport: Transport, journal: Journal, clock=None):
        self.io, self.journal, self.clock = transport, journal, clock or Clock()

    def _event(self, state, event, **details):
        state["audit"].append({"utc_epoch": self.clock.wall(), "event": event, **details})
        self.journal.save(state)

    def _call(self, budget, method, *args):
        # Every new request, including each member of a health pair, is guarded.
        return getattr(self.io, method)(TARGET, *args, timeout=budget.timeout())

    def _identity(self, budget):
        identity = self._call(budget, "identity")
        if identity != {"id": TARGET, "identity": IDENTITY, "runtime": "PYTHON|3.13"}:
            raise SafetyError("TARGET_IDENTITY_MISMATCH")

    def _pair(self, budget, expected):
        for route in ("/health", "/ready"):
            try:
                response = self._call(budget, "health", route)
            except OSError as error:
                error.route = route
                raise
            if response.status in (502, 503, 504):
                error = NotReady("TRANSIENT_HTTP")
                error.route, error.http_status = route, response.status
                raise error
            if response.status != 200:
                error = SafetyError("HEALTH_HTTP_FAILURE")
                error.route, error.http_status = route, response.status
                raise error
            body = response.body
            if route == "/health":
                if body != {"status": "ok"}:
                    raise SafetyError("HEALTH_BODY_MISMATCH")
            elif body != expected:
                raise SafetyError("RELEASE_REVISION_OR_READINESS_MISMATCH")
        budget.timeout()  # A response arriving after the deadline is not a pass.

    def _stable(self, state, budget, expected, phase):
        count = 0
        for attempt in range(10):
            try:
                self._pair(budget, expected)
                count += 1
                self._event(state, "HEALTH_PAIR", phase=phase, consecutive=count, attempt=attempt + 1)
                if count == 3:
                    return
            except (OSError, NotReady) as error:
                root = getattr(error, "reason", None) or error
                if isinstance(root, ssl.SSLCertVerificationError):
                    self._event(state, "CERTIFICATE_FAILURE", phase=phase, **sanitized(error))
                    raise SafetyError("CERTIFICATE_VERIFICATION_FAILED") from None
                count = 0
                self._event(state, "HEALTH_RESET", phase=phase, **sanitized(error))
            budget.sleep(10)
        raise NotReady("CONSECUTIVE_PAIRS_NOT_ESTABLISHED")

    def run(self, approved_at, expires):
        """A fresh explicitly approved run. Never resume diagnostics from state."""
        with self.journal.lock():
            if self.journal.path.exists():
                raise SafetyError("EXISTING_STATE_RECOVER_ONLY")
            if not all(math.isfinite(x) for x in (approved_at, expires)) or not 0 < expires - approved_at <= 900:
                raise SafetyError("INVALID_AUTHORIZATION")
            if self.clock.wall() < approved_at:
                raise SafetyError("AUTHORIZATION_NOT_STARTED")
            auth = Budget(self.clock, expires)
            auth.timeout()
            self._identity(auth)
            before = self._call(auth, "settings")
            if FLAG in before.values:
                raise SafetyError("UNEXPECTED_ORIGINAL_FLAG")
            expected = {"status": "ready", "release": RELEASE, "revision": "005"}
            self._pair(auth, expected)
            state = {
                "version": 1, "target": TARGET, "flag": FLAG,
                "approved_at": approved_at, "expires": expires,
                "original": before.values, "expected_health": expected,
                "intent": False, "listing_intent": False, "listing_status": None,
                "diagnostic_passed": False,
                "status": "PREPARED", "audit": [],
            }
            self.journal.save(state)
            # Independent read-back validates decryptability/durability before mutation.
            if self.journal.load() != state:
                raise SafetyError("RECOVERY_STATE_NOT_VERIFIED")
            try:
                current = self._call(auth, "settings")
                if current != before:
                    raise Drift("CONFIGURATION_DRIFT")
                state["intent"] = True
                state["changed_after"] = self.clock.wall()
                self._event(state, "MUTATION_INTENT")  # durable before even an ambiguous PUT
                phase = auth.child(300)
                self._call(phase, "replace", current, {**before.values, FLAG: "false"})
                enabled = self._call(phase, "settings")
                if enabled.values != {**before.values, FLAG: "false"}:
                    raise Drift("ENABLEMENT_READBACK_DRIFT")
                while True:
                    try:
                        lines = self._call(phase, "startup_lines", state["changed_after"])
                        if actual_startup(lines, state["changed_after"]):
                            self._event(state, "ACTUAL_STARTUP_COMPLETE")
                            break
                    except OSError as error:
                        self._event(state, "STARTUP_NETWORK_FAILURE", **sanitized(error))
                    phase.sleep(5)
                self._stable(state, phase, expected, "diagnostic")
                enabled = self._call(phase, "settings")
                if enabled.values != {**before.values, FLAG: "false"}:
                    raise Drift("PRE_LISTING_DRIFT")
                auth.timeout()
                phase.timeout()
                state["listing_intent"] = True
                self._event(state, "ONE_LISTING_INTENT")
                # Persist intent first; timeout/crash never permits a second request.
                response = self._call(phase, "listing")
                state["listing_status"] = response.status
                if response.status != 200 or response.body != []:
                    raise SafetyError("WEBJOBS_LISTING_NOT_EMPTY_SUCCESS")
                state["diagnostic_passed"] = True
                self._event(state, "LISTING_SUCCEEDED")
            except Exception as error:
                try:
                    auth.timeout()
                except Expired:
                    state["authorization_expired"] = True
                self._event(state, "DIAGNOSTIC_FAILED", **sanitized(error))
            finally:
                # No authorization check here. Cleanup has a fresh bounded work
                # budget, not a fresh grant to run diagnostics or list WebJobs.
                restored = self._restore(state)
            return restored

    def recover(self):
        """Fresh-process cleanup only, even if authorization expired years ago."""
        with self.journal.lock():
            return self._restore(self.journal.load())

    def _restore(self, state):
        # Validate the scope even when called with in-memory run state.
        if state["target"] != TARGET or state["flag"] != FLAG or FLAG in state["original"]:
            raise SafetyError("INVALID_RESTORATION_SCOPE")
        cleanup = Budget(self.clock, self.clock.wall() + 240)
        overdue = self.clock.wall() >= state["expires"] or state.get("authorization_expired", False)
        state["cleanup_overdue"] = overdue

        def audit(event, **details):
            # A full disk must not block an already authorized restoration.
            # Keep the last durable intent usable; report lost audit persistence.
            try:
                self._event(state, event, **details)
            except OSError:
                state["audit_persistence_failed"] = True

        try:
            audit("RESTORATION_STARTED", overdue=overdue)
            self._identity(cleanup)
            baseline = state["original"]
            for attempt in range(3):
                current = self._call(cleanup, "settings")
                others = {k: v for k, v in current.values.items() if k != FLAG}
                state["unrelated_drift"] = others != baseline
                if FLAG not in current.values:
                    break
                if current.values[FLAG] != "false":
                    raise Drift("FLAG_CHANGED_BY_OTHER_OPERATOR")
                if not state["intent"]:
                    raise Drift("NO_DIAGNOSTIC_MUTATION_INTENT")
                # Preserve concurrent unrelated changes; restore only our flag.
                try:
                    self._call(cleanup, "replace", current, others)
                except (OSError, Drift) as error:
                    audit("RESTORE_WRITE_UNCERTAIN", attempt=attempt + 1, **sanitized(error))
                    continue  # Re-read; never replay an old whole-map snapshot.
                break
            verify = self._call(cleanup, "settings")
            if FLAG in verify.values:
                raise SafetyError("FLAG_RESTORATION_UNVERIFIED")
            state["flag_restored"] = True
            state["unrelated_drift"] = verify.values != baseline
            self._stable(state, cleanup, state["expected_health"], "cleanup")
            final = self._call(cleanup, "settings")
            if final.values != verify.values:
                raise Drift("POST_RESTORATION_DRIFT")
            state["health_verified"] = True
            state["status"] = "RESTORED_WITH_DRIFT" if state["unrelated_drift"] else "RESTORED"
            if overdue:
                state["overall"] = "BLOCKED_WINDOW_EXCEEDED"
            else:
                state["overall"] = "PASS" if state.get("diagnostic_passed") and not state["unrelated_drift"] else "PARTIAL"
            audit("RESTORATION_VERIFIED", overdue=overdue, drift=state["unrelated_drift"])
        except Exception as error:
            state["status"] = "BLOCKED_RESTORATION_UNVERIFIED"
            state["overall"] = "BLOCKED"
            audit("RESTORATION_FAILED", **sanitized(error))
        if state.get("audit_persistence_failed"):
            state["overall"] = "BLOCKED_AUDIT_PERSISTENCE"
        return {
            key: state.get(key) for key in
            ("status", "overall", "cleanup_overdue", "flag_restored", "health_verified", "unrelated_drift", "listing_status", "audit_persistence_failed")
        }
