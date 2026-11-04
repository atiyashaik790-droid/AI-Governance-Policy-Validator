"""Only approved services are contacted. Fixtures are explicit test dependencies."""

import asyncio
import httpx
from urllib.parse import urlparse
from uuid import UUID
from contextvars import ContextVar

from .config import settings
from .schemas import ModerationCategory
from typing import get_args

generation_usage: ContextVar[dict | None] = ContextVar("generation_usage", default=None)


class ProviderUnavailable(Exception):
    def __init__(
        self, message: str = "Provider unavailable", *, code: str = "PROVIDER_UNAVAILABLE", response: httpx.Response | None = None
    ):
        super().__init__(message)
        self.diagnostics: dict = {"code": code}
        if response is not None:
            self.diagnostics["http_status"] = response.status_code
            # Only UUID correlation identifiers, never provider bodies or headers wholesale.
            for header in ("apim-request-id", "x-request-id", "x-ms-request-id"):
                try:
                    self.diagnostics["request_id"] = str(UUID(response.headers.get(header, "")))
                    break
                except ValueError:
                    continue


def generation_failure(error: Exception, response: httpx.Response | None) -> ProviderUnavailable:
    """Classify safely without persisting exception messages, URLs, prompts or keys."""
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        code = {
            400: "GENERATION_INVALID_REQUEST",
            401: "GENERATION_AUTHENTICATION_FAILED",
            403: "GENERATION_PERMISSION_DENIED",
            404: "GENERATION_DEPLOYMENT_NOT_FOUND",
            429: "GENERATION_RATE_LIMITED",
        }.get(status, "GENERATION_PROVIDER_ERROR" if status >= 500 else "GENERATION_HTTP_ERROR")
    elif isinstance(error, httpx.ReadTimeout):
        code = "GENERATION_READ_TIMEOUT"
    elif isinstance(error, httpx.ConnectTimeout):
        code = "GENERATION_CONNECT_TIMEOUT"
    elif isinstance(error, httpx.TimeoutException):
        code = "GENERATION_TRANSPORT_TIMEOUT"
    elif isinstance(error, httpx.TransportError):
        code = "GENERATION_TRANSPORT_ERROR"
    else:
        code = "GENERATION_INVALID_RESPONSE"
    return ProviderUnavailable("Azure generation unavailable", code=code, response=response)


# Validate that configured endpoints cannot send credentials to arbitrary hosts.
def validate_azure_endpoint(endpoint: str, suffix: str) -> None:
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not (parsed.hostname or "").endswith(suffix) or parsed.username or parsed.query:
        raise ProviderUnavailable("Invalid approved Azure endpoint")


# Normalize a real moderation result, treating malformed responses as unavailable.
async def moderate_user_prompt(text: str, required_categories: list[str] | None = None) -> list[str]:
    if settings.provider_mode == "fixture":
        if "[MODERATION_UNAVAILABLE]" in text:
            raise ProviderUnavailable("Fixture outage")
        return ["violence"] if "[MODERATION_FLAG]" in text else []
    if not settings.openai_api_key:
        raise ProviderUnavailable("Moderation not configured")
    try:
        async with httpx.AsyncClient(timeout=settings.provider_timeout) as client:
            response = await client.post(
                "https://api.openai.com/v1/moderations",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={"model": "omni-moderation-latest", "input": text},
            )
            response.raise_for_status()
            result = response.json()["results"][0]
            if type(result["flagged"]) is not bool or not isinstance(result["categories"], dict) or not result["categories"]:
                raise ValueError("Malformed moderation")
            if any(type(value) is not bool for value in result["categories"].values()):
                raise ValueError("Malformed categories")
            known = set(get_args(ModerationCategory))
            if required_categories and not set(required_categories).issubset(result["categories"]):
                raise ValueError("Required moderation category missing")
            if set(result["categories"]) - known:
                raise ValueError("Unrecognized moderation category")
            categories = [key for key, value in result["categories"].items() if value]
            if result["flagged"] and not categories:
                raise ValueError("Flagged without categories")
            return categories
    except Exception as error:
        raise ProviderUnavailable("Moderation inspection unavailable") from error


# Acquire and close the installed Azure credential in a worker thread.
def _generation_access_token() -> str:
    from azure.identity import DefaultAzureCredential

    with DefaultAzureCredential() as credential:
        return credential.get_token("https://cognitiveservices.azure.com/.default").token


