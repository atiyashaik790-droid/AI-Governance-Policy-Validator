"""Application composition and compatibility exports; routes retain their original order."""

# Imports retained for existing app.main callers as well as application composition.
# ruff: noqa: F401

import asyncio
import re
from uuid import UUID, uuid4
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
from .protected_reviews import lifespan as protected_review_lifespan
from .routers.protected_reviews import router as protected_reviews_router
from .database import get_database
from .models import Policy, Version, Assignment, Audit, Execution, Review, Feedback, Export
from .schemas import (
    PolicyDocument,
    TextRequest,
    FeedbackRequest,
    ExportRequest,
    GovernanceResult,
    PolicyResponse,
    PolicyListResponse,
    InspectionResult,
    RollbackRequest,
    ReviewUpdate,
    ReviewResolution,
)
from .user_access import UserGovernanceResult
from .security import authenticate, require_role, Identity, account_enabled
from .engine import inspect_text, detect_sensitive_information, redact_personal_information
from . import providers, exports, analytics as analytics_service, usage
from .sessions import router as session_router
from .sso import router as sso_router
from .release import information as release_information
from .models import ReviewAssignment, ReviewNote
from .schema_compatibility import inspect_schema
from .routers.system import app_schema_revision, health, ready, maintenance_status, capabilities, diagnostics
from .routers.integration_verification import router as integration_verification_router
from .middleware import logger, bound_request_size
from .dependencies import DB, USER
from .exception_handlers import database_failure, concurrent_policy_change, invalid_request
from .repositories import record_audit_event, serialize, list_records
from .services.policies import get_policy, load_active_policy, policy_details, transition_policy
from .routers.policies import (
    get_all_policies,
    create_new_policy,
    view_policy,
    update_existing_policy,
    delete_draft_policy,
    simulate_policy,
    policy_versions,
    rollback_policy,
)
from .services.governance import governed_execution, governance
from .routers.governance import inference_usage
from .routers.audit import executions, audit_events, analytics
from .routers.reviews import reviews, review_detail, assign_review
from .services.reviews import get_review, sanitize_review_reason, resolve_review
from .routers.feedback import collect_feedback, feedback_summary
from .routers.reports import export_sanitized_report, reconcile_export, report_exports
from .routers.workspace_v2 import router as workspace_v2_router
from .routers.reporting_v2 import router as reporting_v2_router
from .routers.governance_v2 import router as governance_v2_router
from .routers.document_uploads import router as document_uploads_router
from .routers.categories import router as categories_router
from .routers.simulation_v2 import router as simulation_v2_router
from .chat_history import router as chat_history_router, require_conversation


# Registration is explicit to preserve the exact baseline raw and effective route order.
app = FastAPI(title="AI Governance Policy Validator", version="1.2.0", lifespan=protected_review_lifespan)

app.include_router(session_router)
app.include_router(chat_history_router)

app.include_router(sso_router)
app.include_router(categories_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "If-Match", "X-CSRF-Token"],
    expose_headers=["X-Request-ID", "Retry-After", "ETag", "X-Session-Reason"],
)

app.middleware("http")(bound_request_size)

app.exception_handler(SQLAlchemyError)(database_failure)

app.exception_handler(StaleDataError)(concurrent_policy_change)

app.exception_handler(RequestValidationError)(invalid_request)

app.get("/health")(health)

app.get("/ready")(ready)

app.get("/api/policies", response_model=list[PolicyListResponse])(get_all_policies)

app.post("/api/policies", status_code=201, response_model=PolicyResponse)(create_new_policy)

app.get("/api/policies/{policy_id}", response_model=PolicyResponse)(view_policy)

app.put("/api/policies/{policy_id}", response_model=PolicyResponse)(update_existing_policy)

app.delete("/api/policies/{policy_id}")(delete_draft_policy)

app.post("/api/policies/{policy_id}/simulate", response_model=InspectionResult)(simulate_policy)

app.get("/api/policies/{policy_id}/versions")(policy_versions)

app.get("/api/usage")(inference_usage)

app.post("/api/policies/{policy_id}/rollback")(rollback_policy)

app.get("/api/audit/executions")(executions)

app.get("/api/audit/events")(audit_events)

app.get("/api/analytics/compliance")(analytics)

app.get("/api/analytics/violations")(analytics)

app.get("/api/analytics/overview")(analytics)

app.get("/api/audit/summary")(analytics)

app.get("/api/reviews")(reviews)

app.get("/api/reviews/{review_id}")(review_detail)

app.put("/api/reviews/{review_id}/assignment")(assign_review)

app.post("/api/feedback", status_code=201)(collect_feedback)

app.get("/api/feedback/summary")(feedback_summary)

app.post("/api/reports/export", status_code=201)(export_sanitized_report)

app.post("/api/reports/exports/{export_id}/reconcile")(reconcile_export)

app.get("/api/reports/exports")(report_exports)

app.get("/api/maintenance")(maintenance_status)

app.get("/api/capabilities")(capabilities)

app.get("/api/settings")(diagnostics)

app.include_router(integration_verification_router)


def register_policy_operation(operation: str) -> None:
    # Delegate a specific lifecycle endpoint to the shared transition implementation.
    def policy_operation(policy_id: str, db: Session = DB, user: Identity = USER):
        return transition_policy(policy_id, operation, db, user)

    policy_operation.__name__ = f"{operation}_policy"
    app.add_api_route(f"/api/policies/{{policy_id}}/{operation}", policy_operation, methods=["POST"], response_model=PolicyResponse)


def register_governance_operation(operation: str) -> None:
    # Run the same gateway for the specified inspection or generation operation.
    async def governance_operation(payload: TextRequest, db: Session = DB, user: Identity = USER):
        if payload.conversation_id:
            require_conversation(db, user, payload.conversation_id)
        return await governance(operation, payload, db, user)

    governance_operation.__name__ = operation.replace("-", "_")
    app.add_api_route(f"/api/governance/{operation}", governance_operation, methods=["POST"], response_model=GovernanceResult | UserGovernanceResult)


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

app.include_router(workspace_v2_router)
app.include_router(reporting_v2_router)
app.include_router(governance_v2_router)
app.include_router(simulation_v2_router)
app.include_router(document_uploads_router)
app.include_router(protected_reviews_router)
