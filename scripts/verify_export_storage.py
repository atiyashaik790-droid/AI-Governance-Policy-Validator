"""Independently hash one existing ADLS export with an explicit CLI reader; no writes."""

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


def verify(account_url, filesystem, path, expected, tenant, maximum_bytes=5000000):
    from azure.core import MatchConditions
    from azure.identity import AzureCliCredential
    from azure.storage.filedatalake import DataLakeServiceClient

    host = urlsplit(account_url)
    if (
        host.scheme != "https"
        or not re.fullmatch(r"[a-z0-9]+\.dfs\.core\.windows\.net", host.netloc)
        or host.path not in ("", "/")
        or host.query
        or host.fragment
        or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", filesystem)
        or any(
            not re.fullmatch(r"[A-Za-z0-9_.-]+", p) or p in (".", "..")
            for p in path.split("/")
        )
        or not re.fullmatch(r"[a-fA-F0-9]{64}", expected)
        or not 1 <= maximum_bytes <= 20000000
    ):
        raise ValueError("Invalid explicit export verification target")
    report = {
        "time": datetime.now(timezone.utc).isoformat(),
        "scope": "READ_ONLY_EXACT_OBJECT",
        "identity": "Explicit Azure CLI reader; no writer identity fallback",
        "permissions_changed": False,
        "expected_sha256": expected.lower(),
    }
    try:
        with AzureCliCredential(tenant_id=tenant) as credential:
            with DataLakeServiceClient(
                account_url,
                credential=credential,
                retry_total=0,
                connection_timeout=10,
                read_timeout=20,
            ) as service:
                file = service.get_file_system_client(filesystem).get_file_client(path)
                properties = file.get_file_properties()
                if properties.size > maximum_bytes:
                    raise ValueError("Object exceeds verification byte limit")
                digest, size = hashlib.sha256(), 0
                for chunk in file.download_file(
                    etag=properties.etag, match_condition=MatchConditions.IfNotModified
                ).chunks():
                    size += len(chunk)
                    if size > maximum_bytes:
                        raise ValueError("Object exceeds verification byte limit")
                    digest.update(chunk)
                actual = digest.hexdigest()
                report.update(
                    status="PASS"
                    if actual == expected.lower() and size == properties.size
                    else "MISMATCH",
                    actual_sha256=actual,
                    bytes=size,
                )
    except Exception as error:
        report.update(
            status="UNVERIFIED",
            error_type=type(error).__name__,
            http_status=getattr(error, "status_code", None),
        )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("account-url", "filesystem", "path", "sha256", "tenant"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify(
        args.account_url, args.filesystem, args.path, args.sha256, args.tenant
    )
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
