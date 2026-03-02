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
    module_name = "bk_vision"
    base_url = BK_VISION_API_URL
    platform_authorization = True
    tags = ["BKVision"]


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


class QueryDataset(BKVision):
    name = gettext_lazy("查询数据集")
    method = "POST"
    action = "/api/v1/dataset/query/"


class QueryFieldData(BKVision):
    name = gettext_lazy("查询字段值")
    method = "POST"
    action = "/api/v1/field/{uid}/preview_data/"
    url_keys = ["uid"]


class CreateReportStrategy(BKVision):
    name = gettext_lazy("创建订阅推送")
    method = "POST"
    action = "/api/v1/report/create_report_strategy/"


class UpdateReportStrategy(BKVision):
    name = gettext_lazy("更新订阅推送")
    method = "PUT"
    action = "/api/v1/report/update_report_strategy/{uid}/"
    url_keys = ["uid"]


class DeleteReportStrategy(BKVision):
    name = gettext_lazy("删除订阅推送")
    method = "DELETE"
    action = "/api/v1/report/delete_report_strategy/{uid}/"
    url_keys = ["uid"]


class GetShareList(BKVision):
    platform_authorization = False
    name = gettext_lazy("获取有权限的图表列表")
    method = "GET"
    action = "/api/v1/share/get_share_list/"


class CheckShareAuth(BKVision):
    name = gettext_lazy("检查分享权限")
    method = "GET"
    action = "/api/v1/share/check_share_auth/"


class QueryTestVariable(BKVision):
    name = gettext_lazy("测试变量数据")
    method = "POST"
    action = "/api/v1/variable/test/"
