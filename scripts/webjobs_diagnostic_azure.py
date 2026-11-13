"""Explicitly invoked Azure adapter. Importing this module does no I/O.

Writes fail closed without separately reviewed evidence that this exact ARM
operation enforces conditional updates. No ETag/If-Match support is assumed.
"""

import argparse
import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import secrets
import subprocess
import time
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from webjobs_diagnostic import (
    Diagnostic, Drift, FLAG, IDENTITY, Journal, Response,
    SafetyError, Snapshot, TARGET, sanitized,
)

SUB = "25ddf5d2-6e0b-4a34-82fc-bfc91415e7a6"
TENANT = "4ac50105-0c66-404e-a107-7cbd8a9a6442"
OPERATOR = "b5d8bfbe-f03a-4132-a13f-ab49aae834b7"
APP = "app-governance-validator-atiya-1026"
ARM = "https://management.azure.com"
WEB = f"https://{APP}.azurewebsites.net"
SCM = f"https://{APP}.scm.azurewebsites.net"
API = "2024-11-01"
QUERY = "?api-version=" + API
HASHES = {
    "frontend_sha256": "beb38c3485b8abfb672e5a2bf851f1f178c1a8049f367b450708e5abbe7581d4",
    "backend_sha256": "ad2e4af6c958f24e27e8838cccf8ca9dc46c76fb430c583d2c6737cd3034a813",
}


class Limit:
    def __init__(self, seconds, mono=time.monotonic, wall=time.time):
        if not math.isfinite(seconds) or seconds <= 0:
            raise TimeoutError()
        self.mono, self.end = mono, mono() + seconds
        self.wall, self.end_wall = wall, wall() + seconds

    def left(self):
        remaining = min(self.end - self.mono(), self.end_wall - self.wall())
        if remaining <= 0:
            raise TimeoutError()
        return remaining


class CliCredential:
    """No interactive login or account switching; secrets captured in memory."""

    def __init__(self, runner=subprocess.run, wall=time.time):
        self.runner, self.wall, self.cached = runner, wall, None

    def _az(self, args, limit):
        try:
            result = self.runner(["az", *args, "--only-show-errors", "-o", "json"],
                                 capture_output=True, text=True, timeout=limit.left())
            limit.left()
            if result.returncode:
                raise ValueError()
            return json.loads(result.stdout)
        except Exception:
            raise SafetyError("AZURE_CLI_AUTH_FAILURE") from None

    def token(self, limit):
        if self.cached and self.cached[1] > self.wall() + 120:
            return self.cached[0]
        account = self._az(["account", "show", "--subscription", SUB,
                            "--query", "{id:id,tenantId:tenantId,state:state}"], limit)
        if account != {"id": SUB, "tenantId": TENANT, "state": "Enabled"}:
            raise SafetyError("AZURE_ACCOUNT_MISMATCH")
        result = self._az(["account", "get-access-token", "--subscription", SUB,
                           "--tenant", TENANT, "--resource", ARM + "/"], limit)
        try:
            token = result["accessToken"]
            claims = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "==="))
            if (claims["tid"] != TENANT or claims["oid"] != OPERATOR
                    or claims["aud"] != ARM + "/" or claims["exp"] <= self.wall() + 60):
                raise ValueError()
            # CLI supplies the token; Azure verifies its signature, not this parser.
            self.cached = token, claims["exp"]
            return token
        except Exception:
            raise SafetyError("AZURE_TOKEN_IDENTITY_MISMATCH") from None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


@dataclass(frozen=True)
class ConditionalEvidence:
    target: str
    api_version: str
    verified: bool
    reference: str

    def permits(self):
        return self.target == TARGET and self.api_version == API and self.verified is True and bool(self.reference)


@dataclass
class HttpReply:
    status: int
    headers: dict = field(default_factory=dict)
    raw: bytes = field(default=b"", repr=False)


