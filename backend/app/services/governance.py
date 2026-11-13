"""Existing governance gates, persistence, deadlines and usage finalization."""

import asyncio
import json
import time
from fastapi import HTTPException
from sqlalchemy.orm import Session
from ..config import settings
from ..dependencies import DB, USER
from ..models import Execution, Review
from ..schemas import TextRequest
from ..decision_messages import decision_notice
from ..execution_identity import snapshot
from ..protected_reviews import ensure_ready, capture
from ..user_access import public_result
from ..security import Identity, require_role
from ..engine import inspect_text
from .. import providers, usage
from ..repositories import record_audit_event
from .policies import load_active_policy
from .reviews import get_review
from . import policy_sets
from ..stage_timing import stage as timed_stage
from ..chat_history import record_turn


async def governed_execution(operation: str, payload: TextRequest, db: Session = DB, user: Identity = USER, deadline: float | None = None, admission=None, attachment=None, original_prompt=None):
    require_role(user, "Admin", "Developer", "Policy Owner", "User")
    if operation not in ("generate", "validate-input", "validate-output"):
        raise HTTPException(404, "Unknown governance operation")
    if payload.source_review_id:
        source_review = get_review(db, user, payload.source_review_id)
        if source_review.status == "PENDING":
            raise HTTPException(409, "Resolve the review before linked resubmission")
    started = time.perf_counter()
    with timed_stage("policy.selection", db, deadline):
        policy, version, document = admission.pins[0].legacy_tuple() if admission else load_active_policy(db, user)
    with timed_stage("inspection", db, deadline):
        inspected = await inspect_text(payload.text, document)
    result = {
        "input": inspected if operation != "validate-output" else None,
        "output": inspected if operation == "validate-output" else None,
        "decision": inspected["decision"],
        "safe_response": None,
        "model_invoked": False,
        "generation_status": "NOT_INVOKED",
        "provider_mode": settings.provider_mode,
        "policy_id": policy.id,
        "policy_name": document.name,
        "policy_version": version.number,
    }
    if operation == "generate" and inspected["decision"] in ("ALLOW", "REDACT"):
        if admission:
            policy_sets.fence(db, user, admission)
        try:
            result["model_invoked"] = True
            generated = await providers.generate_ai_response(inspected["safe_text"])
            result["generation_status"] = "SUCCEEDED"
            output = await inspect_text(generated, document)
            result["output"] = output
            result["decision"] = "REDACT" if inspected["decision"] == "REDACT" and output["decision"] == "ALLOW" else output["decision"]
            if output["decision"] in ("ALLOW", "REDACT"):
                result["safe_response"] = output["safe_text"]
        except providers.ProviderUnavailable as error:
            result["generation_status"] = "FAILED"
            result["decision"] = "BLOCK"
            result["provider_error"] = "Generation unavailable; response withheld"
            result["provider_diagnostics"] = error.diagnostics
    result["decision_notice"] = decision_notice(result, {policy.id: document})
    if attachment is not None:
        result["attachment"] = attachment
    if payload.source_review_id:
        result["source_review_id"] = payload.source_review_id
    result["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
    if admission:
        policy_sets.fence(db, user, admission, hold=True)
    metadata = json.loads(json.dumps(result))
    metadata.pop("safe_response", None)
    metadata.pop("decision_notice", None)
    metadata["execution_identity"] = snapshot(user)
    for stage in ("input", "output"):
        if metadata.get(stage):
            metadata[stage].pop("safe_text", None)
    execution = Execution(
        tenant=user.tenant,
        actor=user.user,
        policy_id=policy.id,
        version=version.number,
        model="local-fixture" if settings.provider_mode == "fixture" else settings.azure_openai_deployment or "not-configured",
        decision=result["decision"],
        metadata_json=json.dumps(metadata),
    )
    with timed_stage("execution.persistence", db, deadline):
        db.add(execution)
        db.flush()
        result["request_id"] = execution.id
        record_audit_event(db, user, f"governance.{operation}.{result['decision']}", execution.id)
    if result["decision"] == "HUMAN_REVIEW":
        with timed_stage("review.persistence", db, deadline):
            review = Review(tenant=user.tenant, execution_id=execution.id)
            db.add(review)
            db.flush()
        with timed_stage("review.capture", db, deadline):
            capture(db, user, review, payload.text if original_prompt is None else original_prompt)
        result["review_id"] = review.id
    with timed_stage("deadline.precommit", db, deadline):
        # Synchronous database work cannot be cancelled by asyncio; check elapsed time before release.
        if deadline is not None and time.monotonic() >= deadline:
            raise HTTPException(504, "Governance deadline exceeded; response withheld")
    if admission:
        final_state = result["generation_status"] if operation == "generate" else "INSPECTED"
        policy_sets.finish_admission(db, user, admission, final_state, providers.generation_usage.get(), commit=False)
    if operation == "generate":
        record_turn(db, user, payload.conversation_id, result)
    with timed_stage("execution.commit", db, deadline):
        db.commit()
    if deadline is not None and time.monotonic() >= deadline:
        raise HTTPException(504, "Governance deadline exceeded after persistence; inspect history before retrying")
    return result


async def governance(operation: str, payload: TextRequest, db: Session = DB, user: Identity = USER, *, attachment=None, original_prompt=None):
    require_role(user, "Admin", "Developer", "Policy Owner", "User")
    with timed_stage("governance.preflight", db):
        ensure_ready(db)
    # Quotas include inspections because live moderation is also a paid dependency.
    admission = None
    with timed_stage("policy.admission", db):
        if policy_sets.schema_006(db):
            admission = policy_sets.admit(db, user, legacy_only=True)
            identifier = admission.reservation_id
        else:
            load_active_policy(db, user)
            identifier = usage.reserve(db, user)
    providers.generation_usage.set(None)
    state = "FAILED"
    try:
        deadline = time.monotonic() + settings.inference_deadline
        with timed_stage("governance.execution", db, deadline):
            async with asyncio.timeout(settings.inference_deadline):
                if admission:
                    result = await governed_execution(operation, payload, db, user, deadline, admission=admission, attachment=attachment, original_prompt=original_prompt)
                else:
                    result = await governed_execution(operation, payload, db, user, deadline, attachment=attachment, original_prompt=original_prompt)
        state = result["generation_status"] if operation == "generate" else "INSPECTED"
        return public_result(result, user)
    except TimeoutError:
        db.rollback()
        raise HTTPException(504, "Governance deadline exceeded; response withheld") from None
    finally:
        db.rollback()
        if admission:
            policy_sets.finish_admission(db, user, admission, state, providers.generation_usage.get())
        else:
            usage.finish(db, identifier, state, providers.generation_usage.get())
