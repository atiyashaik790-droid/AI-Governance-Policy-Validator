"""Local developer Azure SQL connections: pinned Entra identity, TLS and fresh tokens."""

import base64
import binascii
import importlib
import json
import re
import struct
import time
from collections.abc import Callable
from typing import Any
from uuid import UUID

from azure.core.credentials import TokenCredential
from azure.identity import AzureCliCredential, ManagedIdentityCredential
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, URL
from sqlalchemy.exc import SQLAlchemyError

SQL_SCOPE = "https://database.windows.net/.default"
SQL_COPT_SS_ACCESS_TOKEN = 1256
ODBC_DRIVER = "ODBC Driver 18 for SQL Server"


class DatabaseConfigurationError(SQLAlchemyError):
    """An invalid or unavailable database prerequisite, with no sensitive values."""


class DatabaseAuthenticationError(SQLAlchemyError):
    """Missing, expired or mismatched organizational identity; never contains tokens."""


class DatabaseConnectionError(SQLAlchemyError):
    """Sanitized transport failure; never falls back to a different database."""


# Require explicit directory identifiers rather than choosing a cached account implicitly.
def validate_identity_ids(tenant_id: str, user_object_id: str) -> tuple[str, str]:
    try:
        return str(UUID(tenant_id)), str(UUID(user_object_id))
    except (ValueError, TypeError, AttributeError):
        raise DatabaseConfigurationError("Azure SQL requires valid AZURE_SQL_TENANT_ID and AZURE_SQL_USER_OBJECT_ID UUIDs") from None


# Construct a secret-free, injection-resistant ODBC string; reject conflicting options.
def build_azure_sql_url(database_url: URL) -> URL:
    if database_url.drivername != "mssql+pyodbc":
        raise DatabaseConfigurationError("Azure SQL requires the mssql+pyodbc dialect")
    if database_url.username or database_url.password:
        raise DatabaseConfigurationError("Azure SQL token mode does not accept URL usernames or passwords")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*\.database\.windows\.net", database_url.host or "", re.I):
        raise DatabaseConfigurationError("Azure SQL requires a commercial Azure SQL server FQDN")
    if database_url.port not in (None, 1433) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", database_url.database or ""):
        raise DatabaseConfigurationError("Azure SQL requires port 1433 and a valid database name")
    allowed = {"driver", "encrypt", "trustservercertificate"}
    normalized = {}
    for name, value in database_url.query.items():
        key = name.lower()
        if key not in allowed or key in normalized or not isinstance(value, str):
            raise DatabaseConfigurationError("Unsupported or duplicate Azure SQL URL option; raw ODBC/authentication options are forbidden")
        normalized[key] = value
    if normalized.get("driver", ODBC_DRIVER) != ODBC_DRIVER:
        raise DatabaseConfigurationError("Azure SQL requires Microsoft ODBC Driver 18 for SQL Server")
    if normalized.get("encrypt", "yes").lower() not in ("yes", "true", "mandatory"):
        raise DatabaseConfigurationError("Azure SQL requires encrypted connections")
    if normalized.get("trustservercertificate", "no").lower() not in ("no", "false"):
        raise DatabaseConfigurationError("Azure SQL requires certificate validation")
    connection_string = (
        f"Driver={{{ODBC_DRIVER}}};Server=tcp:{database_url.host},1433;Database={database_url.database};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=10;LongAsMax=Yes"
    )
    return URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})


# Check the trusted SDK token's account binding; Azure SQL still verifies its signature.
def verify_token_identity(token: str, expires_on: int, tenant_id: str, user_object_id: str) -> None:
    try:
        payload = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        identity_matches = str(UUID(claims["tid"])) == tenant_id and str(UUID(claims["oid"])) == user_object_id
        if not identity_matches or expires_on <= time.time() + 60:
            raise ValueError("Wrong identity or insufficient token lifetime")
    except (ValueError, KeyError, IndexError, TypeError, AttributeError, binascii.Error):
        raise DatabaseAuthenticationError(
            "Azure SQL requires an unexpired token for the configured organizational tenant and user"
        ) from None


# Supply an independently obtained valid token for each newly created physical connection.
def install_token_provider(engine: Engine, credential: TokenCredential, tenant_id: str, user_object_id: str) -> Callable:
    # Acquire and encode the token immediately before the ODBC connection handshake.
    def connect_with_entra_token(dialect: Any, connection_record: Any, connection_args: list, connection_parameters: dict) -> Any:
        # SQLAlchemy may insert Trusted_Connection when a URL has no username.
        connection_args = list(connection_args)
        if connection_args and isinstance(connection_args[0], str):
            connection_args[0] = re.sub(r";Trusted_Connection=Yes(?=;|$)", "", connection_args[0], flags=re.I)
            if re.search(r"(?:^|;)(?:UID|PWD|Authentication|Trusted_Connection)\s*=", connection_args[0], re.I):
                raise DatabaseConfigurationError("Incompatible ODBC authentication parameters are forbidden in token mode")
        try:
            token = credential.get_token(SQL_SCOPE)
        except Exception:
            raise DatabaseAuthenticationError(
                "Azure SQL authentication unavailable; sign in to the approved organizational tenant"
            ) from None
        verify_token_identity(token.token, token.expires_on, tenant_id, user_object_id)
        encoded = token.token.encode("utf-16-le")
        connection_parameters["attrs_before"] = {SQL_COPT_SS_ACCESS_TOKEN: struct.pack(f"<I{len(encoded)}s", len(encoded), encoded)}
        try:
            return dialect.connect(*connection_args, **connection_parameters)
        except Exception:
            raise DatabaseConnectionError(
                "Azure SQL connection failed; verify driver, network, TLS and database identity permissions"
            ) from None

    event.listen(engine, "do_connect", connect_with_entra_token)
    return connect_with_entra_token


# Build the SQL engine without opening a connection or performing interactive login.
def create_azure_sql_engine(
    database_url: URL,
    tenant_id: str,
    user_object_id: str,
    credential: TokenCredential | None = None,
    auth_mode: str = "cli",
    query_timeout: int = 15,
) -> Engine:
    if auth_mode not in ("cli", "managed_identity"):
        raise DatabaseConfigurationError("Azure SQL authentication must be cli or managed_identity")
    tenant_id, user_object_id = validate_identity_ids(tenant_id, user_object_id)
    secure_url = build_azure_sql_url(database_url)
    try:
        pyodbc = importlib.import_module("pyodbc")
        if ODBC_DRIVER not in pyodbc.drivers():
            raise ImportError("Microsoft driver unavailable")
    except Exception:
        raise DatabaseConfigurationError(
            "Azure SQL requires unixODBC, libodbc.so.2, pyodbc and registered Microsoft ODBC Driver 18"
        ) from None
    # Use one pool owner; recycled/disposed SQLAlchemy connections must really close.
    pyodbc.pooling = False
    if credential is not None:
        azure_credential = credential
    elif auth_mode == "managed_identity":
        azure_credential = ManagedIdentityCredential()
    else:
        azure_credential = AzureCliCredential(tenant_id=tenant_id, process_timeout=15)
    engine = create_engine(
        secure_url,
        pool_pre_ping=True,
        pool_recycle=2700,
        pool_size=5,
        max_overflow=5,
        pool_timeout=10,
        hide_parameters=True,
        connect_args={"timeout": 10},
    )
    install_token_provider(engine, azure_credential, tenant_id, user_object_id)

    def set_query_timeout(connection, record):
        connection.timeout = query_timeout

    event.listen(engine, "connect", set_query_timeout, insert=True)
    return engine
