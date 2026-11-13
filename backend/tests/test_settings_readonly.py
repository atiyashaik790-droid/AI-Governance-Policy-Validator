"""Settings endpoints keep authorization and truthful offline status."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.config import settings
from app.integration_verification import status, verify
from app.security import Identity
from app.sessions import sessions as demo_sessions
from app import sso


def test_local_provider_has_no_automatic_verification(monkeypatch):
    monkeypatch.setattr(settings, "azure_openai_endpoint", "")
    monkeypatch.setattr(settings, "azure_openai_deployment", "")
    result = status(None, Identity("synthetic", "one", "Admin"), "azure_generation")
    assert result["status"] == "NOT_CONFIGURED"
    assert result["last_verification_at"] is None


def test_non_admin_cannot_list_sessions(monkeypatch):
    user = Identity("synthetic", "one", "User")
    with pytest.raises(HTTPException) as demo:
        demo_sessions(offset=0, limit=20, db=None, user=user)
    assert demo.value.status_code == 403
    monkeypatch.setattr(sso, "cookie_identity", lambda request, db: user)
    with pytest.raises(HTTPException) as entra:
        sso.sessions(request=SimpleNamespace(), db=None)
    assert entra.value.status_code == 403


@pytest.mark.asyncio
async def test_non_admin_cannot_trigger_external_verification():
    with pytest.raises(HTTPException) as denied:
        await verify(None, Identity("synthetic", "one", "User"), "moderation")
    assert denied.value.status_code == 403
