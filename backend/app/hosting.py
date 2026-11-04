"""App Service ASGI entry point. Local CLI/SQLite entry point remains app.main:app."""

from pathlib import Path

from .config import settings
from .web_assets import mount_frontend, validate_hosting_settings

validate_hosting_settings(settings)

from .main import app  # noqa: E402 - Validate deployment settings before constructing the database engine.

mount_frontend(app, Path(__file__).resolve().parents[1] / "static")
