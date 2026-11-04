"""Build and smoke-test isolated fixture containers; never loads the operator's .env."""

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def run(output):
    report = {
        "time": datetime.now(timezone.utc).isoformat(),
        "mode": "ISOLATED_DOCKER_FIXTURE",
        "checks": [],
    }
    if not shutil.which("docker"):
        report.update(status="BLOCKED", reason="Docker executable unavailable")
        output.write_text(json.dumps(report, indent=2) + "\n")
        return 1
    project = "governance-smoke-" + secrets.token_hex(6)
    with tempfile.TemporaryDirectory(prefix=project) as temporary:
        directory = Path(temporary)
        token = secrets.token_urlsafe(32)
        account = {
            "user": "docker-smoke",
            "tenant": project,
            "role": "Admin",
            "token_hash": hashlib.sha256(token.encode()).hexdigest(),
        }
        compose = {
            "services": {
                "backend": {
                    "build": str(ROOT / "backend"),
                    "environment": {
                        "DATABASE_URL": "sqlite:////data/governance.db",
                        "PROVIDER_MODE": "fixture",
                        "PII_MODE": "presidio",
                        "DEMO_ACCOUNTS_JSON": json.dumps([account]),
                        "ALLOW_LEGACY_API_CREDENTIALS": "false",
                        "CORS_ORIGIN": "http://localhost",
                        "AZURE_OPENAI_ENDPOINT": "",
                        "OPENAI_API_KEY": "",
                        "AZURE_OPENAI_API_KEY": "",
                        "ADLS_ACCOUNT_URL": "",
                        "ADLS_FILE_SYSTEM": "",
                    },
                    "volumes": ["smoke-data:/data"],
                    "healthcheck": {
                        "test": [
                            "CMD",
                            "python",
                            "-c",
                            "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready')",
                        ],
                        "interval": "5s",
                        "timeout": "5s",
                        "retries": 24,
                    },
                },
                "frontend": {
                    "build": str(ROOT / "frontend"),
                    "ports": ["127.0.0.1::8080"],
                    "depends_on": {"backend": {"condition": "service_healthy"}},
                    "healthcheck": {
                        "test": [
                            "CMD",
                            "wget",
                            "--quiet",
                            "--spider",
                            "http://127.0.0.1:8080/",
                        ],
                        "interval": "5s",
                        "timeout": "5s",
                        "retries": 24,
                    },
                },
            },
            "volumes": {"smoke-data": {}},
        }
        file = directory / "compose.json"
        file.write_text(json.dumps(compose))
        os.chmod(file, 0o600)
        # Compose's environment and project directory are private, without .env discovery.
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("COMPOSE_")
        }
        command = [
            "docker",
            "compose",
            "--project-directory",
            str(directory),
            "-p",
            project,
            "-f",
            str(file),
        ]

        def docker(*arguments, timeout=120):
            result = subprocess.run(
                [*command, *arguments],
                env=environment,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode:
                raise RuntimeError("Docker command failed: " + arguments[0])
            return result.stdout

        def check(name, condition):
            if not condition:
                raise RuntimeError("Check failed: " + name)
            report["checks"].append(name)

        try:
            docker("build", timeout=1800)
            check("Both production Dockerfiles built", True)
            docker("up", "-d", "--wait", "--wait-timeout", "180", timeout=240)
            check("Both containers healthy after migrations", True)
            address = docker("port", "frontend", "8080").strip()
            if not re.fullmatch(r"127\.0\.0\.1:\d+", address):
                raise RuntimeError("Unexpected container port binding")
            base = "http://" + address

            def request(path, method="GET", data=None, bearer=None):
                headers = {"Content-Type": "application/json"}
                if bearer:
                    headers["Authorization"] = "Bearer " + bearer
                body = json.dumps(data).encode() if data is not None else None
                req = Request(base + path, data=body, method=method, headers=headers)
                try:
                    with urlopen(req, timeout=120) as response:
                        content = response.read()
                        return response.status, json.loads(
                            content
                        ) if "application/json" in response.headers.get(
                            "Content-Type", ""
                        ) else content.decode()
                except HTTPError as error:
                    return error.code, None

            for route in ("/", "/policies", "/simulator"):
                status, html = request(route)
                check("Frontend route " + route, status == 200 and "/assets/" in html)
            asset = re.search(r'src="(/assets/[^\"]+\.js)"', html).group(1)
            check("Production JavaScript asset served", request(asset)[0] == 200)
            check(
                "Unauthenticated API denied through NGINX",
                request("/api/policies")[0] == 401,
            )
            status, session = request("/api/auth/session", "POST", bearer=token)
            check("Session exchange through NGINX", status == 201)
            bearer = session["access_token"]
            try:
                status, policy = request(
                    "/api/policies", "POST", {"name": "Docker smoke policy"}, bearer
                )
                check("Policy creation", status == 201)
                policy_id = policy["id"]
                check(
                    "Policy listing", request("/api/policies", bearer=bearer)[0] == 200
                )
                for operation in ("submit", "approve", "publish", "activate"):
                    check(
                        "Policy " + operation,
                        request(
                            f"/api/policies/{policy_id}/{operation}",
                            "POST",
                            bearer=bearer,
                        )[0]
                        == 200,
                    )
                status, result = request(
                    "/api/governance/generate",
                    "POST",
                    {"text": "Explain data governance."},
                    bearer,
                )
                check(
                    "Fixture generation and output gating",
                    status == 200
                    and result["decision"] == "ALLOW"
                    and bool(result["safe_response"]),
                )
                status, result = request(
                    "/api/governance/generate",
                    "POST",
                    {"text": "Contact demo@example.com"},
                    bearer,
                )
                check(
                    "Installed Presidio redaction",
                    status == 200
                    and result["input"]["decision"] == "REDACT"
                    and result["input"]["revalidated"],
                )
            finally:
                check(
                    "Session logout",
                    request("/api/auth/logout", "POST", bearer=bearer)[0] == 200,
                )
            check(
                "Revoked session denied",
                request("/api/policies", bearer=bearer)[0] == 401,
            )
            report["status"] = "PASS"
        except Exception as error:
            report.update(status="FAILED", error_type=type(error).__name__)
        finally:
            try:
                docker("down", "--volumes", "--remove-orphans")
                report["isolated_resources_removed"] = True
            except Exception:
                report.update(status="FAILED", isolated_resources_removed=False)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    raise SystemExit(run(parser.parse_args().output))
