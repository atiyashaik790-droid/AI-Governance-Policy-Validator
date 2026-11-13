"""Local-only release ZIP verification; all database paths are created in a temporary directory."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts/phase6a-2026-11-06"
EVIDENCE = ROOT / "docs/evidence/phase6a-local-2026-11-06"


def run():
    specification = json.loads((ARTIFACTS / "artifacts.json").read_text())
    result = {"scope": "local extracted production assets, SQLite SQL transport, synthetic OIDC/keys and fixture providers",
              "checks": [], "deployed": False}
    with tempfile.TemporaryDirectory(prefix="phase6a-artifacts-") as tmp:
        temporary = Path(tmp)
        extracts = {}
        manifest = json.loads((ARTIFACTS / "candidate-manifest.json").read_text())
        for name in ["candidate", "fallback"]:
            path = ROOT / specification[name]["path"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == specification[name]["sha256"]
            extracts[name] = temporary / name
            with zipfile.ZipFile(path) as archive:
                assert archive.testzip() is None
                assert set(archive.namelist()) == set(manifest["files"])
                for member in archive.namelist():
                    assert not Path(member).is_absolute() and ".." not in Path(member).parts
                for member, digest in manifest["member_sha256"].items():
                    assert hashlib.sha256(archive.read(member)).hexdigest() == digest
                archive.extractall(extracts[name])
        result["package_integrity"] = "PASS: exact allowlist and member hashes for both ZIPs"
        def migrate(path, revision):
            subprocess.run([sys.executable, "-B", "-m", "alembic", "upgrade", revision], cwd=ROOT / "backend",
                           env={**os.environ, "DATABASE_URL": "sqlite:///" + str(path), "PROVIDER_MODE": "fixture", "PII_MODE": "regex"},
                           check=True, capture_output=True, timeout=60)
        def probe(name, path, revision, *options):
            completed = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/tests/phase6a_package_probe.py"),
                                        "--directory", str(extracts[name]), "--database", str(path), "--revision", revision, *options],
                                       cwd=temporary, capture_output=True, text=True, timeout=60)
            if completed.returncode:
                raise RuntimeError("Local package probe failed: " + completed.stderr[-3000:])
            observed = json.loads(completed.stdout.splitlines()[-1])
            assert observed["passed"]
            result["checks"].append({"artifact": name, **observed})
        for revision in ["004", "005", "006", "007"]:
            path = temporary / (revision + ".db")
            migrate(path, revision)
            probe("candidate", path, revision)
        def retained_snapshot(path):
            with sqlite3.connect(path) as connection:
                content = connection.execute("SELECT * FROM review_protected_content ORDER BY tenant,review_id").fetchall()
                audit = connection.execute("SELECT * FROM audit_events ORDER BY id").fetchall()
                assert content and audit
                return content, audit
        before = retained_snapshot(temporary / "007.db")
        probe("fallback", temporary / "007.db", "007", "--recovery", "--preserve-only")
        assert before == retained_snapshot(temporary / "007.db")
        result["retained_ciphertext_and_audit"] = "PASS: unchanged across separate extracted fallback process"
        path = temporary / "fallback-fresh.db"
        migrate(path, "007")
        probe("fallback", path, "007", "--recovery")
    result["status"] = "PASS"
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "artifact-verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    run()
