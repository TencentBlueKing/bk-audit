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

from blueapps.conf.log import get_logging_config_dict
from blueapps.conf.validators import EnvValidator

from config import RUN_VER

# 环境变量检测
EnvValidator(RUN_VER).validate()

if RUN_VER == "open":
    from blueapps.patch.settings_open_saas import *  # noqa
else:
    from blueapps.patch.settings_paas_services import *  # noqa

# 本地开发环境
RUN_MODE = "DEVELOP"

# 自定义本地环境日志级别
# from blueapps.conf.log import set_log_level # noqa
# LOG_LEVEL = "DEBUG"
# LOGGING = set_log_level(locals())

# APP本地静态资源目录
STATIC_URL = "/static/"

# APP静态资源目录url
REMOTE_STATIC_URL = "%sremote/" % STATIC_URL

# 日常开发 Broker 与真实 Celery 测试 Broker 分离：普通本地任务可继续使用 Redis，
# 集成测试只在受控上下文内临时切换到与生产一致的 RabbitMQ。
BROKER_URL = os.getenv("BKAPP_CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_TEST_BROKER_URL = os.getenv(
    "BKAPP_CELERY_TEST_BROKER_URL",
    "amqp://guest:guest@127.0.0.1:5672//",
)
CELERY_TEST_QUEUE_PREFIX = os.getenv(
    "BKAPP_CELERY_TEST_QUEUE_PREFIX",
    f"{APP_CODE}_test",
)
CELERY_TEST_TASK_TIMEOUT = int(os.getenv("BKAPP_CELERY_TEST_TASK_TIMEOUT", "30"))

DEBUG = True

LOGGING["formatters"]["verbose"] = get_logging_config_dict(locals())["formatters"]["verbose"]

if "bk_audit.contrib.bk_audit" in INSTALLED_APPS:
    INSTALLED_APPS = list(INSTALLED_APPS)
    INSTALLED_APPS.remove("bk_audit.contrib.bk_audit")

# 本地开发数据库设置
# USE FOLLOWING SQL TO CREATE THE DATABASE NAMED APP_CODE
# SQL: CREATE DATABASE `bk-cmdb-fast` DEFAULT CHARACTER SET utf8 COLLATE utf8_general_ci; # noqa: E501
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("MYSQL_NAME", APP_CODE),
        "USER": os.getenv("MYSQL_USER", "root"),
        "PASSWORD": os.getenv("MYSQL_PASSWORD", ""),
        "HOST": os.getenv("MYSQL_HOST", "localhost"),
        "PORT": os.getenv("MYSQL_PORT", "3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
        },
        # pytest 会独立创建测试库，不能依赖业务库的字符集配置。
        # 显式指定后可避免 MySQL 5.7 默认 latin1 导致中文迁移数据写入失败。
        "TEST": {
            "CHARSET": "utf8mb4",
            "COLLATION": "utf8mb4_general_ci",
        },
    },
}

# 跨域
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [origin for origin in str(os.getenv("BKAPP_CORS_ALLOWED_ORIGINS", "")).split(",") if origin]
CSRF_TRUSTED_ORIGINS = [origin for origin in str(os.getenv("BKAPP_CSRF_TRUSTED_ORIGINS", "")).split(",") if origin]

# 多人开发时，无法共享的本地配置可以放到新建的 local_settings.py 文件中
# 并且把 local_settings.py 加入版本管理忽略文件中
try:
    from config.local_settings import *  # noqa
except ImportError:
    pass
