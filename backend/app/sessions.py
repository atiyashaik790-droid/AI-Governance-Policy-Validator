"""Restricted demo credential exchange; not an enterprise identity provider."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from .config import settings
from .database import get_database
from .models import DemoSession, Audit, now
from .security import Identity, authenticate, require_role
from .usage import claim_action


def require_demo_login_enabled():
    if not settings.demo_browser_login_enabled:
        raise HTTPException(403, "Demonstration authentication is disabled")


router = APIRouter(prefix="/api/auth", tags=["restricted demo sessions"], dependencies=[Depends(require_demo_login_enabled)])
DB = Depends(get_database, scope="function")
USER = Depends(authenticate)


@router.post("/session", status_code=201)
def exchange(request: Request, db: Session = DB, user: Identity = USER):
    if user.session_id:
        raise HTTPException(409, "Use the provisioned demo credential to start a new session")
    claim_action(db, user, "session", settings.session_per_minute)
    token = secrets.token_urlsafe(48)
    digest = hashlib.sha256(token.encode()).hexdigest()
    unlimited_local = (
        settings.demo_session_unlimited_local
        and db.bind.dialect.name == "sqlite"
        and request.client is not None
        and request.client.host in {"127.0.0.1", "::1"}
    )
    expires = (
        "9999-12-31T23:59:59+00:00"
        if unlimited_local
        else (datetime.now(timezone.utc) + timedelta(minutes=settings.demo_session_minutes)).isoformat()
    )
    db.add(
        DemoSession(id=digest, tenant=user.tenant, actor=user.user, role=user.role, credential_hash=user.credential_hash, expires=expires)
    )
    db.add(Audit(tenant=user.tenant, actor=user.user, actor_role=user.role, action="session.created", resource=digest[:12]))
    return {"access_token": token, "expires": expires, "authentication": "Restricted demo session; not enterprise SSO"}


@router.get("/me")
def demo_identity(user: Identity = USER):
    if not user.session_id:
        raise HTTPException(401, "Exchange the provisioned credential for a demo session")
    return {"user": user.user, "tenant": user.tenant, "role": user.role,
            "csrf_token": "demo-bearer-session", "expires_at": None, "server_now": now()}


@router.post("/logout")
def logout(db: Session = DB, user: Identity = USER):
    if not user.session_id:
        raise HTTPException(409, "Sign in through a demo session before logout; provisioned credentials require operator revocation")
    db.execute(update(DemoSession).where(DemoSession.id == user.session_id, DemoSession.tenant == user.tenant).values(revoked=1))
    db.add(Audit(tenant=user.tenant, actor=user.user, actor_role=user.role, action="session.revoked", resource=user.session_id[:12]))
    return {"status": "revoked"}


@router.get("/sessions")
def sessions(offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), db: Session = DB, user: Identity = USER):
    require_role(user, "Admin")
    rows = db.scalars(
        select(DemoSession)
        .where(DemoSession.tenant == user.tenant)
        .order_by(DemoSession.created.desc(), DemoSession.id)
        .offset(offset)
        .limit(limit)
    )
    return [
        {"id": row.id, "actor": row.actor, "expires": row.expires, "revoked": bool(row.revoked), "expired": row.expires <= now()}
        for row in rows
    ]


@router.post("/sessions/{session_id}/revoke")
def revoke(session_id: str, db: Session = DB, user: Identity = USER):
    require_role(user, "Admin")
    result = db.execute(update(DemoSession).where(DemoSession.id == session_id, DemoSession.tenant == user.tenant).values(revoked=1))
    if result.rowcount != 1:
        raise HTTPException(404, "Session not found")
    db.add(Audit(tenant=user.tenant, actor=user.user, actor_role=user.role, action="session.revoked", resource=session_id[:12]))
    return {"status": "revoked"}
