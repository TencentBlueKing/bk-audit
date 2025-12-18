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

from enum import Enum

from django.conf import settings

ESB_PREFIX = "/api/c/compapi/v2/"
ESB_URL_FORMAT = "{}{}{{}}".format(settings.BK_COMPONENT_API_URL, ESB_PREFIX)

APIGW_URL_FORMAT = "{}/{{stage}}".format(settings.BK_API_URL_TMPL)


class APIProvider(Enum):
    APIGW = "apigw"
    ESB = "esb"
