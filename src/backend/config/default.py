# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import sys

from bk_audit.constants.utils import LOGGER_NAME
from bkcrypto.constants import AsymmetricCipherType, SymmetricCipherType
from blueapps.conf.default_settings import *  # noqa
from blueapps.conf.log import get_logging_config_dict
from client_throttler import ThrottlerConfig, setup
from django.utils.translation import gettext_lazy
from redis.client import Redis

from core.utils.distutils import strtobool
from core.utils.environ import get_env_or_raise

# 请在这里加入你的自定义 APP

INSTALLED_APPS = ("simpleui",) + INSTALLED_APPS
INSTALLED_APPS += (
    "corsheaders",
    "sslserver",
    "apps.audit",
    "apps.meta",
    "apps.permission",
    "apps.notice",
    "apps.feature",
    "apps.bk_crypto",
    "apps.sops",
    "apps.itsm",
    "apps.user_manage",
    "bk_resource",
    "rest_framework",
    "drf_yasg",
    "blueapps.opentelemetry.instrument_app",
    "apigw_manager.apigw",
    "bk_notice_sdk",
    "bk_audit.contrib.bk_audit",
)

MIDDLEWARE = (
    "core.middleware.csrf.CSRFExemptMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "core.middleware.login_exempt.LoginExemptMiddleware",
) + MIDDLEWARE
MIDDLEWARE += (
    "apigw_manager.apigw.authentication.ApiGatewayJWTGenericMiddleware",  # JWT 认证
    "apigw_manager.apigw.authentication.ApiGatewayJWTAppMiddleware",  # JWT 透传的应用信息
    "apigw_manager.apigw.authentication.ApiGatewayJWTUserMiddleware",  # JWT 透传的用户信息
)

# 默认数据库自增字段
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# 所有环境的日志级别可以在这里配置
LOG_LEVEL = "INFO"

# 静态资源文件(js,css等）在APP上线更新后, 由于浏览器有缓存,
# 可能会造成没更新的情况. 所以在引用静态资源的地方，都把这个加上
# Django 模板中：<script src="/a.js?v=${STATIC_VERSION}"></script>
# 如果静态资源修改了以后，上线前改这个版本号即可
STATIC_VERSION = "1.0"

if strtobool(os.getenv("BKAPP_IS_KUBERNETES", "False")):
    STATIC_ROOT = "static"
else:
    STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]  # noqa

# CELERY 开关，使用时请改为 True，修改项目目录下的 Procfile 文件，添加以下两行命令：
# worker: python manage.py celery worker -l info
# beat: python manage.py celery beat -l info
# 不使用时，请修改为 False，并删除项目目录下的 Procfile 文件中 celery 配置
IS_USE_CELERY = True

# CELERY 并发数，默认为 2，可以通过环境变量或者 Procfile 设置
CELERYD_CONCURRENCY = os.getenv("BK_CELERYD_CONCURRENCY", 2)  # noqa

# CELERY 配置，申明任务的文件路径，即包含有 @task 装饰器的函数文件
CELERY_IMPORTS = ()

# 允许传递对象给任务
CELERY_TASK_SERIALIZER = "pickle"
CELERY_ACCEPT_CONTENT = ["pickle", "json"]

# load logging settings
LOGGING = get_logging_config_dict(locals())
# 日志使用json格式
LOGGING["formatters"]["verbose"] = {"()": "core.log.JsonLogFormatter"}
# 添加额外的logger
LOGGING["loggers"]["bk_resource"] = LOGGING["loggers"]["app"]
LOGGING["loggers"][LOGGER_NAME] = LOGGING["loggers"]["app"]
# 避免多次输出
for _l in LOGGING["loggers"].values():
    _l["propagate"] = False
