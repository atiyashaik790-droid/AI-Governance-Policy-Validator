"""Offline by default; approved HTTP runs retain committed synthetic records."""

import argparse
import fcntl
import hashlib
import json
import os
import re
import signal
import stat
import sys
import time
from collections import Counter
from pathlib import Path
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))


class SafetyStop(RuntimeError):
    pass


def require(condition):
    if not condition:
        raise SafetyStop("HTTP acceptance condition failed")


def canonical_id(value):
    require(type(value) is str and str(UUID(value)) == value)
    return value


def validate_manifest(manifest):
    run_id = canonical_id(manifest["run_id"])
    require(manifest["tenant"] == "http-sql-test-" + run_id)
    require("http_test" not in manifest and manifest.get("record_ids") == {})
    tokens = manifest["tokens"]
    require(
        all(
            type(tokens.get(role)) is str
            and re.fullmatch(r"[A-Za-z0-9_-]+", tokens[role])
            for role in ("Admin", "Developer", "Foreign Admin")
        )
    )
    require(len(set(tokens.values())) == len(tokens))
    return manifest


def demo_accounts(run_id, tokens):
    """Hash caller-supplied credentials; never generate or print credentials here."""
    tenant = "http-sql-test-" + canonical_id(run_id)
    return [
        {
            "user": "synthetic-" + role.lower().replace(" ", "-"),
            "tenant": tenant + "-foreign" if role == "Foreign Admin" else tenant,
            "role": "Admin" if role == "Foreign Admin" else role,
            "token_hash": hashlib.sha256(token.encode()).hexdigest(),
        }
        for role, token in tokens.items()
    ]


def create_manifest(path, run_id, tokens):
    """Future startup helper: accept caller credentials, persist privately, no output."""
    path = Path(path).absolute()
    require(path.resolve() == path and not path.is_relative_to(ROOT))
    manifest = validate_manifest(
        {
            "run_id": run_id,
            "tenant": "http-sql-test-" + canonical_id(run_id),
            "tokens": tokens,
            "record_ids": {},
        }
    )
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as output:
        os.fchmod(output.fileno(), 0o600)
        json.dump(manifest, output, indent=2)
        output.flush()
        os.fsync(output.fileno())
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


