"""Run small, explicitly live adapter probes without exposing credentials or responses."""

import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.config import settings
from app.providers import (
    ProviderUnavailable,
    generate_ai_response,
    moderate_user_prompt,
)


# Extract safe diagnostic metadata without printing error messages, URLs, or headers.
def describe_failure(error: ProviderUnavailable) -> dict:
    cause = error.__cause__ or error
    result = {"status": "FAILED", "exception_type": type(cause).__name__}
    response = getattr(cause, "response", None)
    if response is not None:
        result["http_status"] = response.status_code
        try:
            code = response.json().get("error", {}).get("code")
            if (
                isinstance(code, str)
                and len(code) < 100
                and all(character.isalnum() or character in "_-." for character in code)
            ):
                result["provider_error_code"] = code
        except (ValueError, AttributeError):
            pass
    return result


# Probe only synthetic content; this is adapter connectivity, not a governed user request.
async def check_live_connectivity() -> dict:
    settings.provider_mode = "live"
    report = {
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "probe_type": "LIVE_SYNTHETIC_ADAPTER_CHECK",
        "services": {},
    }
    if settings.azure_openai_endpoint and settings.azure_openai_deployment:
        started = time.perf_counter()
        try:
            response = await generate_ai_response("Reply with exactly the word OK.")
            report["services"]["azure_openai"] = {
                "status": "LIVE_VERIFIED",
                "response_nonempty": bool(response.strip()),
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        except ProviderUnavailable as error:
            report["services"]["azure_openai"] = describe_failure(error)
    else:
        report["services"]["azure_openai"] = {
            "status": "BLOCKED",
            "reason": "Endpoint or deployment missing",
        }
    if settings.openai_api_key:
        try:
            categories = await moderate_user_prompt(
                "Explain the benefits of data governance in simple terms."
            )
            report["services"]["openai_moderation"] = {
                "status": "LIVE_VERIFIED",
                "synthetic_prompt_flagged": bool(categories),
            }
        except ProviderUnavailable as error:
            report["services"]["openai_moderation"] = describe_failure(error)
    else:
        report["services"]["openai_moderation"] = {
            "status": "BLOCKED",
            "reason": "OPENAI_API_KEY missing",
        }
    report["live_generation_and_moderation_ready"] = all(
        service["status"] == "LIVE_VERIFIED" for service in report["services"].values()
    )
    (ROOT / "docs" / "live-connectivity.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    return report


if __name__ == "__main__":
    print(json.dumps(asyncio.run(check_live_connectivity()), indent=2))
