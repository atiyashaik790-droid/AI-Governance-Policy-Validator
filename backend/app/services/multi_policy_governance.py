"""Internal Phase D orchestration only. No public HTTP route is registered."""

import asyncio
import json
import time

from fastapi import HTTPException

from .. import providers
from ..execution_identity import snapshot
from ..protected_reviews import ensure_ready, capture
from ..user_access import public_result
from ..decision_messages import decision_notice, captured_documents
from ..config import settings
from ..engine_multi_policy import evaluate_policy_set, strongest
from ..models import Review
from ..models_multi_policy import Execution006, ExecutionPolicyEvidence
from ..repositories import record_audit_event
from ..security import require_role
from . import policy_sets
from .reviews import get_review
from .multi_policy_evidence import prepare, validate_stage
from ..chat_history import record_turn


def persist(db, user, admission, operation, result, original_prompt=None):
    result["decision_notice"] = decision_notice(result, captured_documents(admission.pins))
    metadata, entries = prepare(admission, operation, result)
    metadata["execution_identity"] = snapshot(user)
    execution = Execution006(tenant=user.tenant, actor=user.user, execution_mode="MULTI", policy_id=None, version=None,
                             model="local-fixture" if settings.provider_mode == "fixture" else settings.azure_openai_deployment or "not-configured",
                             decision=result["decision"], metadata_json=json.dumps(metadata))
    db.add(execution)
    db.flush()
    for pin, decision, status, evidence in entries:
        db.add(ExecutionPolicyEvidence(tenant=user.tenant, execution_id=execution.id, policy_id=pin.policy_id,
                                      version_id=pin.version_id, set_revision=admission.set_revision,
                                      document_sha256=pin.document_sha256, effective_decision=decision,
                                      inspection_status=status, evidence_json=json.dumps(evidence)))
    record_audit_event(db, user, f"governance.multi.{operation}.{result['decision']}", execution.id)
    result["request_id"] = execution.id
    if result["decision"] == "HUMAN_REVIEW":
        review = Review(tenant=user.tenant, execution_id=execution.id)
        db.add(review)
        db.flush()
        capture(db, user, review, original_prompt)
        result["review_id"] = review.id


async def execute(operation, payload, db, user, *, expected_revision=None, attachment=None, original_prompt=None):
    """One admission, one captured set, at most one generation dispatch; no retry."""
    require_role(user, "Admin", "Developer", "Policy Owner", "User")
    if operation not in {"generate", "validate-input", "validate-output"}:
        raise HTTPException(404, "Unknown governance operation")
    if payload.source_review_id:
        review = get_review(db, user, payload.source_review_id)
        if review.status == "PENDING":
            raise HTTPException(409, "Resolve the review before linked resubmission")
    ensure_ready(db)
    admission = None
    result = None
    persistence_attempted = False
    committed = False
    providers.generation_usage.set(None)
    try:
        admission = policy_sets.admit(db, user, expected_revision=expected_revision)
        if admission.mode != "MULTI":
            raise HTTPException(409, "WORKSPACE_MODE_CONFLICT")
        deadline = time.monotonic() + settings.inference_deadline
        async with asyncio.timeout(settings.inference_deadline):
            inspected = validate_stage(await evaluate_policy_set(payload.text, admission.pins, deadline=deadline), admission.pins)
            result = {"input": inspected if operation != "validate-output" else None,
                      "output": inspected if operation == "validate-output" else None,
                      "decision": inspected["decision"], "safe_response": None, "model_invoked": False,
                      "generation_status": "NOT_INVOKED", "set_revision": admission.set_revision}
            if attachment is not None:
                result["attachment"] = attachment
            if payload.source_review_id:
                result["source_review_id"] = payload.source_review_id
            if operation == "generate" and inspected["safe_text"] is not None:
                policy_sets.fence(db, user, admission)
                if time.monotonic() >= deadline:
                    raise TimeoutError("Generation deadline")
                result["model_invoked"] = True
                try:
                    generated = await asyncio.wait_for(providers.generate_ai_response(inspected["safe_text"]),
                                                       min(settings.provider_timeout, deadline - time.monotonic()))
                    if not isinstance(generated, str) or not generated.strip() or len(generated) > 30000:
                        raise ValueError("Invalid generation response")
                except providers.ProviderUnavailable as error:
                    result.update(generation_status="FAILED", decision="BLOCK", provider_error="Generation unavailable; response withheld",
                                  provider_diagnostics=error.diagnostics)
                except Exception:
                    # An ambiguous timeout/transport response is never retried.
                    result.update(generation_status="FAILED", decision="BLOCK", provider_error="Generation unavailable; response withheld")
                else:
                    result["generation_status"] = "SUCCEEDED"
                    output = validate_stage(await evaluate_policy_set(generated, admission.pins, deadline=deadline), admission.pins)
                    result["output"] = output
                    result["decision"] = strongest([inspected["decision"], output["decision"]])
                    result["safe_response"] = output["safe_text"]
            policy_sets.fence(db, user, admission, hold=True)
            persistence_attempted = True
            persist(db, user, admission, operation, result, payload.text if original_prompt is None else original_prompt)
            if operation == "generate":
                record_turn(db, user, payload.conversation_id, result)
            if time.monotonic() >= deadline:
                raise TimeoutError("Persistence deadline")
            status = result["generation_status"] if operation == "generate" else "INSPECTED"
            if not policy_sets.finish_admission(db, user, admission, status, providers.generation_usage.get(), commit=False):
                raise HTTPException(409, "RESERVATION_FENCED")
            db.commit()
            committed = True
            if time.monotonic() >= deadline:
                raise TimeoutError("Release deadline")
            # Published snapshots already carry their display names. Attach them
            # only to the response, leaving stored evidence and decisions intact.
            names = {pin.policy_id: json.loads(pin.document_json)["name"] for pin in admission.pins}
            for stage_name in ("input", "output"):
                stage = result.get(stage_name)
                if isinstance(stage, dict):
                    for item in stage["policies"]:
                        item["policy_name"] = names[item["policy_id"]]
            return public_result(result, user)
    except Exception as error:
        db.rollback()
        # A fenced/timed-out admitted request still gets complete captured-set
        # accounting. Never retry a failed persistence transaction automatically.
        if admission is not None and admission.mode == "MULTI" and (not persistence_attempted or isinstance(error, TimeoutError)) and not committed:
            reason = "REQUEST_TIMEOUT" if isinstance(error, TimeoutError) else "REQUEST_FENCED" if isinstance(error, HTTPException) and error.status_code == 409 else "INSPECTION_FAILED"
            failed = dict(result or {"input": None, "output": None, "model_invoked": False, "generation_status": "NOT_INVOKED"})
            failed.update(decision="BLOCK", safe_response=None, failure_reasons=[reason])
            persist(db, user, admission, operation, failed)
            policy_sets.finish_admission(db, user, admission, "FAILED", providers.generation_usage.get(), commit=False)
            db.commit()
        if isinstance(error, TimeoutError):
            raise HTTPException(504, "Governance deadline exceeded; response withheld") from None
        raise
    finally:
        db.rollback()
        if admission is not None:
            policy_sets.finish_admission(db, user, admission, "FAILED", providers.generation_usage.get())
