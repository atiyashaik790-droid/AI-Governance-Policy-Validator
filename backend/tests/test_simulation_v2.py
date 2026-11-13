"""Read-only simulation against a disposable migrated database."""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models import Policy, Audit, InferenceUsage
from app.models_multi_policy import Execution006, WorkspacePolicyAssignment
from app.routers.simulation_v2 import selected_policy, active_workspace
from app.schemas import TextRequest
from app import providers
from app import engine_multi_policy as evaluator
from test_multi_policy_phase_b import engine006, templates, ADMIN, FOREIGN  # noqa: F401
from test_multi_policy_phase_d import document, setup_workspace


@pytest.fixture(autouse=True)
def inline_detector(monkeypatch):
    async def run(function, *args):
        return function(*args)
    monkeypatch.setattr(evaluator.asyncio, "to_thread", run)


@pytest.mark.parametrize("action,expected", [
    ("ALLOW", "ALLOW"), ("BLOCK", "BLOCK"),
    ("REDACT", "REDACT"), ("HUMAN_REVIEW", "HUMAN_REVIEW"),
])
async def test_selected_simulation(engine006, monkeypatch, action, expected):  # noqa: F811
    doc = document(name=f"Synthetic {action}", keyword="absent" if action == "ALLOW" else "marker", action="BLOCK" if action == "ALLOW" else action)
    monkeypatch.setattr(providers, "moderate_user_prompt", AsyncMock(side_effect=AssertionError("unnecessary provider call")))
    with Session(engine006) as db:
        policy = Policy(tenant="one", name=doc.name, draft=doc.model_dump_json(), status="DRAFT", enabled=1)
        db.add(policy)
        db.commit()
        result = await selected_policy(policy.id, TextRequest(text="marker"), db, ADMIN)
        assert result["decision"] == expected
        assert result["policies"][0]["policy_name"] == doc.name
        assert result["policies"][0]["version_label"] == "Draft revision 1"
        assert result["model_invoked"] is False and result["safe_text"] is None
        with pytest.raises(HTTPException) as foreign:
            await selected_policy(policy.id, TextRequest(text="marker"), db, FOREIGN)
        assert foreign.value.status_code == 404
        with pytest.raises(HTTPException) as unauthorized:
            await selected_policy(policy.id, TextRequest(text="marker"), db, type(ADMIN)("developer", "one", "Developer"))
        assert unauthorized.value.status_code == 403
        assert db.scalar(select(func.count()).select_from(Audit)) == 0
        assert db.scalar(select(func.count()).select_from(InferenceUsage)) == 0
        assert db.scalar(select(func.count()).select_from(Execution006)) == 0


async def test_active_workspace_simulation(engine006, monkeypatch):  # noqa: F811
    monkeypatch.setattr(providers, "moderate_user_prompt", AsyncMock(side_effect=AssertionError("unnecessary provider call")))
    with Session(engine006) as db:
        _, revision = setup_workspace(db, [document(name="Review", keyword="marker", action="HUMAN_REVIEW"), document(name="Block", keyword="marker", action="BLOCK")])
        before = db.execute(select(WorkspacePolicyAssignment.policy_id, WorkspacePolicyAssignment.version_id)).all()
        result = await active_workspace(TextRequest(text="marker"), db, ADMIN)
        assert result["decision"] == "BLOCK" and result["policy_count"] == 2
        assert result["set_revision"] == revision
        assert {p["policy_name"] for p in result["policies"]} == {"Review", "Block"}
        assert {p["version"] for p in result["policies"]} == {1}
        assert db.execute(select(WorkspacePolicyAssignment.policy_id, WorkspacePolicyAssignment.version_id)).all() == before
        assert db.scalar(select(func.count()).select_from(Execution006)) == 0

