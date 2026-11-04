"""Environment-only configuration; no credentials are returned by diagnostics."""

from pathlib import Path
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[2] / ".env", extra="ignore")
    session_per_minute: int = Field(default=10, ge=1, le=1000)
    export_per_minute: int = Field(default=10, ge=1, le=1000)
    allow_legacy_api_credentials: bool = False
    database_query_timeout: int = Field(default=15, ge=1, le=60)
    build_version: str = "working-tree"
    demo_session_minutes: int = Field(default=60, ge=5, le=480)
    inference_user_per_minute: int = Field(default=30, ge=1, le=10000)
    inference_tenant_per_minute: int = Field(default=100, ge=1, le=10000)
    inference_daily_quota: int = Field(default=500, ge=1, le=100000)
    inference_concurrency: int = Field(default=4, ge=1, le=100)
    inference_deadline: float = Field(default=90, ge=5, le=300)
    inference_warning_percent: int = Field(default=80, ge=1, le=100)
    export_max_records: int = Field(default=10000, ge=1, le=50000)
    export_max_bytes: int = Field(default=5000000, ge=1024, le=20000000)
    export_max_attempts: int = Field(default=3, ge=1, le=5)
    export_lease_seconds: int = Field(default=180, ge=60, le=900)
    retention_days: int = Field(default=365, ge=1, le=3650)
    database_url: str = "sqlite:///./governance.db"
    azure_sql_tenant_id: str = ""
    azure_sql_user_object_id: str = ""
    azure_sql_auth_mode: Literal["cli", "managed_identity"] = "cli"
    demo_accounts_json: str = "[]"
    provider_mode: Literal["live", "fixture"] = "live"
    pii_mode: Literal["presidio", "regex"] = "presidio"
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = ""
    azure_openai_api_version: str = "v1"
    azure_openai_api_key: str = ""
    openai_api_key: str = ""
    provider_timeout: float = 20
    adls_account_url: str = ""
    adls_file_system: str = ""
    cors_origin: str = "http://localhost:5173"


settings = Settings()
