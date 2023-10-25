# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - 审计中心 (BlueKing - Audit Center) available.
Copyright (C) 2023 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at https://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import abc

from bk_resource import BkApiResource
from django.utils.translation import gettext_lazy

from api.domains import BK_VISION_API_URL


class BKVision(BkApiResource, abc.ABC):
    module_name = "bk_sops"
    base_url = BK_VISION_API_URL
    platform_authorization = True


class QueryMeta(BKVision):
    name = gettext_lazy("查询视图配置")
    method = "GET"
    action = "/api/v1/meta/query/"


class GetPanel(BKVision):
    name = gettext_lazy("查询视图配置")
    method = "GET"
    action = "/api/v1/panel/"


class QueryData(BKVision):
    name = gettext_lazy("获取面板视图数据")
    method = "POST"
    action = "/api/v1/datasource/query/"


class QueryVariableData(BKVision):
    name = gettext_lazy("获取面板变量数据")
    method = "POST"
    action = "/api/v1/variable/query/"