# 容器使用标准输出
if strtobool(os.getenv("BKAPP_IS_KUBERNETES", "False")):
    LOGGING["formatters"]["json"] = {"()": "core.log.JsonLogFormatter"}
    LOGGING["handlers"] = {
        "stdout": {"level": LOG_LEVEL, "class": "logging.StreamHandler", "formatter": "json", "stream": sys.stdout}
    }
    for _l in LOGGING["loggers"].values():
        _l["handlers"] = ["stdout"]

# 初始化管理员列表，列表中的人员将拥有预发布环境和正式环境的管理员权限
# 注意：请在首次提测和上线前修改，之后的修改将不会生效
INIT_SUPERUSER = []

# BKUI是否使用了history模式
IS_BKUI_HISTORY_MODE = False

# 是否需要对AJAX弹窗登录强行打开
IS_AJAX_PLAIN_MODE = True

# 国际化配置
LOCALE_PATHS = (os.path.join(BASE_DIR, "locale"),)  # noqa

USE_TZ = True
TIME_ZONE = "Asia/Shanghai"
LANGUAGE_CODE = os.getenv("BKAPP_LANGUAGE_CODE", "zh-cn")

LANGUAGES = (
    ("en", "English"),
    ("zh-cn", "简体中文"),
)
LANGUAGE_COOKIE_NAME = os.getenv("BKAPP_LANGUAGE_COOKIE_NAME", "blueking_language")

REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": "blueapps.contrib.drf.exception.custom_exception_handler",
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "blueapps.contrib.drf.utils.pagination.CustomPageNumberPagination",
    "PAGE_SIZE": 100,
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework.authentication.SessionAuthentication",),
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DATETIME_FORMAT": "%Y-%m-%d %H:%M:%S",
    "NON_FIELD_ERRORS_KEY": "params_error",
    "DEFAULT_PARSER_CLASSES": (
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ),
    "DEFAULT_RENDERER_CLASSES": ("core.utils.renderers.APIRenderer",),
    # 版本管理
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",
    "DEFAULT_VERSION": "v1",
    "ALLOWED_VERSIONS": ["v1"],
    "VERSION_PARAM": "api_version",
}

# 平台错误代码: 7位整数，前两位表示产品代号，后5为各产品自行分配
PLATFORM_CODE = "29"

# APIGW配置
BK_APIGW_NAME = os.getenv("BKAPP_BK_APIGW_NAME", "bk-audit")
BK_API_URL_TMPL = os.getenv("BK_API_URL_TMPL", "")
APIGW_DEFINITION_SETTINGS = {"BK_APIGW_NAME": BK_APIGW_NAME}

# ESB配置
BK_COMPONENT_API_URL = os.getenv("BKAPP_BK_COMPONENT_API_URL", os.getenv("BK_COMPONENT_API_URL"))

SWAGGER_SETTINGS = {
    "DEFAULT_INFO": "urls.info",
    "DEFAULT_GENERATOR_CLASS": "bk_resource.utils.generators.BKResourceOpenAPISchemaGenerator",
}

DEFAULT_NAMESPACE = os.getenv("BKAPP_DEFAULT_NAMESPACE", "default")
DEFAULT_BK_BIZ_ID = int(os.getenv("BKAPP_DEFAULT_BK_BIZ_ID", 2))

SESSION_COOKIE_DOMAIN = os.getenv("BKAPP_SESSION_COOKIE_DOMAIN", os.getenv("BKPAAS_BK_DOMAIN"))
CSRF_COOKIE_DOMAIN = SESSION_COOKIE_DOMAIN
LANGUAGE_COOKIE_DOMAIN = SESSION_COOKIE_DOMAIN

BK_RESOURCE = {
    "REQUEST_VERIFY": strtobool(os.getenv("BKAPP_API_REQUEST_VERIFY", "True")),
    "REQUEST_LOG_SPLIT_LENGTH": int(os.getenv("BKAPP_REQUEST_LOG_SPLIT_LENGTH", 1024)),
    "PLATFORM_AUTH_ENABLED": strtobool(os.getenv("BKAPP_PLATFORM_AUTH_ENABLED", "True")),
    "PLATFORM_AUTH_ACCESS_TOKEN": os.getenv("BKAPP_PLATFORM_AUTH_ACCESS_TOKEN"),
    "PLATFORM_AUTH_ACCESS_USERNAME": os.getenv("BKAPP_PLATFORM_AUTH_ACCESS_USERNAME", "admin"),
}

