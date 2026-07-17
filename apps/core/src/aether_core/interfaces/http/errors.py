"""Maps domain errors to RFC 9457 problem responses."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from aether_core.domain.errors import (
    AetherError,
    ConflictError,
    NotFoundError,
    ValidationFailedError,
)


def _status_for(exc: AetherError) -> int:
    if isinstance(exc, NotFoundError):
        return 404
    if isinstance(exc, ConflictError):
        return 409
    if isinstance(exc, ValidationFailedError):
        return 400
    return 500


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AetherError)
    async def aether_error_handler(request: Request, exc: AetherError) -> JSONResponse:
        status = _status_for(exc)
        return JSONResponse(
            status_code=status,
            media_type="application/problem+json",
            content={
                "type": f"aether:{type(exc).__name__}",
                "title": type(exc).__name__,
                "status": status,
                "detail": str(exc),
            },
        )
