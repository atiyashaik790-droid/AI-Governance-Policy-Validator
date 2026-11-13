"""Least-privileged chatbot access and response allowlist; other roles unchanged."""
from fastapi import HTTPException
from .schemas import Action, DecisionNotice, StrictModel, AttachmentMetadata

KNOWN_ROLES = {"Admin", "User", "Developer", "Reviewer", "Auditor", "Policy Owner"}
USER_ENDPOINTS = {
    ("GET", "/api/sso/me"), ("POST", "/api/sso/logout"),
    ("POST", "/api/auth/session"), ("GET", "/api/auth/me"), ("POST", "/api/auth/logout"),
    ("GET", "/api/v2/workspace/policy-state"),
    ("GET", "/api/chat/conversations"), ("POST", "/api/chat/conversations"),
    ("GET", "/api/chat/conversations/{conversation_id}"),
    *(("POST", prefix + "/governance/" + operation)
      for prefix in ("/api", "/api/v2") for operation in ("generate", "generate-document")),
}


def authorize(request, user):
    if user.role not in KNOWN_ROLES or not user.user.strip() or not user.tenant.strip():
        raise HTTPException(403, "Authorized membership is required")
    path = request.scope.get("route")
    path = path.path if path is not None else request.url.path
    if user.role == "User" and (request.method, path) not in USER_ENDPOINTS:
        raise HTTPException(403, "User access is limited to the chatbot and its governed requests")
    return user


class UserInspection(StrictModel):
    decision: Action
    revalidated: bool = False
    inspection_status: str | None = None


class UserGovernanceResult(StrictModel):
    decision: Action
    decision_notice: DecisionNotice | None = None
    input: UserInspection | None = None
    output: UserInspection | None = None
    safe_response: str | None = None
    model_invoked: bool
    generation_status: str
    request_id: str
    review_id: str | None = None
    attachment: AttachmentMetadata | None = None


def public_result(result, user):
    if user.role != "User":
        return result
    value = {key: result[key] for key in UserGovernanceResult.model_fields if key in result}
    for name in ("input", "output"):
        stage = result.get(name)
        value[name] = {key: stage[key] for key in UserInspection.model_fields if key in stage} if isinstance(stage, dict) else None
    return UserGovernanceResult.model_validate(value).model_dump()
