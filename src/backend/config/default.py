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
import json
import sys

from bk_audit.constants.utils import LOGGER_NAME
from bkcrypto.constants import AsymmetricCipherType, SymmetricCipherType
from blueapps.conf.default_settings import *  # noqa
from blueapps.conf.log import get_logging_config_dict
from client_throttler import ThrottlerConfig, setup
from client_throttler.constants import TimeDurationUnit
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
    "drf_spectacular",
    "drf_spectacular_sidecar",
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

# 最大任务数
SELF_MANAGED_MAX_TASKS = int(os.getenv("BKAPP_SELF_MANAGED_MAX_TASKS", 10000))

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
    "DEFAULT_SCHEMA_CLASS": "core.utils.spectacular.BKResourceAutoSchema",
}

# 平台错误代码: 7位整数，前两位表示产品代号，后5为各产品自行分配
PLATFORM_CODE = "29"

# APIGW配置
BK_APIGW_NAME = os.getenv("BKAPP_BK_APIGW_NAME", "bk-audit")
# 多租户配置
MULTI_TENANT_ENABLED = strtobool(os.getenv("BKAPP_MULTI_TENANT_ENABLED", "False"))
# 单租户ID
BK_TENANT_ID = os.getenv("BKPAAS_APP_TENANT_ID") or "tencent"

BK_API_URL_TMPL = os.getenv("BK_API_URL_TMPL", "")
APIGW_DEFINITION_SETTINGS = {"BK_APIGW_NAME": BK_APIGW_NAME}
USE_APIGW = strtobool(os.getenv("BKAPP_USE_APIGW", "False"))
USERMANAGE_APIGW_NAME = os.getenv("BKAPP_USERMANAGE_APIGW_NAME", "bk-user")

# ESB配置
BK_COMPONENT_API_URL = os.getenv("BKAPP_BK_COMPONENT_API_URL", os.getenv("BK_COMPONENT_API_URL"))

BK_IAM_APIGW_NAME = os.getenv("BKAPP_BK_IAM_APIGW_NAME", "bk-iam")
LOG_APIGW_NAME = os.getenv("BKAPP_LOG_APIGW_NAME", "log-search")
BK_PAAS_APIGW_NAME = os.getenv("BKAPP_BK_PAAS_APIGW_NAME", "bkpaas3")
BK_BASE_APIGW_NAME = os.getenv("BKAPP_BK_BASE_APIGW_NAME", "bk-base")
BK_MONITOR_APIGW_NAME = os.getenv("BKAPP_BK_MONITOR_APIGW_NAME", "bkmonitorv3")
DEVSECOPS_APIGW_NAME = os.getenv("BKAPP_DEVSECOPS_APIGW_NAME", "devsecops")
BK_LOG_API_URL = os.getenv("BKAPP_LOG_API_URL")
BK_BASE_API_URL = os.getenv("BKAPP_BASE_API_URL")
BK_CMSI_API_URL = os.getenv("BKAPP_CMSI_URL")
BK_SOPS_API_URL = os.getenv("BKAPP_BK_SOPS_API_URL")
BK_SOPS_APIGW_NAME = os.getenv("BKAPP_BK_SOPS_APIGW_NAME", "bk-sops")
BK_ITSM_APIGW_NAME = os.getenv("BKAPP_BK_ITSM_APIGW_NAME", "bk-itsm")
BKIAM_APIGW_NAME = os.getenv("BKAPP_BKIAM_APIGW_NAME", "bkiam")
BK_VISION_API_NAME = os.getenv("BKAPP_BK_VISION_API_NAME", "bk-vision")
BK_VISION_API_URL = os.getenv("BKAPP_BK_VISION_API_URL")

# AI Audit Report (智能体)
AI_AUDIT_REPORT_APIGW_NAME = os.getenv("BKAPP_AI_AUDIT_REPORT_APIGW_NAME", "bp-ai-audit-report")
AI_AUDIT_REPORT_API_URL = os.getenv("BKAPP_AI_AUDIT_REPORT_API_URL", "")
AI_AUDIT_REPORT_APP_CODE = os.getenv("BKAPP_AI_AUDIT_REPORT_APP_CODE", "")
AI_AUDIT_REPORT_SECRET_KEY = os.getenv("BKAPP_AI_AUDIT_REPORT_SECRET_KEY", "")

