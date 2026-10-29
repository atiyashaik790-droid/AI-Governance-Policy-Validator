"""Only approved services are contacted. Fixtures are explicit test dependencies."""

import httpx
from urllib.parse import urlparse
from .config import settings


class ProviderUnavailable(Exception):
    pass


# Validate that configured endpoints cannot send credentials to arbitrary hosts.
def validate_azure_endpoint(endpoint: str, suffix: str) -> None:
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not (parsed.hostname or "").endswith(suffix) or parsed.username or parsed.query:
        raise ProviderUnavailable("Invalid approved Azure endpoint")


# Normalize a real moderation result, treating malformed responses as unavailable.
async def moderate_user_prompt(text: str) -> list[str]:
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
            if type(result["flagged"]) is not bool or not isinstance(result["categories"], dict):
                raise ValueError("Malformed moderation")
            if any(type(value) is not bool for value in result["categories"].values()):
                raise ValueError("Malformed categories")
            categories = [key for key, value in result["categories"].items() if value]
            if result["flagged"] and not categories:
                raise ValueError("Flagged without categories")
            return categories
    except Exception as error:
        raise ProviderUnavailable("Moderation inspection unavailable") from error


# Generate only after the gateway has approved input; never log request bodies.
async def generate_ai_response(text: str) -> str:
    if settings.provider_mode == "fixture":
        if "[OUTPUT_SECRET]" in text:
            return "api_key=sk-test-" + "A" * 30
        return "Data governance helps teams keep information accurate, secure, and useful. [Deterministic local fixture]"
    validate_azure_endpoint(settings.azure_openai_endpoint, ".openai.azure.com")
    if not settings.azure_openai_deployment:
        raise ProviderUnavailable("Azure deployment not configured")
    try:
        headers = {}
        if settings.azure_openai_api_key:
            headers["api-key"] = settings.azure_openai_api_key
        else:
            from azure.identity.aio import DefaultAzureCredential

            async with DefaultAzureCredential() as credential:
                token = await credential.get_token("https://cognitiveservices.azure.com/.default")
                headers["Authorization"] = f"Bearer {token.token}"
        endpoint = settings.azure_openai_endpoint.rstrip("/")
        if settings.azure_openai_api_version == "v1":
            url, params = f"{endpoint}/openai/v1/chat/completions", None
        else:
            from urllib.parse import quote

            url = f"{endpoint}/openai/deployments/{quote(settings.azure_openai_deployment, safe='')}/chat/completions"
            params = {"api-version": settings.azure_openai_api_version}
        async with httpx.AsyncClient(timeout=settings.provider_timeout) as client:
            response = await client.post(
                url,
                params=params,
                headers=headers,
                json={
                    "model": settings.azure_openai_deployment,
                    "messages": [{"role": "user", "content": text}],
                    "max_completion_tokens": 700,
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip() or len(content) > 30000:
                raise ValueError("Invalid model response")
            return content
    except Exception as error:
        raise ProviderUnavailable("Azure generation unavailable") from error


# Upload sanitized metadata to an existing ADLS filesystem without provisioning resources.
def upload_report(path: str, content: str) -> None:
    validate_azure_endpoint(settings.adls_account_url, ".dfs.core.windows.net")
    if not settings.adls_file_system:
        raise ProviderUnavailable("ADLS filesystem not configured")
    from azure.identity import DefaultAzureCredential
    from azure.storage.filedatalake import DataLakeServiceClient

    with DefaultAzureCredential() as credential:
        with DataLakeServiceClient(settings.adls_account_url, credential=credential, connection_timeout=10, read_timeout=20) as service:
            file = service.get_file_system_client(settings.adls_file_system).get_file_client(path)
            file.upload_data(content.encode(), overwrite=False)
