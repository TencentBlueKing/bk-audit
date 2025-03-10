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

import os

# V3判断环境的环境变量为BKPAAS_ENVIRONMENT
import sys
from warnings import warn

import environ
import pymysql

# 读取环境变量文件
# 配置优先级 环境变量 -> .env文件 -> settings.py
environ.Env.read_env()

if "BKPAAS_ENVIRONMENT" in os.environ:
    ENVIRONMENT = os.getenv("BKPAAS_ENVIRONMENT", "dev")
# V2判断环境的环境变量为BK_ENV
else:
    PAAS_V2_ENVIRONMENT = os.environ.get("BK_ENV", "development")
    ENVIRONMENT = {
        "development": "dev",
        "testing": "stag",
        "production": "prod",
    }.get(PAAS_V2_ENVIRONMENT)
DJANGO_CONF_MODULE = "config.{env}".format(env=ENVIRONMENT)

# 模块化
DEPLOY_SERVICE = os.getenv("BKAPP_DEPLOY_SERVICE")
if DEPLOY_SERVICE not in os.listdir("services"):
    raise SystemError("Deploy Service Unknown => %s" % DEPLOY_SERVICE)
# 添加代码源
sys.path.append(os.path.join(os.getcwd(), f"services/{DEPLOY_SERVICE}"))
sys.path.append(os.path.join(os.getcwd(), "apps"))

# pysql 初始化
pymysql.install_as_MySQLdb()


def load_settings(module_path: str, raise_exception: bool = True):
    try:
        module = __import__(module_path, globals(), locals(), ["*"])
    except ImportError as err:
        msg = "Could not import config '{}' (Is it on sys.path?): {}".format(module_path, err)
        if raise_exception:
            raise ImportError(msg)
        warn(msg)
        return
    for setting in dir(module):
        if setting == "INSTALLED_APPS" and setting in globals():
            globals()[setting] = (*globals()[setting], *getattr(module, setting))
        elif setting == setting.upper():
            globals()[setting] = getattr(module, setting)


load_settings(module_path=DJANGO_CONF_MODULE)
load_settings(module_path=f"services.{DEPLOY_SERVICE}.settings", raise_exception=False)


# 屏蔽DRF新版本路由注册的不兼容逻辑
def is_already_registered(self, new_basename):
    return False


from bk_resource.routers import ResourceRouter  # noqa

ResourceRouter.is_already_registered = is_already_registered

# 目前 Django 仅是对 5.7 做了软性的不兼容改动，在没有使用 8.0 特异的功能时，对 5.7 版本的使用无影响，这边做个patch兼容5.7
from django.db.backends.mysql.features import DatabaseFeatures  # noqa
from django.utils.functional import cached_property  # noqa


class PatchFeatures:
    @cached_property
    def minimum_database_version(self):
        if self.connection.mysql_is_mariadb:
            return (10, 4)
        else:
            return (5, 7)


DatabaseFeatures.minimum_database_version = PatchFeatures.minimum_database_version