# ESB component names
BK_LOG_ESB_NAME = os.getenv("BKAPP_BK_LOG_ESB_NAME", "bk_log")
USERMANAGE_ESB_NAME = os.getenv("BKAPP_USERMANAGE_ESB_NAME", "usermanage")
MONITOR_V3_ESB_NAME = os.getenv("BKAPP_MONITOR_V3_ESB_NAME", "monitor_v3")
ITSM_ESB_NAME = os.getenv("BKAPP_ITSM_ESB_NAME", "itsm")
CMSI_ESB_NAME = os.getenv("BKAPP_CMSI_ESB_NAME", "cmsi")

SWAGGER_SETTINGS = {
    "DEFAULT_INFO": "urls.info",
    "DEFAULT_GENERATOR_CLASS": "bk_resource.utils.generators.BKResourceOpenAPISchemaGenerator",
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Audit',
    'DESCRIPTION': '审计中心 API',
    'VERSION': 'v1',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'ENABLE_PYDANTIC_V2': True,
    'SWAGGER_UI_DIST': 'SIDECAR',
    'SWAGGER_UI_FAVICON_HREF': 'SIDECAR',
    'REDOC_DIST': 'SIDECAR',
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

DATABASES["default"]["ENGINE"] = "dj_db_conn_pool.backends.mysql"
DATABASES["default"]['POOL_OPTIONS'] = {
    'POOL_SIZE': int(os.getenv("BKAPP_DB_POOL_SIZE", 64)),
    'MAX_OVERFLOW': int(os.getenv("BKAPP_DB_MAX_OVERFLOW", 64)),
    'RECYCLE': 60 * 60,
}

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
    "bkbase_data_source": os.getenv("BKAPP_FEATURE_BKBASE_DATA_SOURCE", "on"),
    "storage_edit": os.getenv("BKAPP_FEATURE_STORAGE_EDIT", "deny"),
    "enable_doris": os.getenv("BKAPP_FEATURE_ENABLE_DORIS", "on"),
    "check_bkvision_share_permission": os.getenv("BKAPP_FEATURE_CHECK_BKVISION_SHARE_PERMISSION", "on"),
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
BKBASE_DATA_TOKEN = os.getenv("BKAPP_BKBASE_DATA_TOKEN", "")

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
PROCESS_RISK_MAX_RETRY = int(os.getenv("BKAPP_PROCESS_RISK_MAX_RETRY", 3))
ENABLE_MULTI_PROCESS_RISK = strtobool(os.getenv("BKAPP_ENABLE_MULTI_PROCESS_RISK", "True"))

# cache lock
DEFAULT_CACHE_LOCK_TIMEOUT = int(os.getenv("BKAPP_DEFAULT_CACHE_LOCK_TIMEOUT", 60 * 60))

# Throttler
throttler_config = ThrottlerConfig(
    redis_client=Redis(host=REDIS_HOST, port=int(REDIS_PORT), password=REDIS_PASSWORD, db=int(REDIS_DB)),
    placeholder_offset=int(os.getenv("BKAPP_THROTTLER_PLACEHOLDER_OFFSET", TimeDurationUnit.MINUTE.value)),
)
setup(throttler_config)
SOPS_API_RATE_LIMIT = os.getenv("BKAPP_SOPS_API_RATE_LIMIT", "10/s")
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
# 用于网关 Stag Host
BKAUDIT_API_STAG_HOST = os.getenv("BKAPP_BKAUDIT_API_STAG_HOST", "")
# 用于网关发布环境
BKAUDIT_API_RELEASE_STAGES = [stag for stag in os.getenv("BKAPP_BKAUDIT_API_RELEASE_STAGES", "").split(",") if stag]
# 用于网关资源文档
BK_APIGW_RESOURCE_DOCS_BASE_DIR = os.getenv("BKAPP_APIGW_RESOURCE_DOCS_BASE_DIR", "support-files/apigw/docs")

# BK Audit
BK_AUDIT_SETTINGS = {
    "formatter": "apps.audit.formatters.AuditFormatter",
}

# 全局配置
BK_SHARED_RES_URL = os.getenv("BKAPP_BK_SHARED_RES_URL", os.getenv("BKPAAS_SHARED_RES_URL", ""))

# CORS 允许的 header
CORS_ALLOW_HEADERS = [
    "x-requested-with",
    "content-type",
    "accept,origin",
    "authorization",
    "x-csrftoken",
    "user-agent",
    "accept-encoding",
    "time-zone",
    *os.getenv("BKAPP_CORS_ALLOW_HEADERS", "").split(","),
]

SECURE_CROSS_ORIGIN_OPENER_POLICY = "unsafe-none"

# 队列存储时长(天)
DEFAULT_QUEUE_STORAGE_EXPIRES = int(os.getenv("BKAPP_DEFAULT_QUEUE_STORAGE_EXPIRES", 1))
# HDFS存储时长(天) -1 表示不限制
DEFAULT_HDFS_STORAGE_EXPIRES = int(os.getenv("BKAPP_DEFAULT_HDFS_STORAGE_EXPIRES", -1))
# 审计 kafka 配置
KAFKA_CONFIG = json.loads(os.getenv("BKAPP_INIT_KAFKA_CONFIG", "{}"))
# 事件 kafka 拉取超时时长
EVENT_KAFKA_TIMEOUT_MS = int(os.getenv("BKAPP_EVENT_KAFKA_TIMEOUT_MS", 1000))
# 事件 kafka 最大拉取记录数
EVENT_KAFKA_MAX_RECORDS = int(os.getenv("BKAPP_EVENT_KAFKA_MAX_RECORDS", 10))
# 事件 kafka 拉取间隔时间
EVENT_KAFKA_SLEEP_TIME = float(os.getenv("BKAPP_EVENT_KAFKA_SLEEP_TIME", 0.5))

# 系统访问地址(用作 swagger 访问返回)
BK_BACKEND_URL = os.getenv("BKAPP_BACKEND_URL", BK_IAM_RESOURCE_API_HOST)

# [在Django5.x将去除]设置为true在Django 4.x发行周期中继续使用Pytz Tzinfo对象
USE_DEPRECATED_PYTZ = True

# 处理风险定时任务调度周期(分)
PROCESS_ONE_RISK_PERIODIC_TASK_MINUTE = os.getenv("BKAPP_PROCESS_ONE_RISK_PERIODIC_TASK_MINUTE", "*/10")

# 同步处理套餐结果定时任务调度周期(分)
SYNC_AUTO_RESULT_PERIODIC_TASK_MINUTE = os.getenv("BKAPP_SYNC_AUTO_RESULT_PERIODIC_TASK_MINUTE", "*/10")

# 图表结果缓存时间(秒)
VISION_CACHE_TIMEOUT = int(os.getenv("BKAPP_VISION_CACHE_TIMEOUT", "86400"))

# 处理日志导出任务定时任务调度周期(分)
PROCESS_LOG_EXPORT_TASK_MINUTE = os.getenv("BKAPP_PROCESS_LOG_EXPORT_TASK_MINUTE", "*/5")

# 处理日志导出任务缓存锁超时时间(秒)
PROCESS_LOG_EXPORT_TASK_LOCK_TIMEOUT = int(os.getenv("BKAPP_PROCESS_LOG_EXPORT_TASK_LOCK_TIMEOUT", 60 * 60 * 24 * 2))

# 处理日志导出任务最大重试次数
PROCESS_LOG_EXPORT_TASK_MAX_REPEAT_TIMES = int(os.getenv("BKAPP_PROCESS_LOG_EXPORT_TASK_MAX_REPEAT_TIMES", 3))

# 日志导出任务调度最大时间周期(秒)
LOG_EXPORT_TASK_MAX_PERIODIC_TIME = int(os.getenv("BKAPP_LOG_EXPORT_TASK_MAX_PERIODIC_TIME", 60 * 60 * 24 * 7))

# 日志导出任务分页大小
LOG_EXPORT_TASK_PAGE_SIZE = int(os.getenv("BKAPP_LOG_EXPORT_TASK_PAGE_SIZE", 100))

# 初始化系统管理员
SYSTEM_ADMIN = [p for p in os.getenv("BKAPP_SYSTEM_ADMIN", "admin").split(",") if p]

# 日志字段清除时间周期(秒)
LOG_FIELD_CLEAR_PERIODIC_TIME = int(os.getenv("BKAPP_LOG_FIELD_CLEAR_PERIODIC_TIME", 60 * 60 * 24))

# 日志导出最大条数
LOG_EXPORT_MAX_COUNT = int(os.getenv("BKAPP_LOG_EXPORT_MAX_COUNT", 100000))

# 日志导出任务过期时间(天)
LOG_EXPORT_MAX_DURATION = int(os.getenv("BKAPP_LOG_EXPORT_MAX_DURATION", 30))

# 处理过期导出任务调度周期(小时)
PROCESS_EXPIRED_LOG_TASK_HOUR = os.getenv("BKAPP_PROCESS_EXPIRED_LOG_TASK_HOUR", "*/24")

# 处理过期任务最大调度时间(天)
PROCESS_EXPIRED_LOG_TASK_MAX_DURATION = int(
    os.getenv("BKAPP_PROCESS_EXPIRED_LOG_TASK_MAX_DURATION", LOG_EXPORT_MAX_DURATION + 60)
)

# 日志导出任务时卡住任务的最大查询时间范围（天）
STUCK_TASK_SEARCH_DAYS = int(os.getenv("BKAPP_STUCK_TASK_SEARCH_DAYS", 7))

# 处理状态为运行中且卡住的日志导出任务调度周期(小时)
PROCESS_STUCK_LOG_TASK_HOUR = os.getenv("BKAPP_PROCESS_STUCK_LOG_TASK_HOUR", "*/1")

#  Alert Configuration
ALERT_DATA_ID = int(os.getenv("BKAPP_ALERT_DATA_ID", 0))

#  Alert Configuration
ALERT_ACCESS_TOKEN = os.getenv("BKAPP_ALERT_ACCESS_TOKEN", "")

# 日志导出状态上报的数据ID
LOG_EXPORT_STATUS_DATA_ID = int(os.getenv("BKAPP_LOG_EXPORT_STATUS_DATA_ID", 0))

# 日志导出状态上报的数据token
LOG_EXPORT_STATUS_ACCESS_TOKEN = os.getenv("BKAPP_LOG_EXPORT_STATUS_ACCESS_TOKEN", "")

# metric report
METRIC_REPORT_TRACE_URL = os.getenv("BKAPP_METRIC_REPORT_TRACE_URL", "")
# bkvision是否更新
BKVISION_UPDATE_CRON_MINUTE = os.getenv("BKAPP_BKVISION_UPDATE_CRON_MINUTE", "*/5")
# bkvision是否更新任务超时时间
BKVISION_UPDATE_TASK_TIMEOUT = int(os.getenv("BKAPP_BKVISION_UPDATE_TASK_TIMEOUT", 60 * 10))

# 反向拉取需要屏蔽的高危端口
HIGH_RISK_PORTS = {
    int(port)
    for port in os.getenv(
        "BKAPP_HIGH_RISK_PORTS",
        "21,22,23,25,69,135,137,138,139,161,162,389,465,514,587,636,873,1099,2181,2375,2376,27017,3306,3389,36000,4848,50070,50075,5432,56000,5900,5901,6379,7001,7002,9200,9300,10050,10051,10250,10255,11211",  # noqa
    ).split(
        ","
    )  # noqa
}

# 检查丢失场景的间隔时间
CHECK_LOST_SCENE_INTERVAL = int(os.getenv("BKAPP_CHECK_LOST_SCENE_INTERVAL", 10))

# 1 年过期，单位秒
RECENT_USED_TTL = int(os.getenv("BKAPP_RECENT_USED_TTL", 60 * 60 * 24 * 365))

# CORS 允许的 header
CORS_EXPOSE_HEADERS = ['Content-Disposition']

# Doris 事件表入库配置
EVENT_DORIS_EXPIRES = os.getenv("BKAPP_EVENT_DORIS_EXPIRES", "1080d")

# 日志订阅查询最大时间范围（毫秒），默认 30 天
LOG_SUBSCRIPTION_MAX_TIME_RANGE = int(os.getenv("BKAPP_LOG_SUBSCRIPTION_MAX_TIME_RANGE", 30 * 24 * 60 * 60 * 1000))

# API 工具执行默认超时时间
API_TOOL_EXECUTE_DEFAULT_TIMEOUT = int(os.getenv("BKAPP_API_TOOL_EXECUTE_DEFAULT_TIMEOUT", 120))
# API 工具非 JSON 数据默认最大返回字符数
API_TOOL_EXECUTE_DEFAULT_MAX_RETURN_CHAR = int(os.getenv("BKAPP_API_TOOL_EXECUTE_DEFAULT_MAX_RETURN_CHAR", 1000))

"""
以下为框架代码 请勿修改
"""
# celery settings
if IS_USE_CELERY:
    INSTALLED_APPS = locals().get("INSTALLED_APPS", [])
    INSTALLED_APPS += (
        "django_celery_beat",
        "django_celery_results",
    )
    CELERY_ENABLE_UTC = True
    CELERYBEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
    CELERY_RESULT_BACKEND = 'django-db'

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
