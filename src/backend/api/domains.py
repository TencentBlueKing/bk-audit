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

from django.conf import settings

from api.constants import APIProvider
from api.utils import get_endpoint
from core.utils.distutils import strtobool

APIGW_ENABLED = strtobool(os.getenv("BKAPP_USE_APIGW", "False"))

# 权限中心
BK_IAM_API_URL = get_endpoint("bk-iam", stag="stage")

# 日志平台
BK_LOG_API_URL = get_endpoint("log-search") if APIGW_ENABLED else get_endpoint("bk_log", APIProvider.ESB)

# PaaSV3
BK_PAAS_API_URL = get_endpoint(os.getenv("BKAPP_BK_PAAS_APIGW_NAME", "bkpaas3"), stage="prod")

# User Manage
USER_MANAGE_URL = get_endpoint("usermanage", APIProvider.ESB)

# BkBase
BK_BASE_API_URL = os.getenv("BK_BASE_API_URL")
if not BK_BASE_API_URL:
    BK_BASE_API_URL = get_endpoint(os.getenv("BKAPP_BK_BASE_APIGW_NAME", "bk-base"), stag="test")

# BkMonitor
BK_MONITOR_API_URL = (
    get_endpoint("bkmonitorv3", stag="stage") if APIGW_ENABLED else get_endpoint("monitor_v3", provider=APIProvider.ESB)
)
BK_MONITOR_METRIC_PROXY_URL = settings.BK_MONITOR_METRIC_PROXY_URL

# CMSI
BK_CMSI_API_URL = get_endpoint("cmsi", APIProvider.ESB, stage="prod")

# Watermark
WATERMARK_API_URL = get_endpoint("devsecops", APIProvider.APIGW)

# BK SOps
BK_SOPS_API_URL = get_endpoint("bk-sops", APIProvider.APIGW, stag="stage")

# BK ITSM
BK_ITSM_API_URL = get_endpoint("bk-itsm", APIProvider.APIGW) if APIGW_ENABLED else get_endpoint("itsm", APIProvider.ESB)

# BK Vision
BK_VISION_API_URL = os.getenv("BKAPP_BK_VISION_API_URL")
if not BK_VISION_API_URL:
    BK_VISION_API_URL = get_endpoint("bk-vision", APIProvider.APIGW, stag="stag-new")

# BK IAM V4
BK_IAM_V4_API_URL = get_endpoint("bkiam", APIProvider.APIGW, stag="dev")