class AzureTransport:
    def __init__(self, credential, evidence=None, opener=None, mono=time.monotonic, wall=time.time):
        self.credential, self.evidence = credential, evidence
        self.opener = opener or build_opener(NoRedirect())
        self.mono, self.wall, self.listing_sent = mono, wall, False

    def _target(self, target):
        if target != TARGET:
            raise SafetyError("TARGET_IDENTITY_MISMATCH")

    def _request(self, base, path, limit, method="GET", payload=None, extra=None):
        # Strict endpoint allowlist: no job mutation, restart, SQL or deploy routes.
        arm_allowed = ((method == "GET" and path in (TARGET + QUERY, TARGET + "/config/web" + QUERY))
                       or (method == "POST" and path == TARGET + "/config/appsettings/list" + QUERY)
                       or (method == "PUT" and path == TARGET + "/config/appsettings" + QUERY))
        scm_allowed = method == "GET" and (path == "/api/continuouswebjobs" or path == "/api/vfs/LogFiles/"
                        or bool(re.fullmatch(r"/api/vfs/LogFiles/\d{4}_\d\d_\d\d_[A-Za-z0-9_.-]+_docker\.log", path)))
        if not ((base == ARM and arm_allowed) or (base == SCM and scm_allowed)
                or (base == WEB and method == "GET" and path in ("/health", "/ready"))):
            raise SafetyError("ENDPOINT_NOT_AUTHORIZED")
        headers = {}
        if base != WEB:
            headers["Authorization"] = "Bearer " + self.credential.token(limit)
        headers.update(extra or {})
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode()
        req = Request(base + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=limit.left()) as response:
                raw = response.read(3_000_001)
                if len(raw) > 3_000_000:
                    raise SafetyError("RESPONSE_TOO_LARGE")
                limit.left()
                return HttpReply(response.status, dict(response.headers), raw)
        except HTTPError as error:
            status = error.code
            error.close()  # Never expose error bodies/headers/settings in logs.
            return HttpReply(status)

    @staticmethod
    def _json(reply):
        if reply.status not in (200, 201, 206):
            raise SafetyError("AZURE_HTTP_FAILURE")
        try:
            return json.loads(reply.raw)
        except Exception:
            raise SafetyError("INVALID_AZURE_RESPONSE") from None

    def identity(self, target, timeout):
        self._target(target)
        limit = Limit(timeout, self.mono, self.wall)
        site = self._json(self._request(ARM, TARGET + QUERY, limit))
        config = self._json(self._request(ARM, TARGET + "/config/web" + QUERY, limit))["properties"]
        if (site.get("id", "").casefold() != TARGET.casefold()
                or site.get("name") != APP or site.get("identity", {}).get("principalId") != IDENTITY
                or site.get("properties", {}).get("defaultHostName") != APP + ".azurewebsites.net"
                or site.get("properties", {}).get("reserved") is not True
                or site.get("kind") != "app,linux"
                or config.get("linuxFxVersion") != "PYTHON|3.13"
                or config.get("alwaysOn") is not True or config.get("numberOfWorkers") != 1):
            raise SafetyError("TARGET_IDENTITY_MISMATCH")
        return {"id": TARGET, "identity": IDENTITY, "runtime": "PYTHON|3.13"}

    def _settings(self, limit):
        reply = self._request(ARM, TARGET + "/config/appsettings/list" + QUERY, limit, "POST")
        data = self._json(reply)
        if data.get("id", "").casefold() != (TARGET + "/config/appsettings").casefold():
            raise SafetyError("SETTINGS_RESOURCE_MISMATCH")
        values = data.get("properties")
        if not isinstance(values, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in values.items()):
            raise SafetyError("INVALID_AZURE_RESPONSE")
        version = next((v for k, v in reply.headers.items() if k.lower() == "etag"), "")
        return Snapshot(values, version)

    def settings(self, target, timeout):
        self._target(target)
        return self._settings(Limit(timeout, self.mono, self.wall))

    def replace(self, target, expected, desired, timeout):
        self._target(target)
        if not self.evidence or not self.evidence.permits():
            raise SafetyError("CONDITIONAL_WRITE_UNVERIFIED")
        if not re.fullmatch(r'"[^"\r\n]+"', expected.version):
            raise SafetyError("STRONG_ETAG_REQUIRED")
        before_other = {k: v for k, v in expected.values.items() if k != FLAG}
        after_other = {k: v for k, v in desired.items() if k != FLAG}
        enable = FLAG not in expected.values and desired.get(FLAG) == "false"
        restore = expected.values.get(FLAG) == "false" and FLAG not in desired
        if before_other != after_other or not (enable or restore):
            raise SafetyError("UNRELATED_CHANGE_FORBIDDEN")
        limit = Limit(timeout, self.mono, self.wall)
        if self._settings(limit) != expected:
            raise Drift("CAS_FAILED")
        reply = self._request(ARM, TARGET + "/config/appsettings" + QUERY, limit, "PUT",
                              {"properties": desired}, {"If-Match": expected.version})
        if reply.status in (409, 412):
            raise Drift("CAS_FAILED")
        if reply.status not in (200, 201):
            raise SafetyError("AZURE_HTTP_FAILURE")
        # A transport failure here is ambiguous; controller already persisted intent.
        if self._settings(limit).values != desired:
            raise Drift("ENABLEMENT_READBACK_DRIFT")

    def startup_lines(self, target, since, timeout):
        self._target(target)
        limit = Limit(timeout, self.mono, self.wall)
        entries = self._json(self._request(SCM, "/api/vfs/LogFiles/", limit))
        names = [v for v in entries if re.fullmatch(r"\d{4}_\d\d_\d\d_[A-Za-z0-9_.-]+_docker\.log", v.get("name", ""))]
        names = sorted(names, key=lambda v: v.get("mtime") or "", reverse=True)[:2]
        # Never stitch independent log streams into one synthetic startup sequence.
        for entry in names:
            reply = self._request(SCM, "/api/vfs/LogFiles/" + entry["name"], limit,
                                  extra={"Range": "bytes=-300000"})
            if reply.status in (200, 206):
                from webjobs_diagnostic import actual_startup
                lines = reply.raw.decode(errors="replace").splitlines()
                if actual_startup(lines, since):
                    return lines
        return []

    def health(self, target, route, timeout):
        self._target(target)
        reply = self._request(WEB, route, Limit(timeout, self.mono, self.wall))
        if reply.status != 200:
            return Response(reply.status, {})
        data = self._json(reply)
        if route == "/health":
            return Response(200, {"status": data.get("status")})
        release = data.get("release", {})
        if any(release.get(k) != v for k, v in HASHES.items()):
            raise SafetyError("RELEASE_REVISION_OR_READINESS_MISMATCH")
        return Response(200, {"status": data.get("status"), "release": release.get("build_version"),
                              "revision": data.get("database_revision")})

    def listing(self, target, timeout):
        self._target(target)
        if self.listing_sent:
            raise SafetyError("LISTING_ALREADY_ATTEMPTED")
        self.listing_sent = True  # no automatic retry after any ambiguous failure
        reply = self._request(SCM, "/api/continuouswebjobs", Limit(timeout, self.mono, self.wall))
        return Response(reply.status, self._json(reply) if reply.status == 200 else None)


