"""Explicit, gated provider verification; tenant-scoped immutable audit evidence."""
import asyncio
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select

from . import providers
from .config import settings
from .models import Audit
from .schemas import StrictModel
from .security import require_role
from .usage import claim_action

Integration = Literal["azure_generation", "moderation", "adls"]
NAMES = ("azure_generation", "moderation", "adls")


class VerificationRequest(StrictModel):
    confirm_billable_operation: Literal[True]


def utc_now():
    return datetime.now(timezone.utc)


def configuration(name):
    values = {
        "azure_generation": (settings.azure_openai_endpoint, settings.azure_openai_deployment,
                             settings.azure_openai_api_version, settings.azure_openai_api_key),
        "moderation": (settings.openai_api_key,),
        "adls": (settings.adls_account_url, settings.adls_file_system),
    }[name]
    required = values[:2] if name != "moderation" else values
    # Azure generation/ADLS can use the existing managed identity without a key.
    identity = [os.getenv(key, "") for key in ("AZURE_CLIENT_ID", "AZURE_TENANT_ID", "AZURE_CLIENT_SECRET")]
    fingerprint = hashlib.sha256(json.dumps([name, *values, *identity], separators=(",", ":")).encode()).hexdigest()
    return all(value.strip() for value in required), fingerprint


def status(db, user, name):
    configured, fingerprint = configuration(name)
    base = {"status": "NOT_CONFIGURED" if not configured else "CONFIGURED_NOT_VERIFIED",
            "last_verification_at": None, "error_code": None,
            "freshness_hours": settings.integration_verification_freshness_hours,
            "verification_enabled": settings.integration_verification_enabled and settings.provider_mode == "live"}
    if not configured:
        return base
    actions = [f"integration.{name}.{value}" for value in ("VERIFIED", "FAILED")]
    row = db.scalar(select(Audit).where(Audit.tenant == user.tenant, Audit.action.in_(actions),
                                        Audit.resource.startswith(fingerprint))
                    .order_by(Audit.created.desc(), Audit.id.desc()).limit(1))
    if row is None:
        return base
    try:
        checked = datetime.fromisoformat(row.created)
        if checked.tzinfo is None or checked > utc_now():
            return base
    except ValueError:
        return base
    base["last_verification_at"] = row.created
    if row.action.endswith(".FAILED"):
        base.update(status="FAILED", error_code="VERIFICATION_FAILED")
    else:
        base["status"] = "VERIFIED" if utc_now() - checked <= timedelta(hours=settings.integration_verification_freshness_hours) else "STALE"
    return base


def statuses(db, user):
    return {name: status(db, user, name) for name in NAMES}


async def verify(db, user, name):
    require_role(user, "Admin")
    if not settings.integration_verification_enabled or settings.provider_mode != "live":
        raise HTTPException(403, "Real verification requires separately approved server enablement")
    configured, fingerprint = configuration(name)
    if not configured:
        raise HTTPException(409, "Integration is not configured")
    claim_action(db, user, "integration.verify", 1)
    object_path = f"governance-reports/integration/{uuid4()}.json" if name == "adls" else None
    db.add(Audit(tenant=user.tenant, actor=user.user, actor_role=user.role, action=f"integration.{name}.ATTEMPT", resource=fingerprint))
    if object_path:
        db.add(Audit(tenant=user.tenant, actor=user.user, actor_role=user.role, action="integration.adls.OBJECT", resource=object_path))
    db.commit()  # Shared rate limit and attempt survive provider/worker failure.
    outcome = "FAILED"
    try:
        if name == "azure_generation":
            answer = await providers.generate_ai_response("Synthetic integration check. Reply with OK.")
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError()
        elif name == "moderation":
            result = await providers.moderate_user_prompt("Synthetic integration check: hello.")
            if not isinstance(result, list):
                raise ValueError()
        else:
            content = '{"verification":"synthetic"}'
            await asyncio.to_thread(providers.upload_report, object_path, content)
            digest = await asyncio.to_thread(providers.report_digest, object_path, len(content.encode()))
            if digest != hashlib.sha256(content.encode()).hexdigest():
                raise ValueError()
        outcome = "VERIFIED"
    except Exception:
        # No exception messages, bodies, provider URLs, credentials or prompts.
        pass
    db.add(Audit(tenant=user.tenant, actor=user.user, actor_role=user.role, action=f"integration.{name}.{outcome}",
                 resource=fingerprint, created=utc_now().isoformat()))
    db.commit()
    return status(db, user, name)
