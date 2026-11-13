"""Empty -> current SQLite rehearsal, never evidence of Azure SQL execution."""

import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.analytics import overview
from app.models import Audit, Policy, SsoMembership, Version
from app.models_multi_policy import WorkspacePolicyAssignment
from app.schema_compatibility import inspect_schema
from app.schema_manifests import metadata_for_revision
from app.security import Identity
from app.services.policies import get_policy
from app.routers.policies import create_new_policy
from test_multi_policy_phase_b import migrate, fixture_engine

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("fresh_demo", ROOT / "scripts/prepare_fresh_demo.py")
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


@pytest.fixture
def fresh(tmp_path):
    path = tmp_path / "fresh.db"
    migrate(path, "head")
    engine = fixture_engine(path)
    with Session(engine, expire_on_commit=False) as db:
        yield db
    engine.dispose()


def test_empty_chain_schema_and_analytics(fresh):
    assert fresh.scalar(text("SELECT version_num FROM alembic_version")) == "011"
    assert inspect_schema(fresh, require_sso=True)["revision"] == "011"
    for table in metadata_for_revision("011").sorted_tables:
        expected = 8 if table.name == "governance_categories" else 0
        assert fresh.scalar(select(text("count(*)")).select_from(table)) == expected
    result = overview(fresh, Identity("admin", demo.TENANT, "Admin"), None, None)
    assert result["total_policies"] == result["total_validations"] == 0


def test_demo_idempotence_memberships_multi_and_isolation(fresh):
    demo.seed_local(fresh)

    def snapshot():
        return {table.name: list(fresh.execute(select(table)).tuples()) for table in metadata_for_revision("011").sorted_tables}

    before = snapshot()
    demo.seed_local(fresh)
    assert snapshot() == before
    assert set(fresh.scalars(select(SsoMembership.role))) == {"Admin", "User"}
    assert len(list(fresh.scalars(select(WorkspacePolicyAssignment).where(WorkspacePolicyAssignment.active)))) == 8
    policy = fresh.scalar(select(Policy))
    with pytest.raises(HTTPException) as denied:
        get_policy(fresh, Identity("other", "other-tenant", "Admin"), policy.id)
    assert denied.value.status_code == 404
    from app.schemas import PolicyDocument

    with pytest.raises(HTTPException) as denied:
        create_new_policy(PolicyDocument(name="Denied"), fresh, Identity("user", demo.TENANT, "User"))
    assert denied.value.status_code == 403
    assert len(list(fresh.scalars(select(Version)))) == 8


def test_seed_drift_is_not_overwritten(fresh):
    demo.seed_local(fresh)
    member = fresh.scalar(select(SsoMembership).where(SsoMembership.role == "User"))
    member.role = "Admin"
    fresh.commit()
    before = len(list(fresh.scalars(select(Audit))))
    with pytest.raises(ValueError, match="drift"):
        demo.seed_local(fresh)
    assert len(list(fresh.scalars(select(Audit)))) == before
    assert member.role == "Admin"


def test_resume_after_interrupted_publication(fresh, monkeypatch):
    import app.services.policies as lifecycle

    original = lifecycle.transition_policy

    def interrupt(*args, **kwargs):
        if args[1] == "approve":
            raise RuntimeError("synthetic interruption")
        return original(*args, **kwargs)

    monkeypatch.setattr(lifecycle, "transition_policy", interrupt)
    with pytest.raises(RuntimeError):
        demo.seed_local(fresh)
    assert fresh.scalar(select(Policy.status)) == "SUBMITTED"
    monkeypatch.setattr(lifecycle, "transition_policy", original)
    demo.seed_local(fresh)
    assert len(list(fresh.scalars(select(Version)))) == 8


def test_seed_rejects_non_disposable_database():
    from unittest.mock import Mock

    db = Mock()
    db.get_bind.return_value.dialect.name = "mssql"
    db.get_bind.return_value.url.database = "production"
    with pytest.raises(ValueError, match="disposable"):
        demo.seed_local(db)
    db.execute.assert_not_called()


