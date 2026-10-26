"""Cấu hình logging dùng chung cho backend LearnCloud.

Mục tiêu:
* Một nơi duy nhất cấu hình log; module khác chỉ gọi ``get_logger(__name__)``.
* Mỗi request có ``request_id`` (đọc từ header ``X-Request-ID`` hoặc tự sinh) và
  id này tự xuất hiện trong mọi dòng log của request đó, giúp truy vết một lỗi
  từ response về log (local, CloudWatch Logs khi chạy trên Lambda).
* Hai định dạng: ``text`` (dễ đọc khi dev) và ``json`` (mỗi dòng một JSON, phù
  hợp CloudWatch Logs Insights).

Cấu hình qua biến môi trường (hoặc file ``.env`` ở thư mục gốc dự án):
* ``LOG_LEVEL``  - DEBUG | INFO | WARNING | ERROR. Mặc định: DEBUG nếu
  ``DEBUG=true``, ngược lại INFO.
* ``LOG_FORMAT`` - ``text`` (mặc định) hoặc ``json``.

Quy tắc an toàn: KHÔNG log body request, header xác thực, presigned URL,
access key hoặc nội dung transcript/đáp án. Chỉ log method, path, status,
thời gian và các id nghiệp vụ.

Cách dùng (trong ``main.py``)::

    from app.utils.logging import setup_logging, RequestLoggingMiddleware
    setup_logging()
    app.add_middleware(RequestLoggingMiddleware)
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware

try:  # python-dotenv có trong requirements.txt; vẫn phòng khi thiếu.
    from dotenv import dotenv_values
except ImportError:  # pragma: no cover
    dotenv_values = None

# backend/app/utils/logging.py -> thư mục gốc dự án là parents[3]
_PROJECT_ROOT = Path(__file__).resolve().parents[3]

_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)

# Chỉ nhận request id an toàn, tránh chèn xuống dòng/ký tự lạ vào log.
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

# Thuộc tính chuẩn của LogRecord, dùng để tách các trường ``extra=`` do người dùng thêm.
_STANDARD_RECORD_ATTRS = set(
    logging.LogRecord("x", logging.INFO, "x", 0, "", None, None).__dict__
) | {"message", "asctime", "request_id", "taskName"}

_configured = False


# --------------------------------------------------------------------------- #
# Request id
# --------------------------------------------------------------------------- #
def get_request_id() -> str:
    """Trả về request id của ngữ cảnh hiện tại ("-" nếu ngoài request)."""
    return _request_id_var.get()


def set_request_id(request_id: str) -> None:
    """Gán request id cho ngữ cảnh hiện tại."""
    _request_id_var.set(request_id)


class RequestIdFilter(logging.Filter):
    """Gắn ``record.request_id`` vào mọi bản ghi log."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


# --------------------------------------------------------------------------- #
# Formatter
# --------------------------------------------------------------------------- #
class JsonFormatter(logging.Formatter):
    """Mỗi bản ghi là một dòng JSON (UTF-8, giữ nguyên tiếng Việt)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": datetime.fromtimestamp(record.created, timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


_TEXT_FORMAT = "%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s: %(message)s"


# --------------------------------------------------------------------------- #
# Cấu hình
# --------------------------------------------------------------------------- #
def _env(name: str) -> str | None:
    """Đọc biến từ môi trường, sau đó từ ``.env`` ở thư mục gốc dự án."""
    value = os.environ.get(name)
    if value is not None:
        return value
    if dotenv_values is not None:
        env_file = _PROJECT_ROOT / ".env"
        if env_file.exists():
            return dotenv_values(env_file).get(name)
    return None


def _resolve_level(level: str | int | None) -> int:
    if level is None:
        level = _env("LOG_LEVEL")
    if level is None:
        debug = (_env("DEBUG") or "").strip().lower() in {"1", "true", "yes"}
        level = "DEBUG" if debug else "INFO"
    if isinstance(level, int):
        return level
    resolved = logging.getLevelName(str(level).strip().upper())
    return resolved if isinstance(resolved, int) else logging.INFO


def setup_logging(
    level: str | int | None = None,
    fmt: str | None = None,
    *,
    force: bool = False,
) -> None:
    """Cấu hình root logger. An toàn khi gọi nhiều lần (idempotent).

    Khi chạy trên AWS Lambda, runtime đã gắn sẵn handler cho root logger nên
    hàm chỉ đổi formatter/filter của handler đó thay vì thêm handler mới
    (tránh mỗi dòng log bị in hai lần trên CloudWatch).
    """
    global _configured
    if _configured and not force:
        return

    fmt = (fmt or _env("LOG_FORMAT") or "text").strip().lower()
    formatter: logging.Formatter = (
        JsonFormatter() if fmt == "json" else logging.Formatter(_TEXT_FORMAT)
    )

    root = logging.getLogger()
    root.setLevel(_resolve_level(level))

    if not root.handlers:
        root.addHandler(logging.StreamHandler(sys.stdout))

    for handler in root.handlers:
        handler.setFormatter(formatter)
        if not any(isinstance(f, RequestIdFilter) for f in handler.filters):
            handler.addFilter(RequestIdFilter())

    # Giảm nhiễu từ thư viện bên thứ ba.
    for noisy in ("boto3", "botocore", "urllib3", "s3transfer"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str | None = None) -> logging.Logger:
    """Lấy logger theo tên module: ``logger = get_logger(__name__)``."""
    return logging.getLogger(name)


# --------------------------------------------------------------------------- #
# Middleware
# --------------------------------------------------------------------------- #
_logger = get_logger("app.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Gán request id và ghi một dòng log cho mỗi request.

    * Đọc ``X-Request-ID`` từ client/API Gateway nếu hợp lệ, nếu không tự sinh.
    * Lưu vào ``request.state.request_id`` để exception handler dùng lại.
    * Trả lại header ``X-Request-ID`` trong response.
    * Mức log theo status: 2xx/3xx -> INFO, 4xx -> WARNING, 5xx -> ERROR.
    """

    async def dispatch(self, request, call_next):
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if _SAFE_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        set_request_id(request_id)
        request.state.request_id = request_id

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed = (time.perf_counter() - started) * 1000
            _logger.exception(
                "%s %s -> unhandled exception (%.1f ms)",
                request.method,
                request.url.path,
                elapsed,
            )
            raise

        elapsed = (time.perf_counter() - started) * 1000
        status_code = response.status_code
        level = (
            logging.ERROR
            if status_code >= 500
            else logging.WARNING
            if status_code >= 400
            else logging.INFO
        )
        _logger.log(
            level,
            "%s %s -> %s (%.1f ms)",
            request.method,
            request.url.path,
            status_code,
            elapsed,
        )
        response.headers["X-Request-ID"] = request_id
        return response