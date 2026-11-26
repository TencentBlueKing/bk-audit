import logging

from blueapps.utils.logger import logger
from django.conf import settings

LARGE_REQUEST_SIZE = 1024 * 1024
OBSERVED_METHODS = {"POST", "PUT", "PATCH"}
BODY_LIMIT_MEDIA_TYPES = {"application/json", "application/x-www-form-urlencoded"}


def _declared_content_length(raw_length):
    if raw_length is None:
        return None, "missing"

    value = str(raw_length).strip()
    if not value:
        return None, "missing"
    if value.isascii() and value.isdecimal():
        try:
            return int(value), "declared"
        except ValueError:
            # Python limits the number of decimal digits it can convert.
            pass
    return None, "invalid"


class RequestSizeLoggingMiddleware:
    """Observe the declared HTTP body size before downstream request handling."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.LOG_LARGE_REQUEST_BODY and request.method in OBSERVED_METHODS:
            self._log_size(request)
        return self.get_response(request)

    def _log_size(self, request):
        length, length_status = _declared_content_length(request.META.get("CONTENT_LENGTH"))
        content_type = (request.META.get("CONTENT_TYPE") or "").partition(";")[0].strip().lower()
        limit = settings.DATA_UPLOAD_MAX_MEMORY_SIZE

        level = logging.INFO
        if length_status == "missing":
            message = "SEC012_REQUEST_SIZE 请求长度未声明"
        elif length_status == "invalid":
            message = "SEC012_REQUEST_SIZE 请求长度无效"
        elif content_type in BODY_LIMIT_MEDIA_TYPES and limit is not None and length > limit:
            level = logging.WARNING
            message = "SEC012_REQUEST_SIZE 声明长度超过 Django 上限，可能返回 413"
        elif length >= LARGE_REQUEST_SIZE:
            message = "SEC012_REQUEST_SIZE 请求声明长度达到 1 MiB"
        else:
            return

        logger.log(
            level,
            message,
            extra={
                "method": request.method,
                "request_path": request.path,
                "content_type": content_type,
                "content_length": length,
                "length_status": length_status,
            },
        )
