"""Server-only, bounded attribution; never infer event-time identity from membership."""
from typing import Literal
from uuid import UUID
from pydantic import Field, field_validator
from .schemas import StrictModel


class ExecutionIdentity(StrictModel):
    actor: str = Field(min_length=1, max_length=80)
    tenant: str = Field(min_length=1, max_length=80)
    role: Literal["Admin", "User", "Developer", "Reviewer", "Auditor", "Policy Owner"]
    directory_tenant: str | None = None
    object_id: str | None = None

    @field_validator("directory_tenant", "object_id")
    @classmethod
    def valid_uuid(cls, value):
        return str(UUID(value)) if value is not None else None


def snapshot(user):
    return ExecutionIdentity(actor=user.user, tenant=user.tenant, role=user.role,
                             directory_tenant=user.directory_tenant, object_id=user.object_id).model_dump()


def recorded_identity(row, metadata):
    try:
        value = ExecutionIdentity.model_validate(metadata.get("execution_identity"))
        if value.actor != row.actor or value.tenant != row.tenant:
            return None
        return value.model_dump()
    except (ValueError, TypeError):
        return None
