from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.utils.logging import get_logger, get_request_id

logger = get_logger(__name__)


# --------------------------------------------------------------------------- #
# Hệ thống exception nghiệp vụ
# --------------------------------------------------------------------------- #
class AppError(Exception):
    """Lớp gốc của mọi lỗi nghiệp vụ có chủ đích."""

    status_code: int = 500
    code: str = "INTERNAL_ERROR"
    default_message: str = "Internal server error."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.default_message
        if code is not None:
            self.code = code
        self.details = details
        self.headers = headers
        super().__init__(self.message)


class BadRequestError(AppError):
    """400 - dữ liệu đầu vào sai về nghiệp vụ."""

    status_code = 400
    code = "BAD_REQUEST"
    default_message = "Bad request."


class UnauthorizedError(AppError):
    """401 - chưa xác thực hoặc danh tính không hợp lệ."""

    status_code = 401
    code = "UNAUTHORIZED"
    default_message = "Authentication required."


class ForbiddenError(AppError):
    """403 - đã xác thực nhưng thiếu quyền / chưa unlock."""

    status_code = 403
    code = "FORBIDDEN"
    default_message = "You do not have permission to perform this action."


class NotFoundError(AppError):
    """404 - tài nguyên không tồn tại (hoặc không được phép biết là có tồn tại)."""

    status_code = 404
    code = "NOT_FOUND"
    default_message = "Resource not found."


class ConflictError(AppError):
    """409 - trạng thái hiện tại không cho phép (trùng, sai trạng thái pipeline...)."""

    status_code = 409
    code = "CONFLICT"
    default_message = "The request conflicts with the current state."


class ExternalServiceError(AppError):
    """502 - dịch vụ ngoài (S3, Bedrock, Transcribe...) lỗi hoặc không phản hồi."""

    status_code = 502
    code = "EXTERNAL_SERVICE_ERROR"
    default_message = "An upstream service failed."


# --------------------------------------------------------------------------- #
# Dựng response
# --------------------------------------------------------------------------- #
_STATUS_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "TOO_MANY_REQUESTS",
    500: "INTERNAL_ERROR",
    502: "EXTERNAL_SERVICE_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or get_request_id()


def error_response(
    request: Request,
    status_code: int,
    code: str,
    detail: Any,
    *,
    details: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Tạo JSON lỗi theo định dạng chung của dự án."""
    body: dict[str, Any] = {
        "detail": detail,
        "code": code,
        "request_id": _request_id(request),
    }
    if details is not None:
        body["details"] = details
    # Luôn trả X-Request-ID, kể cả khi lỗi 500 đi qua ServerErrorMiddleware
    # (nằm ngoài RequestLoggingMiddleware nên middleware không kịp gắn header).
    out_headers = {"X-Request-ID": body["request_id"], **(headers or {})}
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(body),
        headers=out_headers,
    )


# --------------------------------------------------------------------------- #
# Handler
# --------------------------------------------------------------------------- #
async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    if exc.status_code >= 500:
        logger.error(
            "%s %s -> %s %s: %s",
            request.method,
            request.url.path,
            exc.status_code,
            exc.code,
            exc.message,
            exc_info=exc,
        )
        # 5xx: thông điệp và details nội bộ chỉ nằm trong log, không gửi cho client.
        return error_response(
            request,
            exc.status_code,
            exc.code,
            type(exc).default_message,
            headers=exc.headers,
        )
    logger.info(
        "%s %s -> %s %s: %s",
        request.method,
        request.url.path,
        exc.status_code,
        exc.code,
        exc.message,
    )
    return error_response(
        request,
        exc.status_code,
        exc.code,
        exc.message,
        details=exc.details,
        headers=exc.headers,
    )


async def _handle_http_exception(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Bao cả ``fastapi.HTTPException`` đang dùng trong các route hiện có."""
    code = _STATUS_CODES.get(exc.status_code, f"HTTP_{exc.status_code}")
    return error_response(
        request,
        exc.status_code,
        code,
        exc.detail,
        headers=getattr(exc, "headers", None),
    )


async def _handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """422 - giữ nguyên danh sách lỗi của FastAPI trong ``detail``."""
    return error_response(
        request,
        422,
        "VALIDATION_ERROR",
        exc.errors(),
    )


async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """500 - lỗi không lường trước; log đầy đủ, trả thông điệp chung."""
    logger.error(
        "%s %s -> unhandled %s",
        request.method,
        request.url.path,
        type(exc).__name__,
        exc_info=exc,
    )
    return error_response(
        request,
        500,
        "INTERNAL_ERROR",
        AppError.default_message,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Đăng ký toàn bộ handler lên ứng dụng FastAPI."""
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(Exception, _handle_unexpected_error)