"""Operator-only, explicit identity mapping. Defaults to validation/plan without DB access."""

import argparse
import json
import sys
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

ROLES = {"Admin", "User", "Developer", "Reviewer", "Auditor", "Policy Owner"}


def validate_mapping(data: dict) -> dict:
    expected = {"directory_tenant", "object_id", "tenant", "actor", "role", "enabled"}
    if (
        set(data) != expected
        or data["role"] not in ROLES
        or type(data["enabled"]) is not bool
    ):
        raise ValueError(
            "Provide the exact documented membership fields and an approved role"
        )
    for key in ("directory_tenant", "object_id"):
        data[key] = str(UUID(data[key]))
    for key in ("tenant", "actor"):
        if (
            not isinstance(data[key], str)
            or not 1 <= len(data[key]) <= 80
            or not all(c.isalnum() or c in "-_.:@" for c in data[key])
        ):
            raise ValueError(
                "Tenant and actor must be approved stable application identifiers"
            )
    return data


def apply_mapping(db, data: dict, operator: str, approval: str):
    from sqlalchemy import select
    from app.models import Audit, SsoMembership

    membership = db.scalar(
        select(SsoMembership).where(
            SsoMembership.directory_tenant == data["directory_tenant"],
            SsoMembership.object_id == data["object_id"],
        )
    )
    if membership and (membership.tenant, membership.actor) != (
        data["tenant"],
        data["actor"],
    ):
        raise ValueError(
            "Stable actor/workspace remapping requires separate reviewed migration"
        )
    if membership and all(
        getattr(membership, field) == value for field, value in data.items()
    ):
        return (
            membership  # Exact rerun is a no-op, including append-only audit history.
        )
    if not membership:
        membership = SsoMembership(**data)
        db.add(membership)
        db.flush()
    else:
        membership.role, membership.enabled = data["role"], data["enabled"]
    db.add(
        Audit(
            tenant=data["tenant"],
            actor=operator,
            action="sso.membership.provisioned",
            resource=f"{membership.id}:{data['role']}:{data['enabled']}:{approval}",
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--operator")
    parser.add_argument("--approval-ref")
    args = parser.parse_args()
    try:
        data = validate_mapping(json.loads(args.mapping.read_text()))
        if not args.apply:
            print(
                json.dumps(
                    {"mode": "PLAN_ONLY", "valid": True, "database_accessed": False}
                )
            )
            return
        if (
            not args.operator
            or not args.approval_ref
            or len(args.operator) > 80
            or len(args.approval_ref) > 100
        ):
            raise ValueError(
                "Apply requires an authorized operator and explicit approval reference"
            )
        from app.config import settings

        if data["directory_tenant"] != str(UUID(settings.entra_tenant_id)):
            raise ValueError("Directory must match the approved SSO tenant")
        from app.database import SessionLocal

        with SessionLocal.begin() as db:
            apply_mapping(db, data, args.operator, args.approval_ref)
        print(json.dumps({"mode": "APPROVED_MEMBERSHIP_APPLIED"}))
    except Exception:
        raise SystemExit(
            "Membership operation failed; check approved mapping, operator, permissions and migration. No credentials printed."
        ) from None


if __name__ == "__main__":
    main()
