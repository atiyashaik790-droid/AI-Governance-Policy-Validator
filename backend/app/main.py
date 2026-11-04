"""Tenant-scoped API and governance gateway."""

import asyncio
import re
from uuid import uuid4
import json
import logging
import time
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, Query, Request, Body, Header
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, func, text, cast, Float, case
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from .config import settings
from .database import get_database
from .models import Policy, Version, Assignment, Audit, Execution, Review, Feedback, Export
from .schemas import (
    PolicyDocument,
    TextRequest,
    FeedbackRequest,
    ExportRequest,
    GovernanceResult,
    PolicyResponse,
    InspectionResult,
    RollbackRequest,
    ReviewUpdate,
    ReviewResolution,
)
from .security import authenticate, require_role, Identity, account_enabled
from .engine import inspect_text, detect_sensitive_information, redact_personal_information
from . import providers, exports, analytics as analytics_service, usage
from .sessions import router as session_router
from .release import information as release_information
from .models import ReviewAssignment, ReviewNote

app_schema_revision = "004"

logger = logging.getLogger("governance.http")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
logger.propagate = False

app = FastAPI(title="AI Governance Policy Validator", version="1.2.0")
app.include_router(session_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "If-Match"],
    expose_headers=["X-Request-ID", "Retry-After"],
)
# Finish the transaction before sending success, including dependency commit failures.
DB = Depends(get_database, scope="function")
USER = Depends(authenticate)


