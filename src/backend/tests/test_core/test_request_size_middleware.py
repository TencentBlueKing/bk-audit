import logging
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from blueapps.utils.logger import logger
from django.test import RequestFactory

from core.middleware.request_size import RequestSizeLoggingMiddleware

DEFAULT_LIMIT = 2_621_440
JSON = "application/json"
FORM = "application/x-www-form-urlencoded"


class HeaderOnlyRequest(SimpleNamespace):
    def __getattr__(self, name):
        raise AssertionError(f"Middleware accessed more than request metadata: {name}")


@pytest.fixture
def observe_request(settings, caplog, monkeypatch):
    settings.LOG_LARGE_REQUEST_BODY = True
    settings.DATA_UPLOAD_MAX_MEMORY_SIZE = DEFAULT_LIMIT
    caplog.set_level(logging.INFO, logger=logger.name)
    monkeypatch.setattr(logger, "handlers", [caplog.handler])
    monkeypatch.setattr(logger, "propagate", False)

    def observe(length, content_type=JSON, method="POST"):
        http_request = RequestFactory().generic(method, "/api/submit/?value=omit-this-value", CONTENT_TYPE=content_type)
        meta = http_request.META
        if length is None:
            meta.pop("CONTENT_LENGTH", None)
        else:
            meta["CONTENT_LENGTH"] = length
        request = HeaderOnlyRequest(method=http_request.method, path=http_request.path, META=meta)
        downstream = Mock()

        response = RequestSizeLoggingMiddleware(downstream)(request)

        downstream.assert_called_once_with(request)
        assert downstream.call_args.args[0] is request
        assert response is downstream.return_value
        return caplog.records

    return observe


@pytest.mark.parametrize(
    ("length", "content_type", "method"),
    [
        ("0", JSON, "POST"),
        (str(1024 * 1024 - 1), JSON, "POST"),
        (str(DEFAULT_LIMIT + 1), JSON, "GET"),
        (None, FORM, "DELETE"),
    ],
)
def test_requests_outside_observation_scope_are_quiet(observe_request, length, content_type, method):
    assert observe_request(length, content_type, method) == []


@pytest.mark.parametrize("length", [None, str(DEFAULT_LIMIT + 1)])
def test_disabled_middleware_is_quiet(observe_request, settings, length):
    settings.LOG_LARGE_REQUEST_BODY = False

    assert observe_request(length) == []


@pytest.mark.parametrize(
    ("length", "content_type", "method", "media_type", "level"),
    [
        (1024 * 1024, JSON, "POST", JSON, logging.INFO),
        (DEFAULT_LIMIT - 1, JSON, "POST", JSON, logging.INFO),
        (DEFAULT_LIMIT, JSON, "POST", JSON, logging.INFO),
        (DEFAULT_LIMIT, FORM, "PUT", FORM, logging.INFO),
        (DEFAULT_LIMIT + 1, "Application/JSON; charset=utf-8", "PATCH", JSON, logging.WARNING),
        (DEFAULT_LIMIT + 1, FORM, "PUT", FORM, logging.WARNING),
        (DEFAULT_LIMIT + 1, "multipart/form-data; boundary=example", "POST", "multipart/form-data", logging.INFO),
        (DEFAULT_LIMIT + 1, "", "POST", "", logging.INFO),
    ],
)
def test_log_levels_and_fields(observe_request, length, content_type, method, media_type, level):
    (record,) = observe_request(str(length), content_type, method)

    assert record.levelno == level
    assert record.message.startswith("SEC012_REQUEST_SIZE")
    assert ("可能返回 413" in record.message) == (level == logging.WARNING)
    assert "omit-this-value" not in record.message
    assert record.method == method
    assert record.request_path == "/api/submit/"
    assert record.content_type == media_type
    assert record.content_length == length
    assert record.length_status == "declared"


@pytest.mark.parametrize(
    ("length", "status", "message"),
    [
        (None, "missing", "未声明"),
        ("", "missing", "未声明"),
        ("-1", "invalid", "无效"),
        ("abc", "invalid", "无效"),
        ("123,456", "invalid", "无效"),
        ("1_000_000", "invalid", "无效"),
    ],
)
def test_unknown_length_is_logged_separately(observe_request, length, status, message):
    (record,) = observe_request(length)

    assert record.levelno == logging.INFO
    assert record.message.startswith("SEC012_REQUEST_SIZE")
    assert message in record.message
    assert record.content_length is None
    assert record.length_status == status


@pytest.mark.parametrize(("limit", "level"), [(None, logging.INFO), (2_000_000, logging.WARNING)])
def test_warning_uses_the_effective_django_limit(observe_request, settings, limit, level):
    settings.DATA_UPLOAD_MAX_MEMORY_SIZE = limit

    (record,) = observe_request(str(DEFAULT_LIMIT))

    assert record.levelno == level
