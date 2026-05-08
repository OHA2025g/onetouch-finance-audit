"""App-specific errors and HTTPException enrichment with request IDs."""
from __future__ import annotations
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class ServiceError(HTTPException):
    """Domain / service error with a stable error code for clients and logs."""

    def __init__(self, detail: str, *, code: str = "service_error", status_code: int = 400) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.code = code


def _with_request_id(body: dict[str, Any], request: Request) -> dict[str, Any]:
    rid = getattr(request.state, "request_id", None)
    if rid is None:
        return body
    return {**body, "request_id": rid}


def register_exception_handlers(app: Any) -> None:
    # Register more specific subtypes before HTTPException (ServiceError is a subclass).
    @app.exception_handler(ServiceError)
    async def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
        body: dict[str, Any] = {"detail": exc.detail, "code": exc.code}
        return JSONResponse(status_code=exc.status_code, content=_with_request_id(body, request))

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, (list, dict)):
            body = {"detail": exc.detail}
        else:
            body = {"detail": str(exc.detail)}
        if exc.headers:
            return JSONResponse(
                status_code=exc.status_code,
                content=_with_request_id(body, request),
                headers=dict(exc.headers),
            )
        return JSONResponse(status_code=exc.status_code, content=_with_request_id(body, request))
