"""Environment-only configuration; no credentials are returned by diagnostics."""

from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[2] / ".env", extra="ignore")
    database_url: str = "sqlite:///./governance.db"
    azure_sql_tenant_id: str = ""
    azure_sql_user_object_id: str = ""
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
