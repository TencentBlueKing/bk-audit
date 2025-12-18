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

from __future__ import absolute_import

__all__ = ["celery_app", "RUN_VER", "APP_CODE", "SECRET_KEY", "BK_URL", "BASE_DIR"]

import os

# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
from blueapps.core.celery import celery_app

from core.utils.environ import get_env_or_raise

# 这些变量将由平台通过环境变量提供给应用，本地开发时需手动配置
APP_CODE = os.getenv("BKPAAS_APP_ID", "bk_audit")
# 应用用于调用云 API 的 Secret
SECRET_KEY = get_env_or_raise("BKPAAS_APP_SECRET")
# SaaS运行版本，如非必要请勿修改
RUN_VER = get_env_or_raise("BKPAAS_ENGINE_REGION")
if RUN_VER == "default":
    RUN_VER = "open"

# 蓝鲸SaaS平台URL，例如 http://paas.bking.com
BK_URL = os.getenv("BKPAAS_URL", None)

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
