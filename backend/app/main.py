"""Tenant-scoped API and governance gateway."""

import csv
import io
import json
import logging
import time
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, func, text, cast, Float
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from .config import settings
from .database import get_database
from .models import Policy, Version, Assignment, Audit, Execution, Review, Feedback, Export
from .schemas import PolicyDocument, TextRequest, FeedbackRequest, ExportRequest, GovernanceResult, PolicyResponse, InspectionResult
from .security import authenticate, require_role, Identity
from .engine import inspect_text
from . import providers

logger = logging.getLogger("governance.http")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
logger.propagate = False

app = FastAPI(title="AI Governance Policy Validator", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
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
    response = await call_next(request)
    logger.info(
        json.dumps(
            {
                "event": "http.completed",
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
def get_policy(db: Session, user: Identity, policy_id: str) -> Policy:
    policy = db.scalar(select(Policy).where(Policy.id == policy_id, Policy.tenant == user.tenant))
    if not policy:
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
    if not policy or not policy.enabled or policy.status == "ARCHIVED":
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
    return {"status": "ready", "provider_mode": settings.provider_mode}


# List real policies, scoped to the authenticated tenant.
@app.get("/api/policies", response_model=list[PolicyResponse])
def get_all_policies(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = DB, user: Identity = USER):
    return list_records(db, user, Policy, offset, limit)


# Validate and persist a new editable policy document.
@app.post("/api/policies", status_code=201, response_model=PolicyResponse)
def create_new_policy(document: PolicyDocument, db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Policy Owner")
    policy = Policy(tenant=user.tenant, name=document.name, draft=document.model_dump_json())
    db.add(policy)
    db.flush()
    record_audit_event(db, user, "policy.created", policy.id)
    return serialize(policy)


# Read the current draft and lifecycle status.
@app.get("/api/policies/{policy_id}", response_model=PolicyResponse)
def view_policy(policy_id: str, db: Session = DB, user: Identity = USER):
    return serialize(get_policy(db, user, policy_id))


# Editing leaves historical versions intact and invalidates all draft approvals.
@app.put("/api/policies/{policy_id}", response_model=PolicyResponse)
def update_existing_policy(policy_id: str, document: PolicyDocument, db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Policy Owner")
    policy = get_policy(db, user, policy_id)
    if policy.status == "ARCHIVED":
        raise HTTPException(409, "Archived policy cannot be edited")
    policy.draft, policy.name, policy.status = document.model_dump_json(), document.name, "DRAFT"
    policy.revision += 1
    record_audit_event(db, user, "policy.draft_updated", policy.id)
    db.flush()
    return serialize(policy)


# Delete drafts only; retain any published policy for auditability.
@app.delete("/api/policies/{policy_id}")
def delete_draft_policy(policy_id: str, db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Policy Owner")
    policy = get_policy(db, user, policy_id)
    versions = db.scalar(select(func.count()).select_from(Version).where(Version.policy_id == policy_id))
    if versions or policy.status != "DRAFT":
        raise HTTPException(409, "Only never-published drafts can be deleted")
    record_audit_event(db, user, "policy.deleted", policy.id)
    db.delete(policy)
    return {"deleted": True}


# Simulate the actual draft engine without publishing or invoking generation.
@app.post("/api/policies/{policy_id}/simulate", response_model=InspectionResult)
async def simulate_policy(policy_id: str, payload: TextRequest, db: Session = DB, user: Identity = USER):
    policy = get_policy(db, user, policy_id)
    result = await inspect_text(payload.text, PolicyDocument.model_validate_json(policy.draft))
    record_audit_event(db, user, "policy.simulated", policy_id)
    return result


# Apply explicit lifecycle transitions under backend authorization.
def transition_policy(policy_id: str, operation: str, db: Session = DB, user: Identity = USER):
    policy = get_policy(db, user, policy_id)
    if operation == "approve":
        require_role(user, "Admin", "Reviewer")
    else:
        require_role(user, "Admin", "Policy Owner")
    if operation in ("submit", "approve", "publish"):
        expected = {"submit": "DRAFT", "approve": "SUBMITTED", "publish": "APPROVED"}[operation]
        if policy.status != expected:
            raise HTTPException(409, f"{operation} requires {expected}")
        PolicyDocument.model_validate_json(policy.draft)
        policy.status = {"submit": "SUBMITTED", "approve": "APPROVED", "publish": "PUBLISHED"}[operation]
        if operation == "publish":
            number = (db.scalar(select(func.max(Version.number)).where(Version.policy_id == policy_id)) or 0) + 1
            db.add(Version(policy_id=policy_id, tenant=user.tenant, number=number, document=policy.draft))
    elif operation == "activate":
        version = db.scalar(
            select(Version).where(Version.policy_id == policy_id, Version.tenant == user.tenant).order_by(Version.number.desc())
        )
        if not version or not policy.enabled or policy.status != "PUBLISHED":
            raise HTTPException(409, "Activation requires enabled published policy")
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
    return serialize(policy)


# Return immutable published versions in newest-first order.
@app.get("/api/policies/{policy_id}/versions")
def policy_versions(
    policy_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = DB, user: Identity = USER
):
    get_policy(db, user, policy_id)
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
async def governance(operation: str, payload: TextRequest, db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Developer", "Policy Owner")
    if operation not in ("generate", "validate-input", "validate-output"):
        raise HTTPException(404, "Unknown governance operation")
    started = time.perf_counter()
    policy, version, document = load_active_policy(db, user)
    inspected = await inspect_text(payload.text, document)
    result = {
        "input": inspected if operation != "validate-output" else None,
        "output": inspected if operation == "validate-output" else None,
        "decision": inspected["decision"],
        "safe_response": None,
        "model_invoked": False,
        "provider_mode": settings.provider_mode,
        "policy_id": policy.id,
        "policy_version": version.number,
    }
    if operation == "generate" and inspected["decision"] in ("ALLOW", "REDACT"):
        try:
            result["model_invoked"] = True
            generated = await providers.generate_ai_response(inspected["safe_text"])
            output = await inspect_text(generated, document)
            result["output"] = output
            result["decision"] = "REDACT" if inspected["decision"] == "REDACT" and output["decision"] == "ALLOW" else output["decision"]
            if output["decision"] in ("ALLOW", "REDACT"):
                result["safe_response"] = output["safe_text"]
        except providers.ProviderUnavailable:
            result["decision"] = "BLOCK"
            result["provider_error"] = "Generation unavailable; response withheld"
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
    # Commit audit persistence before returning any content to the caller.
    db.commit()
    return result


# Retrieve execution metadata without raw content.
@app.get("/api/audit/executions")
def executions(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = DB, user: Identity = USER):
    return list_records(db, user, Execution, offset, limit)


# Retrieve append-only policy and enforcement events.
@app.get("/api/audit/events")
def audit_events(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = DB, user: Identity = USER):
    return list_records(db, user, Audit, offset, limit)


# Calculate analytics from persisted tenant executions, never seeded counters.
@app.get("/api/audit/summary")
@app.get("/api/analytics/overview")
@app.get("/api/analytics/violations")
@app.get("/api/analytics/compliance")
def analytics(db: Session = DB, user: Identity = USER):
    rows = db.scalars(select(Execution).where(Execution.tenant == user.tenant)).all()
    decisions = {key: sum(row.decision == key for row in rows) for key in ("ALLOW", "REDACT", "BLOCK", "HUMAN_REVIEW")}
    breakdown, trends, violations = {}, [], {}
    for row in rows:
        metadata = json.loads(row.metadata_json)
        stage = metadata.get("output") or metadata.get("input")
        if stage:
            trends.append({"date": row.created[:10], "score": stage["score"]})
            for category, status in stage["breakdown"].items():
                breakdown[category] = breakdown.get(category, 0) + stage["contributions"][category]
                if status in ("FAILED", "UNKNOWN"):
                    violations[category] = violations.get(category, 0) + 1
    assignment = db.get(Assignment, user.tenant)
    active = db.get(Version, assignment.version_id) if assignment else None
    active_policy = db.get(Policy, active.policy_id) if active else None
    return {
        "total_policies": db.scalar(select(func.count()).select_from(Policy).where(Policy.tenant == user.tenant)),
        "active_policies": int(bool(active_policy and active_policy.enabled)),
        "total_validations": len(rows),
        "decisions": decisions,
        "trends": trends[-100:],
        "violations": violations,
        "contributions": breakdown,
        "active_policy": {"id": active.policy_id, "version": active.number} if active else None,
        "pending_reviews": db.scalar(
            select(func.count()).select_from(Review).where(Review.tenant == user.tenant, Review.status == "PENDING")
        ),
    }


# List metadata-only review cases.
@app.get("/api/reviews")
def reviews(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Reviewer", "Auditor")
    return list_records(db, user, Review, offset, limit)


# Resolve a review inside the authenticated tenant.
def get_review(db: Session, user: Identity, review_id: str):
    require_role(user, "Admin", "Reviewer", "Auditor")
    review = db.scalar(select(Review).where(Review.id == review_id, Review.tenant == user.tenant))
    if not review:
        raise HTTPException(404, "Review not found")
    return review


# Read review metadata without retrieving original held content.
@app.get("/api/reviews/{review_id}")
def review_detail(review_id: str, db: Session = DB, user: Identity = USER):
    review = get_review(db, user, review_id)
    return {**serialize(review), "execution": serialize(db.get(Execution, review.execution_id))}


# Record disposition only; approval never releases content or bypasses revalidation.
def resolve_review(review_id: str, operation: str, db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Reviewer")
    review = get_review(db, user, review_id)
    if operation not in ("approve", "reject"):
        raise HTTPException(404, "Unknown review action")
    if review.status != "PENDING":
        raise HTTPException(409, "Review already resolved")
    review.status = "APPROVED_RESUBMIT_REQUIRED" if operation == "approve" else "REJECTED"
    record_audit_event(db, user, f"review.{operation}", review.id)
    db.flush()
    return {
        **serialize(review),
        "instruction": "Submit revised content through all current policy gates. No content is released by review.",
    }


# Store bounded numeric feedback, checking the referenced execution tenant.
@app.post("/api/feedback", status_code=201)
def collect_feedback(payload: FeedbackRequest, db: Session = DB, user: Identity = USER):
    execution = db.scalar(select(Execution).where(Execution.id == payload.execution_id, Execution.tenant == user.tenant))
    if not execution:
        raise HTTPException(404, "Execution not found")
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
    report = Export(tenant=user.tenant)
    db.add(report)
    db.flush()
    rows = [
        {"request_id": row.id, "timestamp": row.created, "decision": row.decision, "policy_id": row.policy_id, "version": row.version}
        for row in db.scalars(select(Execution).where(Execution.tenant == user.tenant))
    ]
    if payload.format == "json":
        content = json.dumps(rows)
    else:
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=["request_id", "timestamp", "decision", "policy_id", "version"])
        writer.writeheader()
        writer.writerows(rows)
        content = stream.getvalue()
    report.path = f"governance-reports/{datetime.now(timezone.utc):%Y/%m/%d}/{report.id}.{payload.format}"
    try:
        providers.upload_report(report.path, content)
        report.status = "SUCCEEDED"
    except Exception:
        report.status = "FAILED"
    record_audit_event(db, user, f"report.{report.status}", report.id)
    return serialize(report)


# List actual export attempts and their accurate outcomes.
@app.get("/api/reports/exports")
def report_exports(offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Auditor")
    return list_records(db, user, Export, offset, limit)


# Expose configuration presence only; connectivity is not inferred from credentials.
@app.get("/api/settings")
def diagnostics(db: Session = DB, user: Identity = USER):
    db.execute(text("SELECT 1"))
    return {
        "authentication": "Local demonstration tokens; not enterprise identity",
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
    def review_operation(review_id: str, db: Session = DB, user: Identity = USER):
        return resolve_review(review_id, operation, db, user)

    review_operation.__name__ = f"{operation}_review"
    app.add_api_route(f"/api/reviews/{{review_id}}/{operation}", review_operation, methods=["POST"])


for policy_operation_name in ("submit", "approve", "publish", "activate", "enable", "disable", "archive"):
    register_policy_operation(policy_operation_name)
for governance_operation_name in ("validate-input", "validate-output", "generate"):
    register_governance_operation(governance_operation_name)
for review_operation_name in ("approve", "reject"):
    register_review_operation(review_operation_name)
