"""Create a local allowlisted App Service ZIP; never contacts Azure or includes .env/data."""

import argparse
import hashlib
import json
import re
import subprocess
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def package(root: Path, frontend: Path, output: Path) -> dict:
    if not (frontend / "index.html").is_file() or not (frontend / "assets").is_dir():
        raise ValueError("Build the React production frontend first")
    html = (frontend / "index.html").read_text()
    if 'src="/assets/' not in html:
        raise ValueError("React assets must use the same-origin /assets path")
    files = {
        "requirements.txt": root / "backend/requirements.lock.txt",
        "startup.sh": root / "deployment/startup.sh",
    }
    for path in (root / "backend/app").glob("*.py"):
        files["app/" + path.name] = path
    files["static/index.html"] = frontend / "index.html"
    for path in (frontend / "assets").iterdir():
        if (
            path.is_symlink()
            or not path.is_file()
            or not re.fullmatch(
                r"[A-Za-z0-9_-]+\.(js|css|woff2?|png|svg|ico)", path.name
            )
        ):
            raise ValueError("Unexpected frontend asset; refusing deployment package")
        if path.suffix == ".js" and b"localhost:8000" in path.read_bytes():
            raise ValueError(
                "Rebuild with VITE_API_URL=/ so browser API calls remain same-origin"
            )
        files["static/assets/" + path.name] = path
    for path in files.values():
        if path.is_symlink() or not path.is_file():
            raise ValueError("Deployment sources must be regular files")
    hashes = {
        name: hashlib.sha256(path.read_bytes()).hexdigest()
        for name, path in sorted(files.items())
    }
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unavailable"
    release = {
        "git_commit": commit,
        "build_version": "1.2-"
        + hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()[:16],
        "built_utc": datetime.now(UTC).isoformat(),
        "required_migration": "004",
        "frontend_sha256": hashlib.sha256(
            json.dumps(
                {
                    key: value
                    for key, value in hashes.items()
                    if key.startswith("static/")
                },
                sort_keys=True,
            ).encode()
        ).hexdigest(),
        "backend_sha256": hashlib.sha256(
            json.dumps(
                {key: value for key, value in hashes.items() if key.startswith("app/")},
                sort_keys=True,
            ).encode()
        ).hexdigest(),
    }
    with (
        output.open("xb") as stream,
        zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive,
    ):
        archive.writestr("release.json", json.dumps(release, sort_keys=True))
        for name, path in sorted(files.items()):
            archive.write(path, name)
    return {
        "artifact": str(output),
        "files": sorted([*files, "release.json"]),
        "release": release,
        "member_sha256": hashes,
        "deployed": False,
        "secrets_or_databases_included": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend-dist", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(package(ROOT, args.frontend_dist, args.output), indent=2))


if __name__ == "__main__":
    main()
