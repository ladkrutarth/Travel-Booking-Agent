"""RFC7807-style problem details and API exceptions."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        title: str,
        detail: str,
        *,
        retryable: bool = False,
        extras: Optional[Dict[str, Any]] = None,
    ):
        self.status = status
        self.code = code
        self.title = title
        self.detail = detail
        self.retryable = retryable
        self.extras = extras or {}
        super().__init__(detail)


def problem_body(
    *,
    status: int,
    code: str,
    title: str,
    detail: str,
    retryable: bool = False,
    request_id: Optional[str] = None,
    extras: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "type": f"https://travel-booking.local/problems/{code}",
        "title": title,
        "status": status,
        "detail": detail,
        "code": code,
        "retryable": retryable,
    }
    if request_id:
        body["request_id"] = request_id
    if extras:
        body.update(extras)
    return body


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=exc.status,
        content=problem_body(
            status=exc.status,
            code=exc.code,
            title=exc.title,
            detail=exc.detail,
            retryable=exc.retryable,
            request_id=request_id,
            extras=exc.extras,
        ),
        media_type="application/problem+json",
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    code = "http_error"
    if exc.status_code == 401:
        code = "unauthorized"
    elif exc.status_code == 404:
        code = "not_found"
    elif exc.status_code == 409:
        code = "conflict"
    return JSONResponse(
        status_code=exc.status_code,
        content=problem_body(
            status=exc.status_code,
            code=code,
            title="Request failed",
            detail=detail,
            request_id=request_id,
        ),
        media_type="application/problem+json",
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=422,
        content=problem_body(
            status=422,
            code="validation_error",
            title="Validation failed",
            detail="One or more fields are invalid.",
            request_id=request_id,
            extras={"errors": exc.errors()},
        ),
        media_type="application/problem+json",
    )
