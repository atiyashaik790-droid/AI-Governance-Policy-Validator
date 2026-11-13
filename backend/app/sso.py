"""Single-tenant Entra OIDC. Microsoft tokens never cross the backend boundary."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit
from uuid import UUID

from httpx import AsyncClient as HttpClient
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.oidc.core import CodeIDToken
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from joserfc import jwt
from joserfc.jwk import KeySet
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .config import settings
from .database import get_database
from .models import Audit, SsoMembership, SsoSession, SsoTransaction, now

router = APIRouter(prefix="/api/sso", tags=["Microsoft sign-in"])
COOKIE = "__Host-governance-session"
TRANSACTION_COOKIE = "__Host-governance-oidc"
ROLES = {"User", "Admin", "Developer", "Reviewer", "Auditor", "Policy Owner"}


def sso_database(db: Session = Depends(get_database, scope="function")):
    from .schema_compatibility import inspect_schema

    inspect_schema(db, require_sso=True)
    return db


DB = Depends(sso_database)
# Authenticated handlers already check the full contract in cookie_identity.
AUTH_DB = Depends(get_database, scope="function")


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def csrf_token(session_token: str) -> str:
    return hmac.new(session_token.encode(), b"governance-csrf-v1", hashlib.sha256).hexdigest()


def configuration(config=settings) -> tuple[str, str]:
    """Pin authority and callback to reviewed configuration, never Host headers."""
    try:
        tenant = str(UUID(config.entra_tenant_id))
        UUID(config.entra_client_id)
        origin = urlsplit(config.sso_public_origin)
        if (
            not config.sso_enabled
            or not config.entra_client_secret
            or origin.scheme != "https"
            or not origin.hostname
            or origin.username is not None
            or origin.password is not None
            or origin.path
            or origin.query
            or origin.fragment
            or config.sso_public_origin != f"https://{origin.netloc}"
        ):
            raise ValueError
    except (ValueError, TypeError):
        raise HTTPException(503, "Microsoft sign-in is not configured") from None
    return f"https://login.microsoftonline.com/{tenant}/v2.0", config.sso_public_origin + "/api/sso/callback"


def safe_return_path(path: str) -> str:
    # Only existing SPA roots; omit query/hash to avoid reflecting callback secrets.
    roots = {"", "chat", "policies", "simulator", "playground", "history", "reviews", "analytics", "reports", "settings"}
    if (
        len(path) > 500
        or not path.startswith("/")
        or path.startswith("//")
        or any(c in path for c in ("\\", "%", "?", "#"))
        or any(ord(c) < 32 for c in path)
        or any(p in (".", "..") for p in path.split("/"))
        or path.split("/")[1] not in roots
    ):
        raise HTTPException(400, "Invalid return route")
    return path


def expiry(minutes: int) -> str:
    return (datetime.fromisoformat(now()).astimezone(timezone.utc) + timedelta(minutes=minutes)).isoformat()


async def metadata() -> dict:
    issuer, _ = configuration()
    async with HttpClient(timeout=10, follow_redirects=False) as client:
        response = await client.get(issuer + "/.well-known/openid-configuration")
        response.raise_for_status()
        data = response.json()
    if data.get("issuer") != issuer:
        raise ValueError("Untrusted discovery issuer")
    # Only Microsoft's configured tenant authority can receive credentials/codes.
    for key in ("authorization_endpoint", "token_endpoint", "jwks_uri", "end_session_endpoint"):
        parsed = urlsplit(data.get(key, ""))
        if parsed.scheme != "https" or parsed.netloc != "login.microsoftonline.com" or parsed.fragment or parsed.username:
            raise ValueError("Untrusted discovery endpoint")
    return data


async def exchange_code(code: str, transaction: SsoTransaction) -> dict:
    issuer, callback = configuration()
    data = await metadata()
    async with AsyncOAuth2Client(
        client_id=settings.entra_client_id,
        client_secret=settings.entra_client_secret,
        token_endpoint_auth_method="client_secret_post",
        redirect_uri=callback,
        scope="openid profile",
        code_challenge_method="S256",
        timeout=10,
    ) as client:
        token = await client.fetch_token(data["token_endpoint"], code=code, code_verifier=transaction.verifier)
    async with HttpClient(timeout=10, follow_redirects=False) as client:
        response = await client.get(data["jwks_uri"])
        response.raise_for_status()
        keys = KeySet.import_key_set(response.json())
    # Library verifies the signature with an explicit asymmetric algorithm allowlist.
    decoded = jwt.decode(token["id_token"], keys, algorithms=["RS256"])
    claims = CodeIDToken(
        decoded.claims,
        decoded.header,
        options={"iss": {"essential": True, "value": issuer}, "aud": {"essential": True, "value": settings.entra_client_id}},
        params={"nonce": transaction.nonce, "client_id": settings.entra_client_id, "access_token": token.get("access_token")},
    )
    claims.validate(leeway=30)
    if claims.get("tid") != str(UUID(settings.entra_tenant_id)) or not claims.get("sub"):
        raise ValueError("Unauthorized directory")
    UUID(claims["oid"])
    # Access, refresh and ID tokens are discarded. No Graph call or offline_access.
    return dict(claims)


def cookie_identity(request: Request, db: Session):
    """Resolve membership on every request, including immediate disable/role changes."""
    from .security import Identity

    configuration()
    raw = request.cookies.get(COOKIE, "")
    if not raw:
        raise HTTPException(401, "Sign in with Microsoft to continue", headers={"X-Session-Reason": "anonymous"})
    from .schema_compatibility import inspect_schema

    inspect_schema(db, require_sso=True)
    session = db.get(SsoSession, digest(raw)) if raw else None
    membership = db.get(SsoMembership, session.membership_id) if session else None

    def denied(reason):
        return HTTPException(401, "Sign in with Microsoft to continue", headers={"X-Session-Reason": reason})

    if (
        not session
        or session.revoked
        or not membership
        or not membership.enabled
        or membership.role not in ROLES
        or membership.directory_tenant != str(UUID(settings.entra_tenant_id))
    ):
        raise denied("ended")
    try:
        expires = datetime.fromisoformat(session.expires)
        if expires.tzinfo is None:
            raise ValueError()
        expired = expires.astimezone(timezone.utc) <= datetime.fromisoformat(now()).astimezone(timezone.utc)
    except (ValueError, TypeError):
        raise denied("ended") from None
    if expired:
        raise denied("expired")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if request.headers.get("origin") != settings.sso_public_origin or not hmac.compare_digest(
            request.headers.get("x-csrf-token", ""), csrf_token(raw)
        ):
            raise HTTPException(403, "Request verification failed; refresh and try again")
    return Identity(
        membership.actor,
        membership.tenant,
        membership.role,
        "sso:" + session.id,
        directory_tenant=membership.directory_tenant,
        object_id=membership.object_id,
    )


@router.get("/status")
def status(db: Session = Depends(get_database, scope="function")):
    try:
        configuration()
        from .schema_compatibility import inspect_schema

        inspect_schema(db, require_sso=True)
        ready = True
    except HTTPException:
        ready = False
    return {
        "sso_enabled": settings.sso_enabled,
        "configured": ready,
        "demo_login_enabled": settings.demo_browser_login_enabled,
    }


@router.get("/login")
async def login(request: Request, return_to: str = "/", db: Session = DB):
    _, callback = configuration()
    target = safe_return_path(return_to)
    from .security import Identity
    from .usage import claim_action

    # Do not trust forwarded IP headers. This is an application-wide shared bound.
    claim_action(db, Identity("sso-login", "sso-system", ""), "oidc", 120)
    try:
        data = await metadata()
    except Exception:
        raise HTTPException(503, "Microsoft sign-in is temporarily unavailable") from None
    state, binding, nonce, verifier = (secrets.token_urlsafe(48) for _ in range(4))
    async with AsyncOAuth2Client(
        client_id=settings.entra_client_id,
        redirect_uri=callback,
        scope="openid profile",
        code_challenge_method="S256",
    ) as client:
        url, _ = client.create_authorization_url(
            data["authorization_endpoint"],
            state=state,
            nonce=nonce,
            code_verifier=verifier,
            response_mode="query",
        )
    db.add(
        SsoTransaction(
            id=digest(state), binding_hash=digest(binding), nonce=nonce, verifier=verifier, return_path=target, expires=expiry(5)
        )
    )
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(TRANSACTION_COOKIE, binding, max_age=300, secure=True, httponly=True, samesite="lax", path="/")
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/callback")
async def callback(request: Request, db: Session = DB):
    configuration()
    # Consume atomically BEFORE contacting Entra. A failed exchange cannot be replayed.
    state = request.query_params.get("state", "")
    transaction = db.get(SsoTransaction, digest(state)) if state and len(state) < 200 else None
    binding = request.cookies.get(TRANSACTION_COOKIE, "")
    valid = transaction and transaction.expires > now() and hmac.compare_digest(transaction.binding_hash, digest(binding))
    if not valid:
        return failure("authentication_failed")
    claimed = db.execute(update(SsoTransaction).where(SsoTransaction.id == transaction.id, SsoTransaction.consumed == 0).values(consumed=1))
    if claimed.rowcount != 1:
        return failure("authentication_failed")
    db.commit()
    try:
        code = request.query_params.get("code", "")
        if request.query_params.get("error") or not code or len(code) > 8192:
            raise ValueError
        claims = await exchange_code(code, transaction)
        directory, object_id = str(UUID(claims["tid"])), str(UUID(claims["oid"]))
        if directory != str(UUID(settings.entra_tenant_id)):
            raise ValueError
    except Exception:
        # Never reflect provider error text, authorization codes or token values.
        return failure("authentication_failed")
    membership = db.scalar(
        select(SsoMembership).where(
            SsoMembership.directory_tenant == directory,
            SsoMembership.object_id == object_id,
            SsoMembership.enabled == 1,
        )
    )
    if not membership or membership.role not in ROLES:
        return failure("access_denied")
    raw = secrets.token_urlsafe(48)
    expires = expiry(settings.sso_session_minutes)
    db.add(SsoSession(id=digest(raw), membership_id=membership.id, expires=expires))
    # Rotate any existing session when a successful fresh login completes.
    old = request.cookies.get(COOKIE)
    if old:
        db.execute(update(SsoSession).where(SsoSession.id == digest(old)).values(revoked=1))
    db.add(Audit(tenant=membership.tenant, actor=membership.actor, actor_role=membership.role, action="sso.session.created", resource=membership.id))
    response = RedirectResponse(settings.sso_public_origin + transaction.return_path, status_code=303)
    response.set_cookie(
        COOKIE,
        raw,
        max_age=settings.sso_session_minutes * 60,
        expires=datetime.fromisoformat(expires),
        secure=True,
        httponly=True,
        samesite="lax",
        path="/",
    )
    response.delete_cookie(TRANSACTION_COOKIE, secure=True, httponly=True, samesite="lax", path="/")
    response.headers["Cache-Control"] = "no-store"
    return response


def failure(reason: str):
    response = RedirectResponse(settings.sso_public_origin + "/?auth_error=" + reason, status_code=303)
    response.delete_cookie(TRANSACTION_COOKIE, secure=True, httponly=True, samesite="lax", path="/")
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/me")
def me(request: Request, db: Session = AUTH_DB):
    user = cookie_identity(request, db)
    session = db.get(SsoSession, user.session_id.removeprefix("sso:"))
    return JSONResponse(
        {
            "user": user.user,
            "tenant": user.tenant,
            "role": user.role,
            "csrf_token": csrf_token(request.cookies[COOKIE]),
            "expires_at": session.expires,
            "server_now": now(),
        },
        headers={"Cache-Control": "no-store"},
    )


@router.post("/logout")
def logout(request: Request, db: Session = AUTH_DB):
    user = cookie_identity(request, db)
    db.execute(update(SsoSession).where(SsoSession.id == user.session_id.removeprefix("sso:")).values(revoked=1))
    db.add(Audit(tenant=user.tenant, actor=user.user, actor_role=user.role, action="sso.session.revoked", resource="browser"))
    issuer, _ = configuration()
    # Local session is revoked before the browser is sent to Microsoft's sign-out.
    url = issuer.removesuffix("/v2.0") + "/oauth2/v2.0/logout?" + urlencode({"post_logout_redirect_uri": settings.sso_public_origin + "/"})
    response = JSONResponse({"logout_url": url}, headers={"Cache-Control": "no-store"})
    response.delete_cookie(COOKIE, secure=True, httponly=True, samesite="lax", path="/")
    return response


@router.get("/sessions")
def sessions(request: Request, offset: int = 0, limit: int = 20, db: Session = AUTH_DB):
    from .security import require_role

    user = cookie_identity(request, db)
    require_role(user, "Admin")
    if offset < 0 or not 1 <= limit <= 100:
        raise HTTPException(422, "Invalid pagination")
    rows = db.execute(
        select(SsoSession, SsoMembership.actor)
        .join(SsoMembership)
        .where(
            SsoMembership.tenant == user.tenant,
        )
        .order_by(SsoSession.expires.desc(), SsoSession.id)
        .offset(offset)
        .limit(limit)
    )
    return [
        {"id": row.id, "actor": actor, "expires": row.expires, "revoked": bool(row.revoked), "expired": row.expires <= now()}
        for row, actor in rows
    ]


@router.post("/sessions/{session_id}/revoke")
def revoke_session(session_id: str, request: Request, db: Session = AUTH_DB):
    from .security import require_role

    user = cookie_identity(request, db)
    require_role(user, "Admin")
    row = db.scalar(select(SsoSession).join(SsoMembership).where(SsoSession.id == session_id, SsoMembership.tenant == user.tenant))
    if not row:
        raise HTTPException(404, "Session not found")
    row.revoked = 1
    db.add(Audit(tenant=user.tenant, actor=user.user, actor_role=user.role, action="sso.session.revoked", resource=session_id[:12]))
    return {"status": "revoked"}
