"""Offline regressions for failures exposed by bounded deployed acceptance."""

import inspect
import io
import threading
import time
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
import requests
from azure.core.credentials import AccessToken
from azure.core.exceptions import ResourceExistsError
from azure.core.pipeline.transport import RequestsTransport
from azure.storage.filedatalake import DataLakeServiceClient

from app import providers
from app.config import settings


@pytest.mark.parametrize("parent_type", ["new", "directory", "file", None, "existing-file"])
def test_adls_conditions_reach_real_sdk_transport_without_unknown_keywords(monkeypatch, parent_type):
    """Exercise real SDK serialization rather than mocking directory methods."""
    sent = []

    class Credential:
        def get_token(self, *_args, **_kwargs):
            return AccessToken("fixture-token", int(time.time()) + 3600)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

    class Session(requests.Session):
        file_created = False

        def request(self, *args, **kwargs):
            # The real requests transport rejects leaked storage-only options.
            arguments = inspect.signature(requests.Session.request).bind(self, *args, **kwargs).arguments
            sent.append((arguments["method"], arguments["url"], dict(arguments["headers"])))
            response = requests.Response()
            response.status_code = 202 if "action=append" in arguments["url"] else 200 if "action=flush" in arguments["url"] else 201
            response._content = b""
            if "resource=directory" in arguments["url"] and parent_type != "new":
                response.status_code = 409
                response.headers["x-ms-error-code"] = "PathAlreadyExists"
                response._content = b"<Error><Code>PathAlreadyExists</Code><Message>Existing path</Message></Error>"
            if arguments["method"] == "HEAD":
                response.status_code = 200
                if parent_type is not None:
                    response.headers["x-ms-meta-hdi_isfolder"] = "true" if parent_type in ("directory", "existing-file") else "false"
            if "resource=file" in arguments["url"]:
                if parent_type == "existing-file":
                    response.status_code = 409
                    response.headers["x-ms-error-code"] = "PathAlreadyExists"
                    response._content = b"<Error><Code>PathAlreadyExists</Code><Message>Existing file</Message></Error>"
                else:
                    self.file_created = True
            if ("action=append" in arguments["url"] or "action=flush" in arguments["url"]) and not self.file_created:
                response.status_code = 404
                response.headers["x-ms-error-code"] = "PathNotFound"
                response._content = b"<Error><Code>PathNotFound</Code><Message>File must be created before append</Message></Error>"
            response.raw = io.BytesIO(b"")
            response.headers.update({"etag": '"fixture"', "last-modified": "Thu, 29 Oct 2026 12:00:00 GMT", "x-ms-request-id": "fixture"})
            return response

    credential = Credential()
    monkeypatch.setattr(settings, "adls_account_url", "https://fixture.dfs.core.windows.net")
    monkeypatch.setattr(settings, "adls_file_system", "reports")
    monkeypatch.setattr("azure.identity.DefaultAzureCredential", lambda: credential)
    monkeypatch.setattr(
        "azure.storage.filedatalake.DataLakeServiceClient",
        lambda *args, **kwargs: DataLakeServiceClient(*args, **kwargs, transport=RequestsTransport(session=Session())),
    )
    if parent_type in ("file", None):
        with pytest.raises(providers.ProviderUnavailable, match="Report parent is not a directory"):
            providers.upload_report("governance-reports/2026/10/30/fixture.json", "[]")
        assert len(sent) == 2
        assert [method for method, _, _ in sent] == ["PUT", "HEAD"]
        return
    if parent_type == "existing-file":
        with pytest.raises(ResourceExistsError):
            providers.upload_report("governance-reports/2026/10/30/fixture.json", "[]")
        assert not any("action=append" in url or "action=flush" in url for _, url, _ in sent)
        creates = [headers for _, url, headers in sent if "resource=file" in url]
        assert len(creates) == 1 and creates[0]["If-None-Match"] == "*"
        return
    providers.upload_report("governance-reports/2026/10/30/fixture.json", "[]")
    directories = [headers for _, url, headers in sent if "resource=directory" in url]
    assert len(directories) == 4
    assert all(headers.get("If-None-Match") == "*" for headers in directories)
    files = [headers for _, url, headers in sent if "action=flush" in url]
    assert len(files) == 1
    creates = [headers for _, url, headers in sent if "resource=file" in url]
    assert len(creates) == 1 and creates[0]["If-None-Match"] == "*"
    assert files[0]["If-Match"] == '"fixture"'


@pytest.mark.asyncio
async def test_generation_identity_uses_existing_sync_transport_off_event_loop(monkeypatch):
    loop_thread = threading.get_ident()
    credential = Mock()
    credential.__enter__ = Mock(return_value=credential)
    credential.__exit__ = Mock(return_value=False)

    def token(*_args, **_kwargs):
        assert threading.get_ident() != loop_thread
        return AccessToken("fixture-token", int(time.time()) + 3600)

    credential.get_token.side_effect = token
    factory = Mock(return_value=credential)
    monkeypatch.setattr("azure.identity.DefaultAzureCredential", factory)
    http = AsyncMock()
    http.__aenter__.return_value = http
    http.post.return_value = httpx.Response(
        200,
        request=httpx.Request("POST", "https://fixture.openai.azure.com"),
        json={"choices": [{"finish_reason": "stop", "message": {"content": "Inspected synthetic answer"}}]},
    )
    monkeypatch.setattr(providers.httpx, "AsyncClient", lambda **_: http)
    monkeypatch.setattr(settings, "provider_mode", "live")
    monkeypatch.setattr(settings, "azure_openai_endpoint", "https://fixture.openai.azure.com")
    monkeypatch.setattr(settings, "azure_openai_deployment", "fixture-model")
    monkeypatch.setattr(settings, "azure_openai_api_key", "")
    assert await providers.generate_ai_response("Safe synthetic input") == "Inspected synthetic answer"
    credential.get_token.assert_called_once_with("https://cognitiveservices.azure.com/.default")
    credential.__exit__.assert_called_once()
    assert http.post.call_args.kwargs["headers"] == {"Authorization": "Bearer fixture-token"}


@pytest.mark.asyncio
async def test_generation_identity_failure_is_sanitized_and_never_posts(monkeypatch):
    monkeypatch.setattr(settings, "provider_mode", "live")
    monkeypatch.setattr(settings, "azure_openai_endpoint", "https://fixture.openai.azure.com")
    monkeypatch.setattr(settings, "azure_openai_deployment", "fixture-model")
    monkeypatch.setattr(settings, "azure_openai_api_key", "")
    factory = Mock(side_effect=RuntimeError("fixture-private-auth-detail"))
    monkeypatch.setattr("azure.identity.DefaultAzureCredential", factory)
    http_factory = Mock()
    monkeypatch.setattr(providers.httpx, "AsyncClient", http_factory)
    with pytest.raises(providers.ProviderUnavailable, match="^Azure generation unavailable$"):
        await providers.generate_ai_response("Safe synthetic input")
    http_factory.assert_not_called()