# Reject oversized requests before JSON parsing and suppress raw validation inputs.
@app.middleware("http")
async def bound_request_size(request: Request, call_next):
    length = request.headers.get("content-length")
    if length and (not length.isdigit() or int(length) > 64000):
        return JSONResponse(status_code=413, content={"detail": "Request exceeds 64 KB"})
    received = 0
    chunks = []
    async for chunk in request.stream():
        received += len(chunk)
        chunks.append(chunk)
        if received > 64000:
            return JSONResponse(status_code=413, content={"detail": "Request exceeds 64 KB"})
    request._body = b"".join(chunks)
    started = time.perf_counter()
    supplied = request.headers.get("x-request-id", "")
    correlation = supplied if re.fullmatch(r"[A-Za-z0-9_-]{8,64}", supplied) else str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = correlation
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
    )
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    logger.info(
        json.dumps(
            {
                "event": "http.completed",
                "correlation_id": correlation,
                "route": getattr(request.scope.get("route"), "path", "unmatched"),
                "method": request.method,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        )
    )
    return response


# Never expose DB connection strings, SQL parameters or sensitive request bodies.
@app.exception_handler(SQLAlchemyError)
async def database_failure(request, error):
    return JSONResponse(status_code=503, content={"detail": "Database operation unavailable; nothing released"})


# Reject stale lifecycle transitions instead of approving an edited draft concurrently.
@app.exception_handler(StaleDataError)
async def concurrent_policy_change(request, error):
    return JSONResponse(status_code=409, content={"detail": "Record changed concurrently; reload and retry"})


# Return locations and types without reflecting potentially sensitive values.
@app.exception_handler(RequestValidationError)
async def invalid_request(request, error):
    return JSONResponse(status_code=422, content={"detail": [{"loc": item["loc"], "type": item["type"]} for item in error.errors()]})


# Record immutable metadata in the same transaction as the governed operation.
def record_audit_event(db: Session, user: Identity, action: str, resource: str) -> None:
    db.add(Audit(tenant=user.tenant, actor=user.user, action=action, resource=resource))


# Resolve a tenant-owned policy without disclosing foreign tenant identifiers.
def get_policy(db: Session, user: Identity, policy_id: str, include_deleted: bool = False) -> Policy:
    policy = db.scalar(select(Policy).where(Policy.id == policy_id, Policy.tenant == user.tenant))
    if not policy or (policy.status == "DELETED" and not include_deleted):
        raise HTTPException(404, "Policy not found")
    return policy


# Return a model's explicitly stored columns as JSON-compatible metadata.
def serialize(record) -> dict:
    return {column.name: getattr(record, column.name) for column in record.__table__.columns}


# Paginate tenant-owned records in stable order.
def list_records(db: Session, user: Identity, model, offset: int, limit: int) -> list:
    ordering = (model.created.desc(), model.id) if hasattr(model, "created") else (model.id.desc(),)
    return [
        serialize(row)
        for row in db.scalars(select(model).where(model.tenant == user.tenant).order_by(*ordering).offset(offset).limit(limit))
    ]


# Resolve exactly one enabled published snapshot; missing assignments always fail closed.
def load_active_policy(db: Session, user: Identity):
    assignment = db.get(Assignment, user.tenant)
    version = db.get(Version, assignment.version_id) if assignment else None
    policy = get_policy(db, user, version.policy_id) if version and version.tenant == user.tenant else None
    if not policy or not policy.enabled or policy.status in ("ARCHIVED", "DELETED"):
        raise HTTPException(409, "No enabled active policy; request withheld")
    return policy, version, PolicyDocument.model_validate_json(version.document)


# Check process liveness without exposing configuration.
@app.get("/health")
def health():
    return {"status": "ok"}


# Check database availability; provider configuration is separately reported.
@app.get("/ready")
def ready(db: Session = DB):
    db.execute(text("SELECT 1"))
    if db.bind.dialect.name == "mssql":
        revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
        if revision != app_schema_revision:
            raise HTTPException(503, "Reviewed database migration required before serving this release")
    return {"status": "ready", "provider_mode": settings.provider_mode, "release": release_information()}


# List real policies, scoped to the authenticated tenant.
@app.get("/api/policies", response_model=list[PolicyResponse])
def get_all_policies(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: str = Query("", max_length=120),
    status: str | None = Query(None, pattern="^(DRAFT|SUBMITTED|APPROVED|PUBLISHED|ARCHIVED)$"),
    enabled: bool | None = None,
    db: Session = DB,
    user: Identity = USER,
):
    query = select(Policy).where(Policy.tenant == user.tenant, Policy.status != "DELETED")
    if search:
        query = query.where(Policy.name.icontains(search, autoescape=True))
    if status:
        query = query.where(Policy.status == status)
    if enabled is not None:
        query = query.where(Policy.enabled == int(enabled))
    published = select(Version.id).where(Version.policy_id == Policy.id, Version.tenant == user.tenant).exists()
    active = (
        select(Assignment.tenant)
        .join(Version, Assignment.version_id == Version.id)
        .where(Assignment.tenant == user.tenant, Version.tenant == user.tenant, Version.policy_id == Policy.id)
        .exists()
    )
    return [
        {**serialize(row), "has_published_versions": bool(has_versions), "is_active": bool(is_active)}
        for row, has_versions, is_active in db.execute(
            # SQL Server permits EXISTS as a predicate, but not a SELECT value.
            query.add_columns(case((published, 1), else_=0), case((active, 1), else_=0))
            .order_by(Policy.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ]


# Validate and persist a new editable policy document.
@app.post("/api/policies", status_code=201, response_model=PolicyResponse)
def create_new_policy(document: PolicyDocument, db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Policy Owner")
    policy = Policy(tenant=user.tenant, name=document.name, draft=document.model_dump_json())
    db.add(policy)
    db.flush()
    record_audit_event(db, user, "policy.created", policy.id)
    return policy_details(db, user, policy)


def policy_details(db: Session, user: Identity, policy: Policy) -> dict:
    has_versions = db.scalar(select(Version.id).where(Version.policy_id == policy.id, Version.tenant == user.tenant).limit(1)) is not None
    active = (
        db.scalar(
            select(Version.id)
            .join(Assignment, Assignment.version_id == Version.id)
            .where(Assignment.tenant == user.tenant, Version.tenant == user.tenant, Version.policy_id == policy.id)
        )
        is not None
    )
    return {**serialize(policy), "has_published_versions": has_versions, "is_active": active}


# Read the current draft and lifecycle status.
@app.get("/api/policies/{policy_id}", response_model=PolicyResponse)
def view_policy(policy_id: str, db: Session = DB, user: Identity = USER):
    return policy_details(db, user, get_policy(db, user, policy_id, include_deleted=True))


# Editing leaves historical versions intact and invalidates all draft approvals.
@app.put("/api/policies/{policy_id}", response_model=PolicyResponse)
def update_existing_policy(
    policy_id: str,
    document: PolicyDocument,
    db: Session = DB,
    user: Identity = USER,
    expected_version: str | None = Header(default=None, alias="If-Match"),
):
    require_role(user, "Admin", "Policy Owner")
    policy = get_policy(db, user, policy_id)
    if policy.status == "ARCHIVED":
        raise HTTPException(409, "Archived policy cannot be edited")
    if expected_version is None:
        raise HTTPException(428, "Reload this policy and send its row_version in If-Match")
    if expected_version.strip('"') != str(policy.row_version):
        raise HTTPException(412, "Policy changed since you opened it; reload and review your changes")
    policy.draft, policy.name, policy.status = document.model_dump_json(), document.name, "DRAFT"
    policy.revision += 1
    record_audit_event(db, user, "policy.draft_updated", policy.id)
    db.flush()
    return policy_details(db, user, policy)


# Remove published policies from the workspace while preserving immutable history.
@app.delete("/api/policies/{policy_id}")
def delete_draft_policy(
    policy_id: str,
    db: Session = DB,
    user: Identity = USER,
    expected_version: str | None = Header(default=None, alias="If-Match"),
):
    require_role(user, "Admin", "Policy Owner")
    policy = get_policy(db, user, policy_id)
    versions = db.scalar(select(func.count()).select_from(Version).where(Version.policy_id == policy_id, Version.tenant == user.tenant))
    if versions:
        if expected_version is None:
            raise HTTPException(428, "Reload this policy and send its row_version in If-Match")
        if expected_version.strip('"') != str(policy.row_version):
            raise HTTPException(412, "Policy changed since you opened it; reload and review your changes")
        assignment = db.get(Assignment, user.tenant)
        active_version = db.get(Version, assignment.version_id) if assignment else None
        if active_version and active_version.policy_id == policy.id:
            raise HTTPException(409, "Activate another policy before deleting this policy")
        if policy.enabled:
            raise HTTPException(409, "Disable this policy before deleting it")
        policy.status, policy.enabled = "DELETED", 0
        record_audit_event(db, user, "policy.removed", policy.id)
        db.flush()
        return {"deleted": True, "history_retained": True}
    if policy.status != "DRAFT":
        raise HTTPException(409, "Only never-published drafts can be deleted")
    record_audit_event(db, user, "policy.deleted", policy.id)
    db.delete(policy)
    return {"deleted": True}


# Simulate the actual draft engine without publishing or invoking generation.
@app.post("/api/policies/{policy_id}/simulate", response_model=InspectionResult)
async def simulate_policy(policy_id: str, payload: TextRequest, db: Session = DB, user: Identity = USER):
    policy = get_policy(db, user, policy_id)
    document = PolicyDocument.model_validate_json(policy.draft)
    identifier = usage.reserve(db, user)
    state = "FAILED"
    try:
        async with asyncio.timeout(settings.inference_deadline):
            deadline = time.monotonic() + settings.inference_deadline
            result = await inspect_text(payload.text, document)
        if time.monotonic() >= deadline:
            raise HTTPException(504, "Simulation deadline exceeded; response withheld")
        record_audit_event(db, user, "policy.simulated", policy_id)
        db.commit()
        if time.monotonic() >= deadline:
            raise HTTPException(504, "Simulation deadline exceeded after persistence; inspect audit history")
        state = "SIMULATED"
        return result
    except TimeoutError:
        raise HTTPException(504, "Simulation deadline exceeded; response withheld") from None
    finally:
        db.rollback()
        usage.finish(db, identifier, state)


# Apply explicit lifecycle transitions under backend authorization.
def transition_policy(policy_id: str, operation: str, db: Session = DB, user: Identity = USER):
    policy = get_policy(db, user, policy_id)
    if operation in ("approve", "reject"):
        require_role(user, "Admin", "Reviewer")
    else:
        require_role(user, "Admin", "Policy Owner")
    if operation in ("submit", "approve", "publish"):
        expected = {"submit": "DRAFT", "approve": "SUBMITTED", "publish": "APPROVED"}[operation]
        if policy.status != expected:
            raise HTTPException(409, f"{operation} requires {expected}")
        document = PolicyDocument.model_validate_json(policy.draft)
        if document.rules.pii_detection.enabled and document.rules.pii_detection.entities:
            from .engine import get_pii_analyzer

            available = {"EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "US_SSN"}
            if settings.pii_mode == "presidio":
                try:
                    available.update(get_pii_analyzer().get_supported_entities(language="en"))
                except Exception:
                    raise HTTPException(503, "PII recognizers unavailable; policy cannot advance") from None
            if set(document.rules.pii_detection.entities) - available:
                raise HTTPException(422, "Policy selects PII entities unavailable in the configured detector")
        policy.status = {"submit": "SUBMITTED", "approve": "APPROVED", "publish": "PUBLISHED"}[operation]
        if operation == "publish":
            number = (db.scalar(select(func.max(Version.number)).where(Version.policy_id == policy_id)) or 0) + 1
            db.add(Version(policy_id=policy_id, tenant=user.tenant, number=number, document=policy.draft))
    elif operation == "reject":
        if policy.status != "SUBMITTED":
            raise HTTPException(409, "Rejection requires SUBMITTED")
        policy.status = "DRAFT"
    elif operation == "activate":
        version = db.scalar(
            select(Version).where(Version.policy_id == policy_id, Version.tenant == user.tenant).order_by(Version.number.desc())
        )
        if not version or not policy.enabled or policy.status != "PUBLISHED":
            raise HTTPException(409, "Activation requires enabled published policy")
        # A concurrent disable/delete must invalidate an activation's stale read.
        policy.row_version += 1
        db.flush()
        assignment = db.get(Assignment, user.tenant)
        if assignment:
            assignment.version_id = version.id
        else:
            db.add(Assignment(tenant=user.tenant, version_id=version.id))
    elif operation in ("enable", "disable"):
        if policy.status == "ARCHIVED":
            raise HTTPException(409, "Archived policies cannot be enabled")
        policy.enabled = int(operation == "enable")
    elif operation == "archive":
        assignment = db.get(Assignment, user.tenant)
        active_version = db.get(Version, assignment.version_id) if assignment else None
        if active_version and active_version.policy_id == policy_id:
            raise HTTPException(409, "Activate another policy before archiving")
        policy.status, policy.enabled = "ARCHIVED", 0
    else:
        raise HTTPException(404, "Unknown lifecycle operation")
    record_audit_event(db, user, f"policy.{operation}", policy_id)
    db.flush()
    return policy_details(db, user, policy)


# Return immutable published versions in newest-first order.
@app.get("/api/policies/{policy_id}/versions")
def policy_versions(
    policy_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = DB, user: Identity = USER
):
    get_policy(db, user, policy_id, include_deleted=True)
    return [
        serialize(row)
        for row in db.scalars(
            select(Version)
            .where(Version.policy_id == policy_id, Version.tenant == user.tenant)
            .order_by(Version.number.desc())
            .offset(offset)
            .limit(limit)
        )
    ]


# Run the complete input and output gates using the same immutable snapshot.
async def governed_execution(operation: str, payload: TextRequest, db: Session = DB, user: Identity = USER, deadline: float | None = None):
    require_role(user, "Admin", "Developer", "Policy Owner")
    if operation not in ("generate", "validate-input", "validate-output"):
        raise HTTPException(404, "Unknown governance operation")
    if payload.source_review_id:
        source_review = get_review(db, user, payload.source_review_id)
        if source_review.status == "PENDING":
            raise HTTPException(409, "Resolve the review before linked resubmission")
    started = time.perf_counter()
    policy, version, document = load_active_policy(db, user)
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
    if payload.source_review_id:
        result["source_review_id"] = payload.source_review_id
    result["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
    metadata = json.loads(json.dumps(result))
    metadata.pop("safe_response", None)
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
    db.add(execution)
    db.flush()
    result["request_id"] = execution.id
    record_audit_event(db, user, f"governance.{operation}.{result['decision']}", execution.id)
    if result["decision"] == "HUMAN_REVIEW":
        review = Review(tenant=user.tenant, execution_id=execution.id)
        db.add(review)
        db.flush()
        result["review_id"] = review.id
    # Synchronous database work cannot be cancelled by asyncio; check elapsed time before release.
    if deadline is not None and time.monotonic() >= deadline:
        raise HTTPException(504, "Governance deadline exceeded; response withheld")
    db.commit()
    if deadline is not None and time.monotonic() >= deadline:
        raise HTTPException(504, "Governance deadline exceeded after persistence; inspect history before retrying")
    return result


async def governance(operation: str, payload: TextRequest, db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Developer", "Policy Owner")
    # Quotas include inspections because live moderation is also a paid dependency.
    load_active_policy(db, user)
    identifier = usage.reserve(db, user)
    providers.generation_usage.set(None)
    state = "FAILED"
    try:
        async with asyncio.timeout(settings.inference_deadline):
            result = await governed_execution(operation, payload, db, user, time.monotonic() + settings.inference_deadline)
        state = result["generation_status"] if operation == "generate" else "INSPECTED"
        return result
    except TimeoutError:
        db.rollback()
        raise HTTPException(504, "Governance deadline exceeded; response withheld") from None
    finally:
        db.rollback()
        usage.finish(db, identifier, state, providers.generation_usage.get())


@app.get("/api/usage")
def inference_usage(db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Auditor")
    return usage.summary(db, user)


@app.post("/api/policies/{policy_id}/rollback")
def rollback_policy(policy_id: str, payload: RollbackRequest, db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Policy Owner")
    policy = get_policy(db, user, policy_id)
    if policy.status == "ARCHIVED":
        raise HTTPException(409, "Archived policies cannot be rolled back")
    version = db.scalar(
        select(Version).where(Version.policy_id == policy_id, Version.tenant == user.tenant, Version.number == payload.version)
    )
    if not version:
        raise HTTPException(404, "Eligible published version not found")
    document = PolicyDocument.model_validate_json(version.document)
    policy.draft, policy.name, policy.status = document.model_dump_json(), document.name, "DRAFT"
    policy.revision += 1
    record_audit_event(db, user, "policy.rollback.DRAFT_REAPPROVAL_REQUIRED", policy.id)
    db.flush()
    return policy_details(db, user, policy)


# Retrieve execution metadata without raw content.
@app.get("/api/audit/executions")
def executions(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = DB, user: Identity = USER):
    return list_records(db, user, Execution, offset, limit)


# Retrieve append-only policy and enforcement events.
@app.get("/api/audit/events")
def audit_events(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    category: str = Query("all", pattern="^(all|policy|governance|administration)$"),
    db: Session = DB,
    user: Identity = USER,
):
    query = select(Audit).where(Audit.tenant == user.tenant)
    if category in ("policy", "governance"):
        query = query.where(Audit.action.startswith(category + "."))
    elif category == "administration":
        query = query.where(~Audit.action.startswith("policy."), ~Audit.action.startswith("governance."))
    return [serialize(row) for row in db.scalars(query.order_by(Audit.created.desc(), Audit.id).offset(offset).limit(limit))]


# Calculate analytics from persisted tenant executions, never seeded counters.
@app.get("/api/audit/summary")
@app.get("/api/analytics/overview")
@app.get("/api/analytics/violations")
@app.get("/api/analytics/compliance")
def analytics(db: Session = DB, user: Identity = USER, start_date: str | None = None, end_date: str | None = None):
    return analytics_service.overview(db, user, start_date, end_date)


# List metadata-only review cases.
@app.get("/api/reviews")
def reviews(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Reviewer", "Auditor", "Developer", "Policy Owner")
    if user.role in ("Developer", "Policy Owner"):
        return [
            serialize(row)
            for row in db.scalars(
                select(Review)
                .join(Execution, Review.execution_id == Execution.id)
                .where(Review.tenant == user.tenant, Execution.tenant == user.tenant, Execution.actor == user.user)
                .order_by(Review.created.desc(), Review.id)
                .offset(offset)
                .limit(limit)
            )
        ]
    return list_records(db, user, Review, offset, limit)


# Resolve a review inside the authenticated tenant.
def get_review(db: Session, user: Identity, review_id: str):
    require_role(user, "Admin", "Reviewer", "Auditor", "Developer", "Policy Owner")
    review = db.scalar(select(Review).where(Review.id == review_id, Review.tenant == user.tenant))
    if not review:
        raise HTTPException(404, "Review not found")
    if user.role in ("Developer", "Policy Owner"):
        execution = db.get(Execution, review.execution_id)
        if not execution or execution.actor != user.user:
            raise HTTPException(404, "Review not found")
    return review


# Read review metadata without retrieving original held content.
@app.get("/api/reviews/{review_id}")
def review_detail(review_id: str, db: Session = DB, user: Identity = USER):
    review = get_review(db, user, review_id)
    return {
        **serialize(review),
        "execution": serialize(db.get(Execution, review.execution_id)),
        "assignment": serialize(db.get(ReviewAssignment, review_id)) if db.get(ReviewAssignment, review_id) else None,
        "decision_history": [
            serialize(note)
            for note in db.scalars(
                select(ReviewNote)
                .where(ReviewNote.review_id == review_id, ReviewNote.tenant == user.tenant)
                .order_by(ReviewNote.created, ReviewNote.id)
            )
        ],
        "instruction": "Original content is not stored. Submit revised text through the playground; all current gates run again.",
    }


def sanitize_review_reason(reason: str) -> str:
    if not reason:
        return ""
    policy = PolicyDocument(name="Review metadata protection")
    try:
        spans = detect_sensitive_information(reason, "secret_detection", policy)
        spans += detect_sensitive_information(reason, "pii_detection", policy)
        return redact_personal_information(reason, spans)[:1000]
    except Exception:
        raise HTTPException(503, "Review metadata inspection unavailable") from None


# Record disposition only; approval never releases content or bypasses revalidation.
def resolve_review(review_id: str, operation: str, db: Session = DB, user: Identity = USER, reason: str = ""):
    require_role(user, "Admin", "Reviewer")
    review = get_review(db, user, review_id)
    if operation not in ("approve", "reject"):
        raise HTTPException(404, "Unknown review action")
    if review.status != "PENDING":
        raise HTTPException(409, "Review already resolved")
    assignment = db.get(ReviewAssignment, review_id)
    if assignment and assignment.assigned_reviewer and assignment.assigned_reviewer != user.user and user.role != "Admin":
        raise HTTPException(403, "This case is assigned to another reviewer")
    reason = sanitize_review_reason(reason)
    db.add(ReviewNote(review_id=review_id, tenant=user.tenant, actor=user.user, action=operation, reason=reason))
    review.status = "APPROVED_RESUBMIT_REQUIRED" if operation == "approve" else "REJECTED"
    record_audit_event(db, user, f"review.{operation}", review.id)
    db.flush()
    return {
        **serialize(review),
        "instruction": "Submit revised content through all current policy gates. No content is released by review.",
    }


@app.put("/api/reviews/{review_id}/assignment")
def assign_review(review_id: str, payload: ReviewUpdate, db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Reviewer")
    review = get_review(db, user, review_id)
    if review.status != "PENDING":
        raise HTTPException(409, "Only pending reviews can be assigned")
    if payload.assigned_reviewer:
        accounts = json.loads(settings.demo_accounts_json)
        if not any(
            account["user"] == payload.assigned_reviewer
            and account["tenant"] == user.tenant
            and account["role"] in ("Admin", "Reviewer")
            and account_enabled(account)
            for account in accounts
        ):
            raise HTTPException(422, "Select an enabled reviewer in this tenant")
    assignment = db.get(ReviewAssignment, review_id)
    if user.role != "Admin":
        if assignment and assignment.assigned_reviewer and assignment.assigned_reviewer != user.user:
            raise HTTPException(403, "Only the assigned reviewer or an administrator can reassign this case")
        if not assignment or not assignment.assigned_reviewer:
            if payload.assigned_reviewer != user.user:
                raise HTTPException(403, "Reviewers may claim an unassigned case for themselves")
    if not assignment:
        assignment = ReviewAssignment(id=review_id, tenant=user.tenant)
        db.add(assignment)
    # Invalidate a disposition loaded before a concurrent reassignment.
    review.row_version += 1
    payload.reason = sanitize_review_reason(payload.reason)
    assignment.assigned_reviewer, assignment.reason = payload.assigned_reviewer, payload.reason
    assignment.updated = datetime.now(timezone.utc).isoformat()
    db.add(ReviewNote(review_id=review_id, tenant=user.tenant, actor=user.user, action="assigned", reason=payload.reason))
    record_audit_event(db, user, "review.assigned", review.id)
    return {"review_id": review.id, **payload.model_dump()}


# Store bounded numeric feedback, checking the referenced execution tenant.
@app.post("/api/feedback", status_code=201)
def collect_feedback(payload: FeedbackRequest, db: Session = DB, user: Identity = USER):
    execution = db.scalar(select(Execution).where(Execution.id == payload.execution_id, Execution.tenant == user.tenant))
    if not execution:
        raise HTTPException(404, "Execution not found")
    prior = db.scalar(
        select(Feedback.id)
        .join(Audit, Audit.resource == Feedback.id)
        .where(
            Feedback.tenant == user.tenant,
            Feedback.execution_id == payload.execution_id,
            Audit.tenant == user.tenant,
            Audit.actor == user.user,
            Audit.action == "feedback.created",
        )
        .limit(1)
    )
    if prior:
        raise HTTPException(409, "You have already submitted feedback for this execution")
    usage.claim_action(db, user, "feedback:" + payload.execution_id, 1, once=True)
    feedback = Feedback(tenant=user.tenant, **payload.model_dump())
    db.add(feedback)
    db.flush()
    record_audit_event(db, user, "feedback.created", feedback.id)
    return serialize(feedback)


# Aggregate feedback for the current tenant.
@app.get("/api/feedback/summary")
def feedback_summary(db: Session = DB, user: Identity = USER):
    return {
        "count": db.scalar(select(func.count()).select_from(Feedback).where(Feedback.tenant == user.tenant)),
        "average": db.scalar(select(func.avg(cast(Feedback.rating, Float))).where(Feedback.tenant == user.tenant)),
    }


# Export an explicit allowlist of non-content fields to an existing ADLS filesystem.
@app.post("/api/reports/export", status_code=201)
def export_sanitized_report(payload: ExportRequest, db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Auditor")
    return exports.create(db, user, payload)


@app.post("/api/reports/exports/{export_id}/reconcile")
def reconcile_export(export_id: str, db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Auditor")
    return exports.process(db, user, export_id, reconcile=True)


# List actual export attempts and their accurate outcomes.
@app.get("/api/reports/exports")
def report_exports(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Auditor")
    return [
        exports.public_report(db, report)
        for report in db.scalars(
            select(Export).where(Export.tenant == user.tenant).order_by(Export.created.desc(), Export.id).offset(offset).limit(limit)
        )
    ]


@app.get("/api/maintenance")
def maintenance_status(db: Session = DB, user: Identity = USER):
    require_role(user, "Admin")
    from .maintenance import plan

    return plan(db, user.tenant)


@app.get("/api/capabilities")
def capabilities(user: Identity = USER):
    from typing import get_args
    from .schemas import PIIEntity, ModerationCategory
    from .engine import get_pii_analyzer

    available = {"EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "US_SSN"}
    detector_status = "AVAILABLE"
    if settings.pii_mode == "presidio":
        try:
            available.update(get_pii_analyzer().get_supported_entities(language="en"))
        except Exception:
            detector_status = "UNAVAILABLE"
            available.clear()
    return {
        "pii_entities": list(get_args(PIIEntity)),
        "available_pii_entities": sorted(available),
        "pii_status": detector_status,
        "moderation_categories": list(get_args(ModerationCategory)),
    }


# Expose configuration presence only; connectivity is not inferred from credentials.
@app.get("/api/settings")
def diagnostics(db: Session = DB, user: Identity = USER):
    db.execute(text("SELECT 1"))
    return {
        "authentication": "Expiring restricted demo sessions and provisioned demo credentials; not enterprise identity",
        "build_version": settings.build_version,
        "release": release_information(),
        "api_contract": "1.2",
        "required_migration": app_schema_revision,
        "migration_status": "READINESS_ENFORCED" if db.bind.dialect.name == "mssql" else "LOCAL_SCHEMA",
        "database_migration": db.execute(text("SELECT version_num FROM alembic_version")).scalar()
        if db.bind.dialect.name == "mssql"
        else "DISPOSABLE_OR_MANUALLY_VERSIONED_SQLITE",
        "demo_session_minutes": settings.demo_session_minutes,
        "legacy_api_credentials": settings.allow_legacy_api_credentials,
        "retention_days": settings.retention_days,
        "database": db.bind.dialect.name,
        "database_status": "CONNECTED",
        "provider_mode": settings.provider_mode,
        "pii_mode": settings.pii_mode,
        "azure_generation": "CONFIGURED_NOT_VERIFIED" if settings.azure_openai_endpoint else "BLOCKED",
        "moderation": "CONFIGURED_NOT_VERIFIED" if settings.openai_api_key else "BLOCKED",
        "adls": "CONFIGURED_NOT_VERIFIED" if settings.adls_account_url else "BLOCKED",
        "role": user.role,
        "tenant": user.tenant,
    }


# Give each documented policy operation its own exact OpenAPI route.
def register_policy_operation(operation: str) -> None:
    # Delegate a specific lifecycle endpoint to the shared transition implementation.
    def policy_operation(policy_id: str, db: Session = DB, user: Identity = USER):
        return transition_policy(policy_id, operation, db, user)

    policy_operation.__name__ = f"{operation}_policy"
    app.add_api_route(f"/api/policies/{{policy_id}}/{operation}", policy_operation, methods=["POST"], response_model=PolicyResponse)


# Give each governance operation a typed and independently discoverable endpoint.
def register_governance_operation(operation: str) -> None:
    # Run the same gateway for the specified inspection or generation operation.
    async def governance_operation(payload: TextRequest, db: Session = DB, user: Identity = USER):
        return await governance(operation, payload, db, user)

    governance_operation.__name__ = operation.replace("-", "_")
    app.add_api_route(f"/api/governance/{operation}", governance_operation, methods=["POST"], response_model=GovernanceResult)


# Expose only supported review dispositions in the REST schema.
def register_review_operation(operation: str) -> None:
    # Resolve the specified review action through the authorization and status gates.
    def review_operation(
        review_id: str, payload: ReviewResolution = Body(default=ReviewResolution()), db: Session = DB, user: Identity = USER
    ):
        return resolve_review(review_id, operation, db, user, payload.reason)

    review_operation.__name__ = f"{operation}_review"
    app.add_api_route(f"/api/reviews/{{review_id}}/{operation}", review_operation, methods=["POST"])


for policy_operation_name in ("submit", "approve", "reject", "publish", "activate", "enable", "disable", "archive"):
    register_policy_operation(policy_operation_name)
for governance_operation_name in ("validate-input", "validate-output", "generate"):
    register_governance_operation(governance_operation_name)
for review_operation_name in ("approve", "reject"):
    register_review_operation(review_operation_name)
