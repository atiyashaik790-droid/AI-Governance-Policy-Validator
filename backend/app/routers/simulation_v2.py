"""Read-only policy inspection for the simulator; no generation or execution record."""

import asyncio
import time
from hashlib import sha256

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..dependencies import DB, USER
from ..engine_multi_policy import evaluate_policy_set
from ..models import Policy
from ..models_multi_policy import WorkspacePolicyState
from ..schemas import PolicyDocument, TextRequest
from ..security import Identity, require_role
from ..services import policy_sets

router = APIRouter(prefix="/api/v2/simulation", tags=["Policy simulation"])


async def inspect(pins, text):
    try:
        async with asyncio.timeout(settings.inference_deadline):
            result = await evaluate_policy_set(text, pins, deadline=time.monotonic() + settings.inference_deadline)
    except TimeoutError:
        raise HTTPException(504, "Simulation deadline exceeded") from None
    # Simulation results contain detector evidence only, never the submitted text.
    result["safe_text"] = None
    return {**result, "simulation": True, "model_invoked": False}


@router.post("/policies/{policy_id}")
async def selected_policy(policy_id: str, payload: TextRequest, db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Policy Owner")
    policy = db.scalar(select(Policy).where(Policy.id == policy_id, Policy.tenant == user.tenant, Policy.status != "DELETED"))
    if policy is None:
        raise HTTPException(404, "Policy not found")
    document = PolicyDocument.model_validate_json(policy.draft)
    encoded = document.model_dump_json()
    pin = policy_sets.PublishedPin(policy.id, f"draft-{policy.revision}", policy.revision, encoded, sha256(encoded.encode()).hexdigest())
    result = await inspect((pin,), payload.text)
    result["policies"][0]["policy_name"] = policy.name
    result["policies"][0]["version_label"] = f"Draft revision {policy.revision}"
    return result


@router.post("/workspace")
async def active_workspace(payload: TextRequest, db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Policy Owner")
    if not policy_sets.schema_006(db):
        raise HTTPException(409, "MULTI workspace unavailable")
    state = db.scalar(select(WorkspacePolicyState).where(WorkspacePolicyState.tenant == user.tenant))
    if state is None or state.mode != "MULTI":
        raise HTTPException(409, "MULTI workspace required")
    pins = policy_sets.capture(db, user, state)
    result = await inspect(pins, payload.text)
    names = dict(db.execute(select(Policy.id, Policy.name).where(Policy.tenant == user.tenant, Policy.id.in_([p.policy_id for p in pins]))).all())
    for item in result["policies"]:
        item["policy_name"] = names.get(item["policy_id"], "")
        item["version_label"] = f"Published version {item['version']}"
    result["set_revision"] = state.set_revision
    return result
