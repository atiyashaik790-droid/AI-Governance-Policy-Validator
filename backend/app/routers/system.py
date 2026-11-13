"""Existing health, readiness, maintenance, capabilities and diagnostics handlers."""

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from ..config import settings
from ..dependencies import DB, USER
from ..security import Identity, require_role
from ..schema_compatibility import inspect_schema
from ..release import information as release_information

app_schema_revision = "011"


def health():
    return {"status": "ok"}


def ready(db: Session = DB):
    contract = inspect_schema(db, require_sso=settings.sso_enabled)
    if db.bind.dialect.name == "mssql" and contract["revision"] != app_schema_revision:
        raise HTTPException(503, "Application database migration is required")
    from ..protected_reviews import ensure_ready
    ensure_ready(db)
    if settings.sso_enabled:
        from ..sso import configuration

        configuration()
    return {
        "status": "ready",
        "provider_mode": settings.provider_mode,
        "release": release_information(),
        "database_revision": contract["revision"],
        "schema_versioned": contract["versioned"],
        "sso_available": settings.sso_enabled and contract["sso_schema"],
    }


def maintenance_status(db: Session = DB, user: Identity = USER):
    require_role(user, "Admin")
    from ..maintenance import plan

    return plan(db, user.tenant)


def capabilities(user: Identity = USER):
    from typing import get_args
    from ..schemas import PIIEntity, ModerationCategory
    from ..engine import get_pii_analyzer

    available = {"EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "US_SSN"}
    detector_status = "AVAILABLE"
    if settings.pii_mode == "presidio":
        try:
            available.update(get_pii_analyzer().get_supported_entities(language="en"))
        except Exception:
            detector_status = "UNAVAILABLE"
            available.clear()
    catalog = list(get_args(PIIEntity))
    return {
        "pii_entities": catalog,
        "available_pii_entities": sorted(available.intersection(catalog)),
        "pii_status": detector_status,
        "pii_mode": settings.pii_mode,
        "moderation_categories": list(get_args(ModerationCategory)),
    }


def diagnostics(db: Session = DB, user: Identity = USER):
    from ..integration_verification import statuses
    integrations = statuses(db, user)
    db.execute(text("SELECT 1"))
    return {
        "authentication": "Microsoft Entra OIDC with server-side browser sessions"
        if settings.sso_enabled
        else "Expiring restricted demo sessions and provisioned demo credentials; not enterprise identity",
        "sso_enabled": settings.sso_enabled,
        "sso_session_minutes": settings.sso_session_minutes,
        "build_version": settings.build_version,
        "release": release_information(),
        "api_contract": "1.2",
        "required_migration": app_schema_revision,
        "migration_status": "READINESS_ENFORCED" if db.bind.dialect.name == "mssql" else "LOCAL_SCHEMA",
        "database_migration": db.execute(text("SELECT version_num FROM alembic_version")).scalar()
        if db.bind.dialect.name == "mssql"
        else "DISPOSABLE_OR_MANUALLY_VERSIONED_SQLITE",
        "demo_session_minutes": settings.demo_session_minutes,
        "demo_session_unlimited_local": settings.demo_session_unlimited_local and db.bind.dialect.name == "sqlite",
        "legacy_api_credentials": settings.allow_legacy_api_credentials,
        "retention_days": settings.retention_days,
        "database": db.bind.dialect.name,
        "database_status": "CONNECTED",
        "provider_mode": settings.provider_mode,
        "pii_mode": settings.pii_mode,
        "azure_generation": integrations["azure_generation"]["status"],
        "moderation": integrations["moderation"]["status"],
        "adls": integrations["adls"]["status"],
        "integrations": integrations,
        "role": user.role,
        "tenant": user.tenant,
    }