class ManifestStore:
    """One locked descriptor for reads and checkpoints; no path reopening race."""

    def __init__(self, path):
        self.path = Path(path).absolute()
        self.fd = None
        self.poisoned = False

    def __enter__(self):
        require(self.path.resolve() == self.path and not self.path.is_relative_to(ROOT))
        self.fd = os.open(self.path, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            self.check_file()
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return self
        except BaseException:
            os.close(self.fd)
            self.fd = None
            raise

    def check_file(self):
        require(self.path.resolve() == self.path and not self.path.is_relative_to(ROOT))
        info = os.fstat(self.fd)
        current = self.path.lstat()
        require(
            stat.S_ISREG(info.st_mode)
            and stat.S_IMODE(info.st_mode) == 0o600
            and info.st_uid == os.getuid()
            and info.st_nlink == 1
            and (info.st_dev, info.st_ino) == (current.st_dev, current.st_ino)
            and stat.S_ISREG(current.st_mode)
        )

    def load(self):
        self.check_file()
        with os.fdopen(os.dup(self.fd), "r") as source:
            source.seek(0)
            return validate_manifest(json.load(source))

    def save(self, manifest):
        require(not self.poisoned)
        try:
            self.check_file()
            content = json.dumps(manifest, indent=2).encode()
            os.lseek(self.fd, 0, os.SEEK_SET)
            remaining = memoryview(content)
            while remaining:
                written = os.write(self.fd, remaining)
                require(written > 0)
                remaining = remaining[written:]
            os.ftruncate(self.fd, len(content))
            os.fsync(self.fd)
            self.check_file()
        except BaseException:
            self.poisoned = True
            raise

    def __exit__(self, *_):
        os.close(self.fd)
        self.fd = None


class VersionSnapshot(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    id: str
    policy_id: str
    tenant: str
    number: int = Field(gt=0)
    document: str
    created: str


def verify_version(row, api, tenant, policy_id, number, document):
    stored = VersionSnapshot.model_validate(dict(row))
    expected = VersionSnapshot.model_validate(api)
    for value in (stored.id, stored.policy_id, expected.id, expected.policy_id):
        canonical_id(value)
    require(
        stored == expected
        and stored.tenant == tenant
        and stored.policy_id == policy_id
        and stored.number == number
        and stored.document == document
    )


EXPECTED_COUNTS = dict(
    zip(
        (
            "policies",
            "policy_versions",
            "active_policy_assignments",
            "audit_events",
            "validation_executions",
            "human_review_cases",
            "feedback_records",
            "evaluation_exports",
        ),
        (1, 2, 1, 29, 7, 2, 2, 2),
        strict=True,
    )
)


def verify_retained(connection, manifest, models):
    """Explicit Core column projections, exact typed records and run-owned links."""
    from sqlalchemy import select

    evidence, tenant = manifest["http_test"], manifest["tenant"]
    expected = evidence["records"]
    require(set(expected) == set(EXPECTED_COUNTS))
    for model in models:
        name = model.__tablename__
        api_rows = expected[name]
        require(len(api_rows) == EXPECTED_COUNTS[name])
        rows = (
            connection.execute(
                select(*model.__table__.columns).where(model.tenant == tenant)
            )
            .mappings()
            .all()
        )
        require(len(rows) == EXPECTED_COUNTS[name])
        key = "tenant" if name == "active_policy_assignments" else "id"
        require(len({row[key] for row in api_rows}) == len(api_rows))
        by_id = {row[key]: row for row in api_rows}
        for row in rows:
            api = by_id[row[key]]
            require(
                row["tenant"] == tenant
                and api["tenant"] == tenant
                and set(row) == set(api)
            )
            require(
                all(
                    type(row[field]) is type(api[field]) and row[field] == api[field]
                    for field in row
                )
            )
            if name == "policy_versions":
                verify_version(
                    row,
                    api,
                    tenant,
                    evidence["policy_id"],
                    api["number"],
                    evidence["documents"][str(api["number"])],
                )
    policy = expected["policies"][0]
    require(
        policy["row_version"] == 10
        and policy["revision"] == 2
        and policy["status"] == "PUBLISHED"
        and policy["enabled"] == 1
        and policy["draft"] == evidence["documents"]["2"]
    )
    versions = expected["policy_versions"]
    require(
        policy["id"] == evidence["policy_id"]
        and policy["id"] in evidence["created"]["policies"]
    )
    require({v["number"] for v in versions} == {1, 2})
    require(
        expected["active_policy_assignments"]
        == [{"tenant": tenant, "version_id": versions[0]["id"]}]
    )
    require(
        versions[0]["number"] == 2
        and all(v["policy_id"] == policy["id"] for v in versions)
    )
    for name in (
        "validation_executions",
        "human_review_cases",
        "feedback_records",
        "evaluation_exports",
    ):
        require({r["id"] for r in expected[name]} == set(evidence["created"][name]))
    executions = {row["id"]: row for row in expected["validation_executions"]}
    require(
        all(
            row["policy_id"] == policy["id"]
            and row["version"] in (1, 2)
            and row["model"] == "local-fixture"
            for row in executions.values()
        )
    )
    require(
        sorted(row["version"] for row in executions.values()) == [1, 1, 1, 1, 1, 2, 2]
    )
    for row in executions.values():
        metadata = json.loads(row["metadata_json"])
        require(
            metadata["provider_mode"] == "fixture" and "safe_response" not in metadata
        )
        require(
            all(
                not metadata.get(stage) or "safe_text" not in metadata[stage]
                for stage in ("input", "output")
            )
        )
    require(
        all(
            {
                "policy_id": row["policy_id"],
                "policy_version": row["version"],
                "decision": row["decision"],
            }
            == evidence["execution_results"][row["id"]]
            for row in executions.values()
        )
    )
    reviews = expected["human_review_cases"]
    require(
        sorted((r["status"], r["row_version"]) for r in reviews)
        == [("APPROVED_RESUBMIT_REQUIRED", 2), ("REJECTED", 2)]
    )
    require(
        all(r["execution_id"] == evidence["review_links"][r["id"]] for r in reviews)
    )
    require(
        all(r["status"] == evidence["review_dispositions"][r["id"]] for r in reviews)
    )
    require(
        {r["execution_id"] for r in reviews}
        == {r["id"] for r in executions.values() if r["decision"] == "HUMAN_REVIEW"}
    )
    require(
        all(
            r["execution_id"] == evidence["feedback_execution"]
            for r in expected["feedback_records"]
        )
    )
    require(
        evidence["feedback_execution"] in executions
        and sorted(r["rating"] for r in expected["feedback_records"]) == [2, 3]
    )
    require(
        all(
            r["status"] == "FAILED"
            and r["path"].endswith(
                "/" + r["id"] + "." + evidence["export_formats"][r["id"]]
            )
            for r in expected["evaluation_exports"]
        )
    )
    owned = {
        identifier for values in evidence["created"].values() for identifier in values
    }
    require(
        all(
            row["resource"] in owned and row["actor"] == "synthetic-admin"
            for row in expected["audit_events"]
        )
    )
    require(all(row["actor"] == "synthetic-admin" for row in executions.values()))
    expected_audits = []
    for operation in evidence["operations"]:
        if operation.get("status") not in (200, 201) or operation["method"] not in (
            "POST",
            "PUT",
            "DELETE",
        ):
            continue
        parts = operation["path"].strip("/").split("/")
        if parts[1] == "policies":
            action = (
                "created"
                if len(parts) == 2
                else "draft_updated"
                if operation["method"] == "PUT"
                else "deleted"
                if operation["method"] == "DELETE"
                else "simulated"
                if parts[-1] == "simulate"
                else parts[-1]
            )
            expected_audits.append(
                (
                    "policy." + action,
                    operation.get("record_id") if len(parts) == 2 else parts[2],
                )
            )
        elif parts[1] == "governance":
            decision = evidence["execution_results"][operation["record_id"]]["decision"]
            expected_audits.append(
                ("governance." + parts[2] + "." + decision, operation["record_id"])
            )
        elif parts[1] == "reviews":
            expected_audits.append(("review." + parts[3], parts[2]))
        elif parts[1] == "feedback":
            expected_audits.append(("feedback.created", operation["record_id"]))
        elif parts[1] == "reports":
            expected_audits.append(("report.FAILED", operation["record_id"]))
    require(
        Counter(expected_audits)
        == Counter((row["action"], row["resource"]) for row in expected["audit_events"])
    )


class Driver:
    def __init__(self, client, manifest, checkpoint):
        self.client, self.manifest, self.checkpoint = client, manifest, checkpoint
        self.evidence = manifest["http_test"]
        self.evidence.setdefault(
            "created",
            {
                name: []
                for name in (
                    "policies",
                    "validation_executions",
                    "human_review_cases",
                    "feedback_records",
                    "evaluation_exports",
                )
            },
        )
        self.stopped = False

    def call(self, method, path, body=None, expected=200, role="Admin"):
        require(not self.stopped)
        try:
            operation = {"method": method, "path": path, "outcome": "UNKNOWN"}
            self.evidence["operations"].append(operation)
            self.checkpoint()  # Durable intent MUST precede transmission.
            response = self.client.request(
                method,
                path,
                json=body,
                headers={"Authorization": "Bearer " + self.manifest["tokens"][role]}
                if role
                else {"Authorization": ""},
            )
            operation.update(status=response.status_code, outcome="RECEIVED")
            self.checkpoint()
            require(response.status_code == expected)
            result = response.json()
            if method == "POST" and expected in (200, 201):
                table = {
                    "/api/policies": "policies",
                    "/api/feedback": "feedback_records",
                    "/api/reports/export": "evaluation_exports",
                }.get(path)
                if table:
                    require(result["tenant"] == self.manifest["tenant"])
                    self.remember(table, result["id"])
                if path.startswith("/api/governance/"):
                    self.remember("validation_executions", result["request_id"])
                    self.evidence.setdefault("execution_results", {})[
                        result["request_id"]
                    ] = {
                        field: result[field]
                        for field in ("policy_id", "policy_version", "decision")
                    }
                    if result.get("review_id"):
                        self.evidence.setdefault("review_links", {})[
                            result["review_id"]
                        ] = result["request_id"]
                        self.remember("human_review_cases", result["review_id"])
            if isinstance(result, dict):
                for field in ("id", "request_id", "review_id"):
                    if result.get(field):
                        identifier = canonical_id(result[field])
                        self.manifest.setdefault("record_ids", {}).setdefault(
                            field, []
                        ).append(identifier)
            if isinstance(result, dict):
                operation["record_id"] = result.get("request_id") or result.get("id")
            self.checkpoint()
            return result
        except BaseException:
            self.stopped = (
                True  # A caller cannot catch an error and continue mutations.
            )
            raise

    def remember(self, table, identifier):
        canonical_id(identifier)
        require(
            identifier
            not in {value for ids in self.evidence["created"].values() for value in ids}
        )
        self.evidence["created"][table].append(identifier)

    def workflows(self):
        from app.schemas import PolicyDocument

        call = self.call
        require(call("GET", "/health")["status"] == "ok")
        require(call("GET", "/ready")["status"] == "ready")
        diagnostics = call("GET", "/api/settings")
        require(
            all(
                diagnostics.get(key) == value
                for key, value in {
                    "database": "mssql",
                    "provider_mode": "fixture",
                    "pii_mode": "regex",
                    "adls": "BLOCKED",
                    "moderation": "BLOCKED",
                    "azure_generation": "BLOCKED",
                    "tenant": self.manifest["tenant"],
                    "role": "Admin",
                }.items()
            )
        )
        # Verify the actual server's token bindings before any HTTP mutation.
        for role, tenant, trusted_role in (
            ("Developer", self.manifest["tenant"], "Developer"),
            ("Foreign Admin", self.manifest["tenant"] + "-foreign", "Admin"),
        ):
            identity = call("GET", "/api/settings", role=role)
            require(identity["tenant"] == tenant and identity["role"] == trusted_role)
        call("GET", "/api/settings", expected=401, role=None)
        document = PolicyDocument(name="Synthetic HTTP SQL acceptance").model_dump()
        self.evidence["documents"] = {
            "1": PolicyDocument.model_validate(document).model_dump_json()
        }
        draft = call("POST", "/api/policies", document, 201)["id"]
        call("PUT", f"/api/policies/{draft}", document)
        call("DELETE", f"/api/policies/{draft}")
        call("GET", f"/api/policies/{draft}", expected=404)
        policy = call("POST", "/api/policies", document, 201)["id"]
        require(
            call(
                "POST",
                f"/api/policies/{policy}/simulate",
                {"text": "Synthetic safe text"},
            )["decision"]
            == "ALLOW"
        )

        def publish():
            for action in ("submit", "approve", "publish", "activate"):
                result = call("POST", f"/api/policies/{policy}/{action}")
                require(
                    result["row_version"]
                    == call("GET", f"/api/policies/{policy}")["row_version"]
                )

        publish()
        first = call("GET", f"/api/policies/{policy}/versions")[0]
        for endpoint, text, decision in (
            ("validate-input", "Synthetic safe text", "ALLOW"),
            ("validate-output", "Synthetic safe text", "ALLOW"),
            ("generate", "Synthetic safe text", "ALLOW"),
            ("generate", "api_key=sk-test-ABCDEFGHIJKLMNOPQRSTUVWXYZ12345", "BLOCK"),
            ("generate", "[OUTPUT_SECRET]", "BLOCK"),
        ):
            result = call("POST", "/api/governance/" + endpoint, {"text": text})
            require(
                result["decision"] == decision and result["provider_mode"] == "fixture"
            )
            if decision == "BLOCK":
                require(result["safe_response"] is None)
            elif endpoint == "generate":
                require(bool(result["safe_response"]))
        call("POST", f"/api/policies/{policy}/disable")
        call("POST", "/api/governance/generate", {"text": "Synthetic safe text"}, 409)
        call("POST", f"/api/policies/{policy}/enable")
        document["rules"]["blocked_keywords"]["action"] = "HUMAN_REVIEW"
        self.evidence["documents"]["2"] = PolicyDocument.model_validate(
            document
        ).model_dump_json()
        call("PUT", f"/api/policies/{policy}", document)
        publish()
        versions = call("GET", f"/api/policies/{policy}/versions")
        require(
            len(versions) == 2 and versions[1] == first and versions[0]["number"] == 2
        )
        self.evidence["versions"] = versions
        for action, status in (
            ("approve", "APPROVED_RESUBMIT_REQUIRED"),
            ("reject", "REJECTED"),
        ):
            held = call("POST", "/api/governance/generate", {"text": "internal-only"})
            require(
                held["decision"] == "HUMAN_REVIEW"
                and held["safe_response"] is None
                and held["model_invoked"] is False
            )
            path = f"/api/reviews/{held['review_id']}"
            require(call("GET", path)["status"] == "PENDING")
            resolved = call("POST", path + "/" + action)
            require(
                resolved["id"] == held["review_id"]
                and resolved["execution_id"] == held["request_id"]
            )
            require(resolved["status"] == status and resolved["row_version"] == 2)
            self.evidence.setdefault("review_dispositions", {})[held["review_id"]] = (
                status
            )
            require(call("GET", path)["row_version"] == 2)
            call("POST", path + "/" + action, expected=409)
        execution = self.manifest["record_ids"]["request_id"][0]
        self.evidence["feedback_execution"] = execution
        feedback_rows = []
        for rating in (2, 3):
            feedback_rows.append(
                call(
                    "POST",
                    "/api/feedback",
                    {"execution_id": execution, "rating": rating},
                    201,
                )
            )
        require(call("GET", "/api/feedback/summary") == {"count": 2, "average": 2.5})
        self.evidence["export_formats"] = {}
        for format in ("json", "csv"):
            exported = call("POST", "/api/reports/export", {"format": format}, 201)
            require(exported["status"] == "FAILED")
            self.evidence["export_formats"][exported["id"]] = format
        for endpoint, expected in (
            ("audit/executions", 7),
            ("reviews", 2),
            ("reports/exports", 2),
        ):
            require(len(call("GET", "/api/" + endpoint)) == expected)
        for endpoint in (
            "audit/summary",
            "analytics/overview",
            "analytics/violations",
            "analytics/compliance",
        ):
            require(call("GET", "/api/" + endpoint)["total_validations"] == 7)
        require(bool(call("GET", "/api/audit/events")))
        call("POST", "/api/policies", document, 403, role="Developer")
        call("GET", f"/api/policies/{policy}", expected=404, role="Foreign Admin")
        call(
            "GET",
            f"/api/reviews/{held['review_id']}",
            expected=404,
            role="Foreign Admin",
        )
        call(
            "POST",
            "/api/feedback",
            {"execution_id": execution, "rating": 3},
            404,
            role="Foreign Admin",
        )
        require(call("GET", "/api/policies", role="Foreign Admin") == [])
        self.evidence["policy_id"] = policy
        self.evidence["records"] = {
            "policies": [call("GET", f"/api/policies/{policy}")],
            "policy_versions": versions,
            "active_policy_assignments": [
                {"tenant": self.manifest["tenant"], "version_id": versions[0]["id"]}
            ],
            "feedback_records": feedback_rows,
        }
        for table, endpoint in (
            ("audit_events", "audit/events"),
            ("validation_executions", "audit/executions"),
            ("human_review_cases", "reviews"),
            ("evaluation_exports", "reports/exports"),
        ):
            self.evidence["records"][table] = call(
                "GET", "/api/" + endpoint + "?limit=100"
            )
        self.checkpoint()


def sql_check(manifest, before):
    # Reuse the reviewed schema preflight, never the standalone write exercise.
    from app.azure_sql import create_azure_sql_engine
    from app.config import settings
    from inventory_azure_sql import install_query_timeout
    from sqlalchemy import func, select
    from sqlalchemy.engine import URL, make_url
    from test_azure_sql_writes import (
        DATABASE,
        MODELS,
        SERVER,
        inventory_module,
        preflight,
    )

    require(make_url(settings.database_url).get_backend_name() == "sqlite")
    engine = create_azure_sql_engine(
        URL.create("mssql+pyodbc", host=SERVER, database=DATABASE),
        settings.azure_sql_tenant_id,
        settings.azure_sql_user_object_id,
    )
    install_query_timeout(engine, 5)
    try:
        with engine.connect() as connection:
            preflight(connection, inventory_module())
            counts = {
                model.__tablename__: connection.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.tenant == manifest["tenant"])
                )
                for model in MODELS
            }
            foreign_counts = {
                model.__tablename__: connection.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.tenant == manifest["tenant"] + "-foreign")
                )
                for model in MODELS
            }
            require(
                all(
                    type(value) is int and value == 0
                    for value in foreign_counts.values()
                )
            )
            if before:
                require(
                    all(type(value) is int and value == 0 for value in counts.values())
                )
            else:
                require(
                    counts == EXPECTED_COUNTS
                    and all(type(value) is int for value in counts.values())
                )
                verify_retained(connection, manifest, MODELS)
            return counts
    finally:
        engine.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-approved-http-test", action="store_true")
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args(argv)
    if not args.execute_approved_http_test:
        print(
            json.dumps(
                {
                    "mode": "OFFLINE_PLAN_ONLY",
                    "connection_attempted": False,
                    "writes_executed": False,
                    "target": "http://127.0.0.1:8001",
                    "retention": "COMMITTED_SYNTHETIC_HISTORY",
                    "timeout_seconds": 300,
                }
            )
        )
        return 0
    if args.manifest is None:
        parser.error("--manifest is required for an approved execution")
    manifest = None
    started = time.monotonic()

    def expired(*_):
        raise SafetyStop("Overall deadline exceeded")

    store = None
    failure_checkpoint = "NOT_ATTEMPTED"
    previous_cli_dir = os.environ.get("AZURE_CONFIG_DIR")
    previous_term = signal.signal(signal.SIGTERM, expired)
    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, 300)
    try:
        store = ManifestStore(args.manifest)
        store.__enter__()
        manifest = store.load()
        manifest["http_test"] = {
            "status": "INCOMPLETE",
            "operations": [],
            "retention": "COMMITTED_SYNTHETIC_HISTORY",
        }
        checkpoint = lambda: store.save(manifest)
        checkpoint()
        cache = ROOT / ".azure-sql-cli"
        require(cache.is_dir())
        os.environ["AZURE_CONFIG_DIR"] = str(cache)
        manifest["http_test"]["initial_counts"] = sql_check(manifest, before=True)
        with httpx.Client(
            base_url="http://127.0.0.1:8001",
            timeout=15,
            trust_env=False,
            follow_redirects=False,
            transport=httpx.HTTPTransport(retries=0, trust_env=False),
        ) as client:
            Driver(client, manifest, checkpoint).workflows()
        manifest["http_test"]["retained_counts"] = sql_check(manifest, before=False)
        manifest["http_test"]["status"] = "HTTP_SQL_TEST_PASSED"
        checkpoint()
        print(
            json.dumps(
                {
                    "status": "HTTP_SQL_TEST_PASSED",
                    "elapsed_seconds": round(time.monotonic() - started, 2),
                }
            )
        )
        return 0
    except (Exception, KeyboardInterrupt) as error:  # noqa: BLE001 - sanitize all transport/driver failures
        if manifest is not None:
            manifest["http_test"].update(
                status="FAILED_OR_INCOMPLETE", error_type=type(error).__name__
            )
            try:
                store.save(manifest)
                failure_checkpoint = "SAVED"
            except (Exception, KeyboardInterrupt):  # noqa: BLE001 - checkpoint failure stays fail-closed
                failure_checkpoint = "UNAVAILABLE"  # Stop; never retry HTTP.
        print(
            json.dumps(
                {
                    "status": "FAILED_OR_INCOMPLETE",
                    "error_type": type(error).__name__,
                    "failure_checkpoint": failure_checkpoint,
                    "recovery": "STOP; retain records and inspect exact tenant read-only; never retry",
                }
            )
        )
        return 2
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        if store is not None and store.fd is not None:
            store.__exit__()
        if previous_cli_dir is None:
            os.environ.pop("AZURE_CONFIG_DIR", None)
        else:
            os.environ["AZURE_CONFIG_DIR"] = previous_cli_dir
        signal.signal(signal.SIGALRM, previous)
        signal.signal(signal.SIGTERM, previous_term)


if __name__ == "__main__":
    raise SystemExit(main())