class DesktopKeys:
    """Existing libsecret store; use system Python with GI. No fallback to files."""

    def __init__(self, backend=None):
        self.backend = backend

    def key(self, operation_id, create=False):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", operation_id):
            raise SafetyError("INVALID_OPERATION_ID")
        try:
            if self.backend is None:
                import gi
                gi.require_version("Secret", "1")
                from gi.repository import Secret
                self.backend = Secret
            secret = self.backend
            service = secret.Service.get_sync(secret.ServiceFlags.OPEN_SESSION | secret.ServiceFlags.LOAD_COLLECTIONS, None)
            collection = secret.Collection.for_alias_sync(service, secret.COLLECTION_DEFAULT, secret.CollectionFlags.NONE, None)
            if collection is None or collection.get_locked():
                raise ValueError()
            schema = secret.Schema.new("org.gpv.WebJobsDiagnosticRecovery", secret.SchemaFlags.NONE,
                                       {"operation_id": secret.SchemaAttributeType.STRING, "app": secret.SchemaAttributeType.STRING})
            attributes = {"operation_id": operation_id, "app": APP}
            value = secret.password_lookup_sync(schema, attributes, None)
            if value is None and create:
                value = base64.b64encode(secrets.token_bytes(32)).decode()
                if not secret.password_store_sync(schema, attributes, secret.COLLECTION_DEFAULT,
                                                  "GPV diagnostic recovery " + operation_id, value, None):
                    raise ValueError()
                if secret.password_lookup_sync(schema, attributes, None) != value:
                    raise ValueError()
            key = base64.b64decode(value, validate=True)
            if len(key) != 32:
                raise ValueError()
            return key
        except Exception:
            raise SafetyError("RECOVERY_KEY_UNAVAILABLE") from None


def require_supervisor(document, expires):
    required = ("verified", "different_host", "survives_initiator_termination", "survives_host_unavailability",
                "journal_access_verified", "key_access_verified", "azure_restore_access_verified")
    if (document.get("target") != TARGET or any(document.get(k) is not True for k in required)
            or not document.get("evidence_reference") or document.get("coverage_until", 0) < expires):
        raise SafetyError("INDEPENDENT_SUPERVISOR_UNVERIFIED")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Explicit approval required. Default writes are blocked.")
    parser.add_argument("mode", choices=("run", "recover"))
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--operation-id", required=True)
    parser.add_argument("--conditional-evidence", type=Path, required=True)
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--supervisor-evidence", type=Path)
    args = parser.parse_args(argv)
    try:
        proof = ConditionalEvidence(**json.loads(args.conditional_evidence.read_text()))
        if not proof.permits():
            raise SafetyError("CONDITIONAL_WRITE_UNVERIFIED")
        approval = None
        if args.mode == "run":
            if args.approval is None or args.supervisor_evidence is None:
                raise SafetyError("LIVE_APPROVAL_AND_SUPERVISOR_REQUIRED")
            approval = json.loads(args.approval.read_text())
            if (approval.get("target") != TARGET or approval.get("operation_id") != args.operation_id
                    or approval.get("scope") != "ONE_FLAG_ONE_LISTING_THEN_RESTORE"):
                raise SafetyError("INVALID_AUTHORIZATION")
            now = datetime.now(timezone.utc).timestamp()
            if not approval["approved_at"] <= now < approval["expires"] or not 0 < approval["expires"] - approval["approved_at"] <= 900:
                raise SafetyError("INVALID_AUTHORIZATION")
            require_supervisor(json.loads(args.supervisor_evidence.read_text()), approval["expires"])
            if args.journal.exists():
                raise SafetyError("EXISTING_STATE_RECOVER_ONLY")
        key = DesktopKeys().key(args.operation_id, create=args.mode == "run")
        controller = Diagnostic(AzureTransport(CliCredential(), proof), Journal(args.journal, key))
        result = controller.recover() if args.mode == "recover" else controller.run(approval["approved_at"], approval["expires"])
        print(json.dumps(result))  # Core result has no settings, headers or key values.
        success = result["status"] == "RESTORED" if args.mode == "recover" else result["overall"] == "PASS"
        return 0 if success else 1
    except Exception as error:
        print(json.dumps({"status": "BLOCKED", "error": sanitized(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
