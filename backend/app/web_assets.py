"""Opt-in production SPA hosting; existing API routes and authentication retain priority."""

import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.engine import make_url

from .config import Settings


def validate_hosting_settings(configuration: Settings) -> None:
    try:
        origin = urlsplit(configuration.cors_origin)
        accounts = json.loads(configuration.demo_accounts_json)
        roles = {"Admin", "Policy Owner", "Developer", "Reviewer", "Auditor"}
        valid_accounts = (
            isinstance(accounts, list)
            and bool(accounts)
            and all(
                isinstance(account, dict)
                and account.get("role") in roles
                and isinstance(account.get("user"), str)
                and 1 <= len(account["user"]) <= 80
                and isinstance(account.get("tenant"), str)
                and 1 <= len(account["tenant"]) <= 80
                and re.fullmatch(r"[a-f0-9]{64}", account.get("token_hash", ""))
                for account in accounts
            )
        )
        valid = (
            make_url(configuration.database_url).drivername == "mssql+pyodbc"
            and configuration.azure_sql_auth_mode == "managed_identity"
            and configuration.provider_mode == "live"
            and configuration.pii_mode == "presidio"
            and configuration.azure_sql_tenant_id
            and configuration.azure_sql_user_object_id
            and configuration.azure_openai_endpoint
            and configuration.azure_openai_deployment
            and configuration.openai_api_key
            and configuration.adls_account_url
            and configuration.adls_file_system
            and origin.scheme == "https"
            and origin.hostname
            and not origin.path
            and not origin.query
            and not origin.fragment
            and origin.username is None
            and valid_accounts
        )
        if not valid:
            raise ValueError
    except Exception:
        raise RuntimeError(
            "App Service requires reviewed live SQL managed identity, providers, HTTPS origin and hashed demo accounts"
        ) from None


def mount_frontend(application: FastAPI, directory: Path) -> None:
    directory = directory.resolve()
    if not (directory / "index.html").is_file() or not (directory / "assets").is_dir():
        raise RuntimeError("React production assets are missing; build the deployment package first")
    application.mount("/assets", StaticFiles(directory=directory / "assets"), name="react-assets")
    spa_roots = {"policies", "simulator", "playground", "history", "reviews", "analytics", "reports", "settings"}

    @application.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if path and (path.split("/", 1)[0] not in spa_roots or any(part in (".", "..") for part in path.split("/"))):
            raise HTTPException(404, "Not found")
        return FileResponse(directory / "index.html", headers={"Cache-Control": "no-cache"})
