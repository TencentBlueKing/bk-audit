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
        if setting == setting.upper():
            globals()[setting] = getattr(module, setting)


load_settings(module_path=DJANGO_CONF_MODULE)
load_settings(module_path=f"services.{DEPLOY_SERVICE}.settings", raise_exception=False)
