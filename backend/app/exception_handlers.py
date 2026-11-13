"""Existing sanitized database, concurrency and validation error responses."""

from fastapi.responses import JSONResponse
import json


async def database_failure(request, error):
    from .middleware import logger
    from .schema_compatibility import schema_diagnostic

    diagnostic = schema_diagnostic(error)
    if diagnostic["category"] == "SCHEMA_QUERY_OR_IMPLEMENTATION_FAILURE":
        diagnostic["category"] = "DATABASE_OPERATION_FAILED"
    logger.warning(json.dumps({
        "event": "database.failed",
        "route": getattr(request.scope.get("route"), "path", "unmatched"),
        **diagnostic,
    }))
    return JSONResponse(status_code=503, content={"detail": "Database operation unavailable; nothing released"})


async def concurrent_policy_change(request, error):
    return JSONResponse(status_code=409, content={"detail": "Record changed concurrently; reload and retry"})


async def invalid_request(request, error):
    return JSONResponse(status_code=422, content={"detail": [{"loc": item["loc"], "type": item["type"]} for item in error.errors()]})