APPEND_SLASH = False

FETCH_INSTANCE_USERNAME = os.getenv("BKAPP_FETCH_INSTANCE_USERNAME", "bk_iam")

REDIS_HOST = get_env_or_raise("REDIS_HOST")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
REDIS_DB = os.getenv("REDIS_DB", "0")

CACHES["db"] = {
    "BACKEND": "django.core.cache.backends.db.DatabaseCache",
    "LOCATION": "django_cache",
    "OPTIONS": {"MAX_ENTRIES": 100000, "CULL_FREQUENCY": 10},
    "TIMEOUT": 3600,
}
CACHES["redis"] = {
    "BACKEND": "django_redis.cache.RedisCache",
    "LOCATION": f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}",
    "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient", "PASSWORD": REDIS_PASSWORD},
    "KEY_PREFIX": os.getenv("REDIS_KEY_PREFIX", ""),
    "TIMEOUT": 3600,
}
CACHES["default"] = CACHES["redis"]
CACHES["login_db"] = CACHES["redis"]

# BkBase
BK_BASE_ACCESS_URL = os.getenv("BKAPP_BK_BASE_ACCESS_URL", "/#/data-hub-detail/index/")
HTTP_PULL_REDIS_TIMEOUT = os.getenv("BKAPP_HTTP_PULL_REDIS_TIMEOUT", "360d")

# IAM
BK_IAM_SYSTEM_ID = os.getenv("BKAPP_IAM_SYSTEM_ID", "bk-audit")
BK_IAM_SYSTEM_NAME = os.getenv("BKAPP_IAM_SYSTEM_NAME", "审计中心")
BK_IAM_USE_APIGATEWAY = True
BK_IAM_APIGATEWAY_URL = os.getenv("BKAPP_BK_IAM_APIGATEWAY_URL")
BK_IAM_RESOURCE_API_HOST = os.getenv("BKAPP_BK_IAM_RESOURCE_API_HOST")

# Version
VERSION_MD_DIR = "version_md"

# UserCookie
AUTH_BACKEND_DOMAIN = SESSION_COOKIE_DOMAIN

# Trace
ENABLE_OTEL_TRACE = strtobool(os.getenv("BKAPP_ENABLE_OTEL_TRACE", "False"))
BK_APP_OTEL_INSTRUMENT_DB_API = strtobool(os.getenv("BKAPP_OTEL_INSTRUMENT_DB_API", "False"))
BKAPP_OTEL_SERVICE_NAME = os.getenv("BKAPP_OTEL_SERVICE_NAME", "bk-audit")
BK_APP_OTEL_ADDTIONAL_INSTRUMENTORS = []

# TAM
AEGIS_ID = os.getenv("BKAPP_AEGIS_ID")

# FeatureToggle
FEATURE_TOGGLE = {
    "bkbase_aiops": os.getenv("BKAPP_FEATURE_BKBASE_AIOPS", "deny"),
    "bklog_otlp": os.getenv("BKAPP_FEATURE_BKLOG_OTLP", "on"),
    "watermark": os.getenv("BKAPP_FEATURE_WATERMARK", "deny"),
    "bkvision": os.getenv("BKAPP_FEATURE_BKVISION", "deny"),
    "bknotice": os.getenv("BKAPP_FEATURE_BKNOTICE", "deny"),
}

# BkLog
BKLOG_PERMISSION_VERSION = os.getenv("BKAPP_BKLOG_PERMISSION_VERSION", "2")

# Index
INDEX_VERSION_NUMBER = os.getenv("BKAPP_INDEX_VERSION_NUMBER", "v1")

