"""Central handling for retryable provider errors and the unified API error envelope."""

import logging
import random
import time
from typing import Callable, TypeVar

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

log = logging.getLogger("gifty.errors")

T = TypeVar("T")

# HTTP status -> machine-readable error code for the {error:{code,message,details}} envelope.
STATUS_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
}


def envelope(status: int, message: str, details: object = None) -> JSONResponse:
    """Build a JSONResponse in the single error shape used across the API."""
    code = STATUS_CODES.get(status, "ERROR")
    body: dict = {"code": code, "message": message}
    if details is not None:
        body["details"] = jsonable_encoder(details)
    return JSONResponse(status_code=status, content={"error": body})


class EnvelopeErrors:
    """ASGI middleware turning unhandled exceptions into the 500 error envelope.

    Lives inside CORSMiddleware so 500s still carry CORS headers — Starlette's
    built-in ServerErrorMiddleware is outermost and would bypass them. Kept as
    raw ASGI (not BaseHTTPMiddleware) so it never buffers the SSE streams.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def guard(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, guard)
        except Exception:
            log.exception("unhandled error")
            if started:
                raise  # response already begun (e.g. mid-stream); can't replace it
            # Never leak internals to the client.
            await envelope(500, "Internal server error")(scope, receive, send)


def register_handlers(app: FastAPI) -> None:
    """Install error handling so every response shares one envelope and shape.

    HTTPException/validation are handled by inner ExceptionMiddleware (CORS headers
    apply); unhandled errors go through EnvelopeErrors, which app wraps with CORS.
    """

    @app.exception_handler(HTTPException)
    async def on_http(_: Request, exc: HTTPException) -> JSONResponse:
        return envelope(exc.status_code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def on_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return envelope(422, "Request validation failed", exc.errors())

    app.add_middleware(EnvelopeErrors)

RETRYABLE_CODES = {429, 500, 502, 503, 504}
RETRYABLE_HINTS = ("connection", "timeout", "unavailable", "overloaded", "ratelimit")


def is_retryable(exc: Exception) -> bool:
    """Return True for transient provider/network errors worth retrying."""
    code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if code in RETRYABLE_CODES:
        return True
    name = type(exc).__name__.lower()
    return any(hint in name for hint in RETRYABLE_HINTS)


def retry_call(fn: Callable[..., T], *args, attempts: int = 3, base: float = 5.0, **kwargs) -> T:
    """Call fn with jittered exponential backoff on retryable errors.

    Args:
        attempts: Max attempts before giving up.
        base: Backoff base seconds; delay = base * 2**i + jitter.
    """
    for i in range(attempts):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            if not is_retryable(exc) or i == attempts - 1:
                raise
            delay = base * (2**i) + random.uniform(0, base)
            log.warning("retryable error (%s); attempt %d/%d, sleeping %.1fs", exc, i + 1, attempts, delay)
            time.sleep(delay)
    raise RuntimeError("unreachable")
