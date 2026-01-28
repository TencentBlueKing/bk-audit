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

import abc

import requests
from client_throttler import Throttler, ThrottlerConfig
from django.conf import settings
from django.utils.translation import gettext_lazy

from api.base import CommonBkApiResource
from api.bk_sops.constants import SOpsDatetime
from api.domains import BK_SOPS_API_URL


class BKSOps(CommonBkApiResource, abc.ABC):
    module_name = "bk_sops"
    base_url = BK_SOPS_API_URL
    platform_authorization = True
    rate_limit = settings.SOPS_API_RATE_LIMIT

    def perform_request(self, validated_request_data):
        return Throttler(
            config=ThrottlerConfig(
                func=super().perform_request,
                key=f"{self.__module__}.{self.__class__.__name__}",
                rate=self.rate_limit,
            )
        )(validated_request_data)


class GetTemplateList(BKSOps):
    name = gettext_lazy("查询业务下的模板列表")
    method = "GET"
    action = "/get_template_list/{bk_biz_id}/"
    url_keys = ["bk_biz_id"]


class GetTemplateInfo(BKSOps):
    name = gettext_lazy("查询业务下单个模板详情")
    method = "GET"
    action = "/get_template_info/{template_id}/{bk_biz_id}/"
    url_keys = ["template_id", "bk_biz_id"]


class CreateTask(BKSOps):
    name = gettext_lazy("通过业务流程模板创建任务")
    method = "POST"
    action = "/create_task/{template_id}/{bk_biz_id}/"
    url_keys = ["template_id", "bk_biz_id"]
    rate_limit = settings.SOPS_OPERATE_API_RATE_LIMIT


class StartTask(BKSOps):
    name = gettext_lazy("开始执行任务")
    method = "POST"
    action = "/start_task/{task_id}/{bk_biz_id}/"
    url_keys = ["task_id", "bk_biz_id"]
    rate_limit = settings.SOPS_OPERATE_API_RATE_LIMIT


class GetTaskStatus(BKSOps):
    name = gettext_lazy("查询任务执行状态")
    method = "GET"
    action = "/get_task_status/{task_id}/{bk_biz_id}/"
    url_keys = ["task_id", "bk_biz_id"]

    def parse_response(self, response: requests.Response):
        data = super().parse_response(response)
        data["start_time"] = SOpsDatetime(data.get("start_time"))
        data["finish_time"] = SOpsDatetime(data.get("finish_time"))
        return data


class OperateTask(BKSOps):
    name = gettext_lazy("操作任务")
    method = "POST"
    action = "/operate_task/{task_id}/{bk_biz_id}/"
    url_keys = ["task_id", "bk_biz_id"]
    rate_limit = settings.SOPS_OPERATE_API_RATE_LIMIT


class GetNodeData(BKSOps):
    name = gettext_lazy("获取节点数据")
    method = "GET"
    action = "/get_task_node_data/{bk_biz_id}/{task_id}/"
    url_keys = ["task_id", "bk_biz_id"]


class OperateNode(BKSOps):
    name = gettext_lazy("操作节点")
    method = "POST"
    action = "/operate_node/{bk_biz_id}/{task_id}/"
    url_keys = ["task_id", "bk_biz_id"]
    rate_limit = settings.SOPS_OPERATE_API_RATE_LIMIT
