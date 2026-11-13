"""Existing request bounds, response headers and HTTP completion logging."""

import json
import logging
import re
import time
from uuid import uuid4
from fastapi import Request
from fastapi.responses import JSONResponse
from .stage_timing import correlation as stage_correlation

logger = logging.getLogger("governance.http")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
logger.propagate = False


async def bound_request_size(request: Request, call_next):
    from .routers.document_uploads import UPLOAD_BODY_LIMIT
    limit = UPLOAD_BODY_LIMIT if request.url.path in {
        "/api/governance/generate-document", "/api/v2/governance/generate-document",
    } else 64000
    limit_error = "Upload request exceeds 400000 bytes" if limit == UPLOAD_BODY_LIMIT else "Request exceeds 64 KB"
    length = request.headers.get("content-length")
    if length and (not length.isdigit() or int(length) > limit):
        return JSONResponse(status_code=413, content={"detail": limit_error})
    received = 0
    chunks = []
    async for chunk in request.stream():
        received += len(chunk)
        chunks.append(chunk)
        if received > limit:
            return JSONResponse(status_code=413, content={"detail": limit_error})
    request._body = b"".join(chunks)
    started = time.perf_counter()
    supplied = request.headers.get("x-request-id", "")
    correlation = supplied if re.fullmatch(r"[A-Za-z0-9_-]{8,64}", supplied) else str(uuid4())
    token = stage_correlation.set(correlation)
    try:
        response = await call_next(request)
    finally:
        stage_correlation.reset(token)
    response.headers["X-Request-ID"] = correlation
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
    )
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    logger.info(
        json.dumps(
            {
                "event": "http.completed",
                "correlation_id": correlation,
                "route": getattr(request.scope.get("route"), "path", "unmatched"),
                "method": request.method,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        )
    )
    return response
