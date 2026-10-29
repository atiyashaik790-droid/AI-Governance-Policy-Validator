"""Explicit database selection; SQLite is preserved and SQL failures never fall back."""

from collections.abc import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker
from .config import Settings, settings
from .azure_sql import DatabaseConfigurationError, create_azure_sql_engine


# Build a database engine shared by FastAPI, diagnostics and Alembic.
def create_database_engine(configuration: Settings) -> Engine:
    try:
        url = make_url(configuration.database_url)
    except Exception:
        raise DatabaseConfigurationError("Invalid DATABASE_URL; check the documented database configuration") from None
    if url.drivername == "mssql+pyodbc":
        return create_azure_sql_engine(url, configuration.azure_sql_tenant_id, configuration.azure_sql_user_object_id)
    if url.drivername not in ("sqlite", "sqlite+pysqlite"):
        raise DatabaseConfigurationError("Unsupported database; choose SQLite or Azure SQL with mssql+pyodbc")
    sqlite_engine = create_engine(url, pool_pre_ping=True, hide_parameters=True, connect_args={"check_same_thread": False})

    # Keep SQLite foreign-key checks enabled on every new connection.
    @event.listens_for(sqlite_engine, "connect")
    def enable_sqlite_foreign_keys(connection, record) -> None:
        connection.execute("PRAGMA foreign_keys=ON")

    return sqlite_engine


engine = create_database_engine(settings)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


# Commit successful requests and roll back failures in the selected database only.
def get_database() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
