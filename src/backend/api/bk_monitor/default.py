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
import copy

from bk_resource import APIResource
from bk_resource.exceptions import APIRequestError
from bk_resource.utils.cache import CacheTypeItem
from django.conf import settings
from django.utils.translation import gettext_lazy

from api.bk_monitor.constants import BKMONITOR_METRIC_MAX_BATCH_SIZE
from api.bk_monitor.serializers import ReportEventSerializer, ReportMetricSerializer
from api.constants import APIProvider
from api.domains import BK_MONITOR_API_URL, BK_MONITOR_METRIC_PROXY_URL
from api.utils import get_endpoint
from core.bk_api_base import AuditBkApiResource


class BKMonitorBaseResource(AuditBkApiResource, abc.ABC):
    module_name = "bk-monitor"
    platform_authorization = True

    @property
    def base_url(self):
        """多租户模式切换到监控 APIGW"""
        if self.use_multi_tenant_mode():
            return get_endpoint(settings.BK_MONITOR_APIGW_NAME, APIProvider.APIGW, stage="prod")
        return BK_MONITOR_API_URL


class SearchAlarmStrategy(BKMonitorBaseResource):
    # 该 api 没有被项目调用
    name = gettext_lazy("查询告警策略")
    method = "POST"

    @property
    def action(self):
        if self.use_multi_tenant_mode():
            return "/app/alarm_strategy/search/"
        return "/search_alarm_strategy_v3/"


class SaveAlarmStrategy(BKMonitorBaseResource):
    name = gettext_lazy("保存告警策略")
    method = "POST"
    TIMEOUT = 30

    @property
    def action(self):
        if self.use_multi_tenant_mode():
            return "/app/alarm_strategy/save/"
        return "/save_alarm_strategy_v3/"


class DeleteAlarmStrategy(BKMonitorBaseResource):
    name = gettext_lazy("删除告警策略")
    method = "POST"

    @property
    def action(self):
        if self.use_multi_tenant_mode():
            return "/app/alarm_strategy/delete/"
        return "/delete_alarm_strategy_v3/"


class SwitchAlarmStrategy(BKMonitorBaseResource):
    name = gettext_lazy("启停告警策略")
    method = "POST"

    @property
    def action(self):
        if self.use_multi_tenant_mode():
            return "/app/alarm_strategy/switch/"
        return "/switch_alarm_strategy/"


class UnifyQuery(BKMonitorBaseResource):
    # 该 api 没有被项目调用
    name = gettext_lazy("聚合查询")
    method = "POST"

    @property
    def action(self):
        if self.use_multi_tenant_mode():
            return "/app/data_query/time_series_unify_query/"
        return "/time_series/unify_query/"


class GetVariableValue(BKMonitorBaseResource):
    # 该 api 没有被项目调用
    name = gettext_lazy("获取变量值")
    method = "POST"

    @property
    def action(self):
        if self.use_multi_tenant_mode():
            return "/app/data_query/get_variable_value/"
        return "/get_variable_value/"


class SearchNoticeGroup(BKMonitorBaseResource):
    name = gettext_lazy("搜索通知组")
    method = "POST"

    @property
    def action(self):
        if self.use_multi_tenant_mode():
            return "/app/user_group/search/"
        return "/search_notice_group/"


class SaveNoticeGroup(BKMonitorBaseResource):
    # 该 api 没有被项目调用
    name = gettext_lazy("保存通知组")
    method = "POST"

    @property
    def action(self):
        if self.use_multi_tenant_mode():
            return "/app/user_group/save/"
        return "/save_notice_group/"


class DeleteNoticeGroup(BKMonitorBaseResource):
    # 该 api 没有被项目调用
    name = gettext_lazy("删除通知组")
    method = "POST"

    @property
    def action(self):
        if self.use_multi_tenant_mode():
            return "/app/user_group/delete/"
        return "/delete_notice_group/"


class SearchAlert(BKMonitorBaseResource):
    name = gettext_lazy("查询告警")
    method = "POST"
    TIMEOUT = 60 * 5

    @property
    def action(self):
        if self.use_multi_tenant_mode():
            return "/app/alert/search/"
        return "/search_alert/"


class GetClusterInfo(BKMonitorBaseResource):
    name = gettext_lazy("获取集群信息")
    method = "GET"
    cache_type = CacheTypeItem(key="MetadataClusterInfo", timeout=60 * 60, user_related=False)

    @property
    def action(self):
        if self.use_multi_tenant_mode():
            return "/app/metadata/get_cluster_info/"
        return "/metadata_get_cluster_info/"


class ReportMetric(APIResource):
    name = gettext_lazy("上报到监控自定义指标")
    module_name = "monitor"
    method = "POST"
    base_url = BK_MONITOR_METRIC_PROXY_URL
    action = "/v2/push/"
    RequestSerializer = ReportMetricSerializer

    def validate_request_data(self, request_data: dict) -> dict:
        # 判断是否需要上报
        if not self.base_url:
            raise APIRequestError(module_name=self.module_name, url=self.action, result="base_url is not set")
        return super().validate_request_data(request_data)

    def perform_request(self, validated_request_data):
        # 针对数据量做兼容
        if len(validated_request_data["data"]) <= BKMONITOR_METRIC_MAX_BATCH_SIZE:
            return {"results": [super().perform_request(validated_request_data)]}
        # 超过时分片
        results = {"results": []}
        datas = copy.deepcopy(validated_request_data["data"])
        for i in range(0, len(datas), BKMONITOR_METRIC_MAX_BATCH_SIZE):
            # fmt: off
            validated_request_data["data"] = datas[i: i + BKMONITOR_METRIC_MAX_BATCH_SIZE]
            results["results"].append(super().perform_request(validated_request_data))
        return results


class ReportEvent(ReportMetric):
    name = gettext_lazy("上报到监控自定义事件")
    RequestSerializer = ReportEventSerializer