@pytest.mark.parametrize(
    "prompt,expected",
    [
        ("Explain why governance matters.", "ALLOW"),
        ("Email alex@example.test or call +1 202-555-0147.", "REDACT"),
        ("Synthetic api_key=DEMO1234567890NOTREAL", "BLOCK"),
        ("Synthetic credit card 4111 1111 1111 1111", "BLOCK"),
        ("An internal-only synthetic note", "BLOCK"),
        ("review-required synthetic request", "HUMAN_REVIEW"),
        ("synthetic-moderation-flag", "BLOCK"),
    ],
)
async def test_eight_policy_profile_decisions_and_attribution(prompt, expected, monkeypatch):
    from hashlib import sha256
    from unittest.mock import AsyncMock
    from app import engine_multi_policy as evaluator
    from app.schemas import PolicyDocument
    from app.services.policy_sets import PublishedPin

    async def coverage(text, required):
        return {name: name == "violence" and "synthetic-moderation-flag" in text for name in required}

    moderate = AsyncMock(side_effect=coverage)
    monkeypatch.setattr(evaluator, "moderation_evidence", moderate)
    pins = []
    for index, document in enumerate(demo.plan()["policies"]):
        encoded = PolicyDocument.model_validate(document).model_dump_json()
        pins.append(PublishedPin(f"policy-{index}", f"version-{index}", 1, encoded, sha256(encoded.encode()).hexdigest()))
    result = await evaluator.evaluate_policy_set(prompt, pins)
    reverse = await evaluator.evaluate_policy_set(prompt, list(reversed(pins)))
    assert result == reverse
    assert result["decision"] == expected
    assert result["policy_count"] == len(result["policies"]) == 8
    assert {item["policy_id"] for item in result["policies"]} == {pin.policy_id for pin in pins}
    if expected == "REDACT":
        assert "alex@example.test" not in result["safe_text"]
        assert "202-555-0147" not in result["safe_text"]
        assert result["revalidated"]
    if "internal-only" in prompt or "api_key=" in prompt or "credit card" in prompt:
        moderate.assert_not_called()


async def test_eight_policy_profile_withholds_when_moderation_unavailable(monkeypatch):
    from hashlib import sha256
    from unittest.mock import AsyncMock
    from app import engine_multi_policy as evaluator
    from app.schemas import PolicyDocument
    from app.services.policy_sets import PublishedPin

    monkeypatch.setattr(evaluator, "moderation_evidence", AsyncMock(side_effect=TimeoutError))
    pins = []
    for index, document in enumerate(demo.plan()["policies"]):
        encoded = PolicyDocument.model_validate(document).model_dump_json()
        pins.append(PublishedPin(f"policy-{index}", f"version-{index}", 1, encoded, sha256(encoded.encode()).hexdigest()))
    result = await evaluator.evaluate_policy_set("Explain governance.", pins)
    assert result["decision"] == "BLOCK" and result["safe_text"] is None


def test_operator_membership_bootstrap_is_idempotent_and_audits_changes(fresh):
    from manage_sso_membership import apply_mapping
    from sqlalchemy import func

    mapping = demo.plan()["memberships"][0]
    apply_mapping(fresh, mapping, "synthetic-operator", "local-only")
    fresh.commit()
    count = fresh.scalar(select(func.count()).select_from(Audit))
    apply_mapping(fresh, mapping, "synthetic-operator", "local-only")
    fresh.commit()
    assert fresh.scalar(select(func.count()).select_from(Audit)) == count
    changed = {**mapping, "enabled": False}
    apply_mapping(fresh, changed, "synthetic-operator", "local-only")
    fresh.commit()
    assert fresh.scalar(select(func.count()).select_from(Audit)) == count + 1
    assert not fresh.scalar(select(SsoMembership)).enabled