# Generate only after the gateway has approved input; never log request bodies.
async def generate_ai_response(text: str) -> str:
    generation_usage.set(None)
    if settings.provider_mode == "fixture":
        if "[OUTPUT_SECRET]" in text:
            return "api_key=sk-test-" + "A" * 30
        return "Data governance helps teams keep information accurate, secure, and useful. [Deterministic local fixture]"
    validate_azure_endpoint(settings.azure_openai_endpoint, ".openai.azure.com")
    if not settings.azure_openai_deployment:
        raise ProviderUnavailable("Azure deployment not configured")
    response = None
    try:
        headers = {}
        if settings.azure_openai_api_key:
            headers["api-key"] = settings.azure_openai_api_key
        else:
            try:
                headers["Authorization"] = f"Bearer {await asyncio.to_thread(_generation_access_token)}"
            except Exception as error:
                raise ProviderUnavailable("Azure generation unavailable", code="GENERATION_AUTHENTICATION_UNAVAILABLE") from error
        endpoint = settings.azure_openai_endpoint.rstrip("/")
        if settings.azure_openai_api_version == "v1":
            url, params = f"{endpoint}/openai/v1/chat/completions", None
        else:
            from urllib.parse import quote

            url = f"{endpoint}/openai/deployments/{quote(settings.azure_openai_deployment, safe='')}/chat/completions"
            params = {"api-version": settings.azure_openai_api_version}
        payload = {
            "model": settings.azure_openai_deployment,
            "messages": [{"role": "user", "content": text}],
            "max_completion_tokens": 700,
        }
        # The verified deployment uses original GPT-5 mini. Its reasoning shares the
        # completion cap; reduce reasoning effort rather than raising cost/time limits.
        # Do not send this model-specific parameter to arbitrary deployment aliases.
        if settings.azure_openai_deployment in ("gpt-5", "gpt-5-mini", "gpt-5-nano"):
            payload["reasoning_effort"] = "minimal"
        async with httpx.AsyncClient(timeout=settings.provider_timeout) as client:
            response = await client.post(
                url,
                params=params,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
            usage = body.get("usage")
            if isinstance(usage, dict):
                generation_usage.set(
                    {
                        key: value
                        for key, value in usage.items()
                        if key in ("prompt_tokens", "completion_tokens") and type(value) is int and value >= 0
                    }
                )
            choice = body["choices"][0]
            finish_reason = choice.get("finish_reason")
            if finish_reason != "stop":
                code = (
                    "GENERATION_TOKEN_LIMIT"
                    if finish_reason == "length"
                    else "GENERATION_CONTENT_FILTERED"
                    if finish_reason == "content_filter"
                    else "GENERATION_INCOMPLETE"
                )
                raise ProviderUnavailable("Azure generation unavailable", code=code, response=response)
            content = choice["message"]["content"]
            if not isinstance(content, str) or not content.strip() or len(content) > 30000:
                raise ValueError("Invalid model response")
            return content
    except ProviderUnavailable:
        raise
    except Exception as error:
        raise generation_failure(error, response) from error


# Upload sanitized metadata to an existing ADLS filesystem without provisioning resources.
def upload_report(path: str, content: str) -> None:
    validate_azure_endpoint(settings.adls_account_url, ".dfs.core.windows.net")
    if not settings.adls_file_system:
        raise ProviderUnavailable("ADLS filesystem not configured")
    import re

    parts = path.split("/")
    if any(part in ("", ".", "..") or not re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts):
        raise ProviderUnavailable("Invalid report path")
    from azure.core import MatchConditions
    from azure.core.exceptions import ResourceExistsError, ResourceModifiedError
    from azure.identity import DefaultAzureCredential
    from azure.storage.filedatalake import DataLakeServiceClient

    with DefaultAzureCredential() as credential:
        with DataLakeServiceClient(
            settings.adls_account_url, credential=credential, connection_timeout=10, read_timeout=20, retry_total=0
        ) as service:
            filesystem = service.get_file_system_client(settings.adls_file_system)
            # ADLS does not create missing parents when uploading a nested file.
            # Conditional creation preserves existing directories, metadata and ACLs.
            for index in range(1, len(parts)):
                directory = filesystem.get_directory_client("/".join(parts[:index]))
                try:
                    directory.create_directory(match_condition=MatchConditions.IfMissing)
                except (ResourceExistsError, ResourceModifiedError):
                    properties = directory.get_directory_properties()
                    if (properties.metadata or {}).get("hdi_isfolder") != "true":
                        raise ProviderUnavailable("Report parent is not a directory") from None
            file = filesystem.get_file_client(path)
            # Conditional creation prevents replacement; the SDK then pins flush to its new ETag.
            file.upload_data(content.encode(), overwrite=True, match_condition=MatchConditions.IfMissing)


def report_digest(path: str, maximum_bytes: int) -> str | None:
    """Read only a known deterministic object, bounded by size; no listing or deletion."""
    import hashlib
    from azure.core import MatchConditions
    from azure.core.exceptions import ResourceNotFoundError
    from azure.identity import DefaultAzureCredential
    from azure.storage.filedatalake import DataLakeServiceClient

    validate_azure_endpoint(settings.adls_account_url, ".dfs.core.windows.net")
    if not settings.adls_file_system or any(part in ("", ".", "..") for part in path.split("/")):
        raise ProviderUnavailable("Invalid report destination")
    with DefaultAzureCredential() as credential:
        with DataLakeServiceClient(
            settings.adls_account_url, credential=credential, connection_timeout=10, read_timeout=20, retry_total=0
        ) as service:
            file = service.get_file_system_client(settings.adls_file_system).get_file_client(path)
            try:
                properties = file.get_file_properties()
                if properties.size > maximum_bytes:
                    raise ProviderUnavailable("Export exceeds recovery limit", code="EXPORT_CONTENT_MISMATCH")
                content = file.download_file(etag=properties.etag, match_condition=MatchConditions.IfNotModified).readall()
            except ResourceNotFoundError:
                return None
            if len(content) > maximum_bytes:
                raise ProviderUnavailable("Export exceeds recovery limit", code="EXPORT_CONTENT_MISMATCH")
            return hashlib.sha256(content).hexdigest()