# Event
BK_MONITOR_METRIC_PROXY_URL = os.getenv("BKAPP_BK_MONITOR_METRIC_PROXY_URL", "")

# BkBase
BKBASE_PROJECT_ID = os.getenv("BKAPP_BKBASE_PROJECT_ID")
BKBASE_PROJECT_NAME = os.getenv("BKAPP_BKBASE_PROJECT_NAME", gettext_lazy("审计中心"))
BKBASE_STREAM_RESOURCE_SET_ID = os.getenv("BKAPP_BKBASE_STREAM_RESOURCE", "default_stream")
BKBASE_BATCH_RESOURCE_SET_ID = os.getenv("BKAPP_BKBASE_BATCH_RESOURCE", "default_batch")
BKBASE_UDF_JSON_EXTRACT_FUNC = os.getenv("BKAPP_BKBASE_UDF_JSON_EXTRACT_FUNC", "udf_json_extract_one")
BKBASE_UDF_BUILD_ORIGIN_DATA_FUNC = os.getenv("BKAPP_BKBASE_UDF_BUILD_ORIGIN_DATA_FUNC", "udf_build_origin_data")
BKBASE_BUILD_ORIGIN_DATA_SEPERATOR = os.getenv("BKAPP_BKBASE_BUILD_ORIGIN_DATA_SEPERATOR", "|!@#$%^&*|")

# Auth
AUTHENTICATION_BACKENDS += ("apigw_manager.apigw.authentication.UserModelBackend",)

# SnapshotUserInfo
SNAPSHOT_USERINFO_RESOURCE_URL = os.getenv("BKAPP_FETCH_USER_INFO_URL", "")
SNAPSHOT_USERINFO_RESOURCE_TOKEN = os.getenv("BKAPP_FETCH_USER_INFO_TOKEN", "")

# Notice
NOTICE_AGG_MINUTES = int(os.getenv("BKAPP_NOTICE_AGG_MINUTES", 30))

# Asset
ASSET_RT_STORAGE_CLUSTER = os.getenv("BKAPP_ASSET_RT_STORAGE_CLUSTER", "")
ASSET_RT_EXPIRE_TIME = os.getenv("BKAPP_ASSET_RT_EXPIRE_TIME", "-1")

# Metadata
CLUSTER_REGISTRY_APP = os.getenv("BKAPP_CLUSTER_REGISTRY_APP", "log-search-4")

# BKCrypto
ENABLE_BKCRYPTO = strtobool(os.getenv("BKAPP_ENABLE_BKCRYPTO", "False"))
BKCRYPTO = {
    "ASYMMETRIC_CIPHER_TYPE": AsymmetricCipherType.SM2.value,
    "SYMMETRIC_CIPHER_TYPE": SymmetricCipherType.SM4.value,
}

# 初始化安全接口人，首次 Migrate 执行后，需要前往 DB 修改
INIT_SECURITY_PERSON = [p for p in os.getenv("BKAPP_INIT_SECURITY_PERSON", "admin").split(",") if p]

# SAAS Code
BKBASE_APP_CODE = os.getenv("BKAPP_BKBASE_APP_CODE", "bk_dataweb")
BK_ITSM_APP_CODE = os.getenv("BKAPP_BK_ITSM_APP_CODE", "bk_itsm")
BK_SOPS_APP_CODE = os.getenv("BKAPP_BK_SOPS_APP_CODE", "bk_sops")

# Risk
ENABLE_PROCESS_RISK_TASK = strtobool(os.getenv("BKAPP_ENABLE_PROCESS_RISK_TASK", "True"))
ENABLE_PROCESS_RISK_WHITELIST = strtobool(os.getenv("BKAPP_ENABLE_PROCESS_RISK_WHITELIST", "False"))
PROCESS_RISK_WHITELIST = [int(i) for i in os.getenv("BKAPP_PROCESS_RISK_WHITELIST", "").split(",") if i]
PROCESS_RISK_MAX_RETRY = int(os.getenv("BKAPP_PROCESS_RISK_MAX_RETRY", 3))
ENABLE_MULTI_PROCESS_RISK = strtobool(os.getenv("BKAPP_ENABLE_MULTI_PROCESS_RISK", "True"))

