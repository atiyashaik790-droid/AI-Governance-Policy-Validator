"""Revision-specific inventories; 006 metadata never leaks into 005 queries."""

from functools import lru_cache
from sqlalchemy import MetaData
from .models import Base
from .models_multi_policy import MultiPolicyBase, MULTI_HISTORY, MULTI_TABLES

SSO_TABLES = frozenset({"sso_memberships", "sso_transactions", "sso_sessions"})
CATEGORY_TABLES = frozenset({"governance_categories", "policy_categories"})
LEGACY_HISTORY = ("audit_events", "policy_versions", "review_notes")


@lru_cache(maxsize=8)
def metadata_for_revision(revision):
    if revision in {"007", "008", "009", "010", "011"}:
        from .models_review_content import ReviewContentBase

        source = ReviewContentBase.metadata
    elif revision == "006":
        source = MultiPolicyBase.metadata
    elif revision in {"004", "005"}:
        source = Base.metadata
    else:
        raise ValueError("Unsupported schema revision")
    result = MetaData()
    for name, table in source.tables.items():
        if (revision not in {"004", "005"} or revision == "005" or name not in SSO_TABLES) and (
            revision in {"009", "010", "011"} or name not in CATEGORY_TABLES
        ):
            copied = table.to_metadata(result)
            if name == "audit_events" and revision not in {"010", "011"}:
                # Historical schema manifests must not gain the nullable 010 role column.
                copied._columns.remove(copied.c.actor_role)
            if name == "policies" and revision in {"004", "005"}:
                for index in tuple(copied.indexes):
                    if index.name == "ux_policies_tenant_id":
                        copied.indexes.remove(index)
            for constraint in table.constraints:
                for target in copied.constraints:
                    if constraint.name == target.name and str(getattr(constraint, "sqltext", "")) == str(getattr(target, "sqltext", "")):
                        target._ddl_if = constraint._ddl_if
    if revision == "011":
        from .chat_models import ChatBase
        for table in ChatBase.metadata.tables.values():
            table.to_metadata(result)
    return result


def history_for_revision(revision):
    return (
        LEGACY_HISTORY
        + (MULTI_HISTORY if revision in {"006", "007", "008", "009", "010", "011"} else ())
        + (("validation_executions",) if revision in {"008", "009", "010", "011"} else ())
    )


MULTI_PERMISSIONS = {
    "workspace_policy_states": ("SELECT", "INSERT", "UPDATE"),
    "workspace_policy_assignments": ("SELECT", "INSERT", "UPDATE"),
    "workspace_policy_assignment_events": ("SELECT", "INSERT"),
    "execution_policy_evidence": ("SELECT", "INSERT"),
}

__all__ = ["metadata_for_revision", "history_for_revision", "SSO_TABLES", "MULTI_TABLES", "MULTI_PERMISSIONS"]
