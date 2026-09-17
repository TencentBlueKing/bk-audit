"""生产栈 SSE 专项测试使用的 WSGI 入口。

该入口只把独立 Gunicorn 进程绑定到当前 Django 测试库，并替换 AI 助手
接口的登录用户。业务对象仍由 pytest 主进程创建，不在子进程注册测试 Handler。
"""

import os

from django.conf import settings

TEST_DATABASE_ENV = "BKAPP_TEST_DATABASE_NAME"
SSE_TEST_USERNAME_ENV = "BKAPP_AI_ASSISTANT_SSE_TEST_USERNAME"

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

settings.DATABASES["default"]["NAME"] = os.environ[TEST_DATABASE_ENV]
settings.ALLOWED_HOSTS = ["*"]
settings.MIDDLEWARE = tuple(
    middleware
    for middleware in settings.MIDDLEWARE
    if "Login" not in middleware and "JWTUser" not in middleware and "JWTApp" not in middleware
)

from blueapps.core.wsgi import get_wsgi_application  # noqa: E402
from rest_framework.permissions import AllowAny  # noqa: E402

_django_application = get_wsgi_application()

from services.web.ai_assistant.resources import attachment, stream  # noqa: E402
from services.web.ai_assistant.views import AttachmentsViewSet  # noqa: E402

_username = os.environ[SSE_TEST_USERNAME_ENV]
attachment.get_request_username = lambda: _username
stream.get_request_username = lambda: _username
AttachmentsViewSet.authentication_classes = []
AttachmentsViewSet.permission_classes = [AllowAny]


def application(environ, start_response):
    """健康检查证明 Django worker 已完成加载，其余请求进入真实应用。"""

    if environ.get("PATH_INFO") == "/__ai_assistant_sse_health__":
        start_response("204 No Content", [("Content-Length", "0")])
        return [b""]
    return _django_application(environ, start_response)
