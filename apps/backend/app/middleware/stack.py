"""Request ID on every response + last-resort 500 handler. HTTPException propagates to FastAPI handlers."""
from __future__ import annotations
import logging
import uuid

from fastapi import HTTPException, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse
from starlette.types import ASGIApp

_log = logging.getLogger("onetouch.unhandled")
REQUEST_ID_HEADER = "X-Request-ID"


class CorrelationErrorMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> StarletteResponse:  # type: ignore[no-untyped-def]
        incoming = request.headers.get(REQUEST_ID_HEADER)
        rid = incoming or str(uuid.uuid4())
        request.state.request_id = rid

        try:
            response = await call_next(request)
        except RequestValidationError as exc:
            r = await request_validation_exception_handler(request, exc)
            r.headers[REQUEST_ID_HEADER] = rid
            return r
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            _log.exception("unhandled error request_id=%s", rid, exc_info=exc)
            r = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error", "request_id": rid},
            )
            r.headers[REQUEST_ID_HEADER] = rid
            return r

        if isinstance(response, Response):
            response.headers[REQUEST_ID_HEADER] = rid
        return response  # type: ignore[return-value]