# cache lock
DEFAULT_CACHE_LOCK_TIMEOUT = int(os.getenv("BKAPP_DEFAULT_CACHE_LOCK_TIMEOUT", 60 * 60))

# Throttler
throttler_config = ThrottlerConfig(
    redis_client=Redis(host=REDIS_HOST, port=int(REDIS_PORT), password=REDIS_PASSWORD, db=int(REDIS_DB))
)
setup(throttler_config)
SOPS_API_RATE_LIMIT = os.getenv("BKAPP_SOPS_API_RATE_LIMIT", "10/s")
SOPS_API_MAX_RETRY_DURATION = float(os.getenv("BKAPP_SOPS_API_MAX_RETRY_DURATION", 5 * 60))
SOPS_OPERATE_API_RATE_LIMIT = os.getenv("BKAPP_SOPS_OPERATE_API_RATE_LIMIT", "10/s")
ITSM_API_RATE_LIMIT = os.getenv("BKAPP_ITSM_API_RATE_LIMIT", "10/s")

# Retry
DEFAULT_MAX_RETRY = int(os.getenv("BKAPP_DEFAULT_MAX_RETRY", 3))
DEFAULT_RETRY_SLEEP_TIME = float(os.getenv("BKAPP_DEFAULT_RETRY_SLEEP_TIME", 0.5))
DEFAULT_MAX_RETRY_SLEEP_TIME = float(os.getenv("BKAPP_DEFAULT_MAX_RETRY_SLEEP_TIME", 1))
if DEFAULT_RETRY_SLEEP_TIME >= DEFAULT_MAX_RETRY_SLEEP_TIME:
    raise SystemError()

# BK Notice
BK_NOTICE = {
    "STAGE": {"dev": "stage", "stag": "stage", "prod": "prod"}[os.getenv("BKPAAS_ENVIRONMENT", "dev")],
    "ENTRANCE_URL": "bk-notice/",
    "DEFAULT_LANGUAGE": LANGUAGE_CODE,
}

# APIGW
# 用于网关Host
BKAUDIT_API_HOST = os.getenv("BKAPP_BKAUDIT_API_HOST", "")

# BK Audit
BK_AUDIT_SETTINGS = {
    "formatter": "apps.audit.formatters.AuditFormatter",
}

# 全局配置
BK_SHARED_RES_URL = os.getenv("BKAPP_BK_SHARED_RES_URL", os.getenv("BKPAAS_SHARED_RES_URL", ""))

"""
以下为框架代码 请勿修改
"""
# celery settings
if IS_USE_CELERY:
    # INSTALLED_APPS = locals().get("INSTALLED_APPS", [])
    # INSTALLED_APPS += (
    #     "django_celery_beat",
    #     "django_celery_results",
    # )
    CELERY_ENABLE_UTC = True
    # CELERYBEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# remove disabled apps
if locals().get("DISABLED_APPS"):
    INSTALLED_APPS = locals().get("INSTALLED_APPS", [])
    DISABLED_APPS = locals().get("DISABLED_APPS", [])

    INSTALLED_APPS = [_app for _app in INSTALLED_APPS if _app not in DISABLED_APPS]

    _keys = (
        "AUTHENTICATION_BACKENDS",
        "DATABASE_ROUTERS",
        "FILE_UPLOAD_HANDLERS",
        "MIDDLEWARE",
        "PASSWORD_HASHERS",
        "TEMPLATE_LOADERS",
        "STATICFILES_FINDERS",
        "TEMPLATE_CONTEXT_PROCESSORS",
    )

    import itertools

    for _app, _key in itertools.product(DISABLED_APPS, _keys):
        if locals().get(_key) is None:
            continue
        locals()[_key] = tuple([_item for _item in locals()[_key] if not _item.startswith(_app + ".")])
