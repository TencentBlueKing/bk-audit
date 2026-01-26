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
from binascii import Error

from bk_resource.exceptions import APIRequestError
from bk_resource.utils.common_utils import ignored
from django.conf import settings
from django.utils.translation import gettext_lazy
from rest_framework import serializers

from api.base import CommonBkApiResource
from api.bk_log.constants import (
    BK_AUDIT_TAGS,
    DEFAULT_VISIBLE_CONFIG,
    PARTITION_ERROR_CODE,
)
from api.bk_log.serializers import (
    AgentStatusSerializer,
    BatchSubscriptionStatusRequestSerializer,
    BatchSubscriptionStatusResponseSerializer,
    BizsTopoRequestSerializer,
    BizsTopoResponseManySerializer,
    CollectorRequestSerializer,
    GetApplyDataResponseSerializer,
    GetCollectorTailLogResponseSerializer,
    GetEtlPreviewRequestSerializer,
    GetEtlPreviewResponseSerializer,
    GetHostInstanceByIPRequestSerializer,
    GetHostInstanceByIPResponseSerializer,
    GetHostInstanceByNodeRequestSerializer,
    GetNodesByTemplateRequestSerializer,
    GetSubscriptionStatusRequestSerializer,
    GetSubscriptionStatusResponseSerializer,
    GetSubscriptTaskDetailRequestSerializer,
    GetSubscriptTaskStatusRequestSerializer,
    GetSubscriptTaskStatusResponseSerializer,
    GetTemplateTopoRequestSerializer,
    GetTemplateTopoResponseSerializer,
    ListAgentStatusRequestSerializer,
    ListBcsClustersRequestSerializer,
    ListBcsClustersResponseSerializer,
    NodeAttrsResponseSerializer,
    PreCheckCollectorEnNameRequestSerialzier,
    PreCheckCollectorEnNameResponseSerialzier,
    RetrySubscriptTaskRequestSerializer,
    StorageBatchConnectivityDetectRequestSerializer,
    StorageBatchConnectivityDetectResponseSerializer,
    StorageDetectRequestSerializer,
    ValidateContainerConfigYamlRequestSerializer,
    ValidateContainerConfigYamlResponseSerializer,
)
from api.domains import BK_LOG_API_URL
from apps.bk_crypto.crypto import asymmetric_cipher
from core.utils.data import distinct


class BKLogBaseResource(CommonBkApiResource, abc.ABC):
    base_url = BK_LOG_API_URL
    module_name = "bk-log"


class GetOperators(BKLogBaseResource):
    action = "/search_index_set/operators/"
    method = "GET"


class StorageBaseResource(BKLogBaseResource):
    tags = ["Storage"]
    platform_authorization = True

    def build_request_data(self, validated_request_data):
        data = super().build_request_data(validated_request_data)
        data.update({"bk_biz_id": settings.DEFAULT_BK_BIZ_ID})
        return data

    def build_storage_params(self, validated_request_data):
        validated_request_data.update(
            {
                "create_bkbase_cluster": True,
                "cluster_namespace": validated_request_data["namespace"],
                "visible_config": DEFAULT_VISIBLE_CONFIG,
                "enable_archive": True,
                "enable_assessment": False,
                "bkbase_tags": BK_AUDIT_TAGS,
            }
        )
        return validated_request_data


class CreateStorage(StorageBaseResource):
    name = gettext_lazy("创建集群")
    action = "/databus_storage/"
    method = "POST"

    def build_request_data(self, validated_request_data):
        data = super().build_request_data(validated_request_data)
        return self.build_storage_params(data)


class UpdateStorage(StorageBaseResource):
    name = gettext_lazy("更新集群")
    serializer_class = serializers.IntegerField
    action = "/databus_storage/{cluster_id}/"
    method = "PUT"
    url_keys = ["cluster_id"]

    def build_request_data(self, validated_request_data):
        data = super().build_request_data(validated_request_data)
        return self.build_storage_params(data)


class DeleteStorage(StorageBaseResource):
    name = gettext_lazy("删除集群")
    action = "/databus_storage/{cluster_id}/"
    method = "DELETE"
    url_keys = ["cluster_id"]


class GetStorages(StorageBaseResource):
    name = gettext_lazy("存储集群列表")
    action = "/databus_storage/?bk_biz_id={bk_biz_id}"
    method = "GET"
    url_keys = ["bk_biz_id"]


class ConnectivityDetect(StorageBaseResource):
    name = gettext_lazy("连通性测试")
    action = "/databus_storage/connectivity_detect/?bk_biz_id={bk_biz_id}"
    method = "POST"
    RequestSerializer = StorageDetectRequestSerializer
    serializer_class = serializers.BooleanField
    url_keys = ["bk_biz_id"]

    def validate_request_data(self, request_data):
        data = super().validate_request_data(request_data)
        if data.get("password"):
            with ignored(Error):
                data["password"] = asymmetric_cipher.decrypt(data["password"])
        return data


class BatchConnectivityDetect(StorageBaseResource):
    name = gettext_lazy("批量连通性测试")
    action = "/databus_storage/batch_connectivity_detect/?bk_biz_id={bk_biz_id}"
    method = "POST"
    RequestSerializer = StorageBatchConnectivityDetectRequestSerializer
    serializer_class = StorageBatchConnectivityDetectResponseSerializer
    url_keys = ["bk_biz_id"]

    def perform_request(self, validated_request_data):
        validated_request_data["cluster_list"] = [
            cluster_id for cluster_id in validated_request_data["cluster_ids"].split(",") if cluster_id
        ]
        data = super().perform_request(validated_request_data)
        if validated_request_data.get("origin_resp", False):
            return data
        return {cluster_id: status_map.get("status", False) for cluster_id, status_map in data.items()}


class NodeAttrs(StorageBaseResource):
    name = gettext_lazy("集群节点属性")
    action = "/databus_storage/node_attrs/"
    method = "POST"
    RequestSerializer = StorageDetectRequestSerializer
    ResponseSerializer = NodeAttrsResponseSerializer
    many_response_data = True


class BizBaseResource(BKLogBaseResource, abc.ABC):
    tags = ["Biz"]


class BizsList(BizBaseResource):
    name = gettext_lazy("业务列表")
    action = "/meta/projects/mine/"
    method = "GET"


class BizTopos(BizBaseResource):
    name = gettext_lazy("业务拓扑")
    action = "bizs/{bk_biz_id}/topo/"
    method = "GET"
    url_keys = ["bk_biz_id"]
    RequestSerializer = BizsTopoRequestSerializer
    ResponseSerializer = BizsTopoResponseManySerializer
    many_response_data = True


class GetHostInstanceByNode(BizBaseResource):
    name = gettext_lazy("实例列表(Node)")
    action = "/bizs/{bk_biz_id}/host_instance_by_node/"
    method = "POST"
    url_keys = ["bk_biz_id"]
    RequestSerializer = GetHostInstanceByNodeRequestSerializer
    serializer_class = AgentStatusSerializer
    many_response_data = True


class GetHostInstanceByIP(BizBaseResource):
    name = gettext_lazy("实例列表(IP)")
    action = "/bizs/{bk_biz_id}/host_instance_by_ip/"
    method = "POST"
    url_keys = ["bk_biz_id"]
    RequestSerializer = GetHostInstanceByIPRequestSerializer
    serializer_class = GetHostInstanceByIPResponseSerializer
    many_response_data = True

    def validate_request_data(self, request_data):
        data = super().validate_request_data(request_data)
        data["ip_list"] = distinct(data["ip_list"])
        return data


class ListAgentStatus(BizBaseResource):
    name = gettext_lazy("获取Agent状态")
    action = "/bizs/{bk_biz_id}/list_agent_status/"
    method = "POST"
    url_keys = ["bk_biz_id"]
    RequestSerializer = ListAgentStatusRequestSerializer
    serializer_class = AgentStatusSerializer
    many_response_data = True

    def validate_request_data(self, request_data):
        data = super().validate_request_data(request_data)
        data["node_list"] = [
            {**instance, "bk_biz_id": instance.get("bk_biz_id") or data["bk_biz_id"]} for instance in data["node_list"]
        ]
        return data


class GetTemplateTopos(BizBaseResource):
    name = gettext_lazy("服务模板拓扑")
    action = "/bizs/{bk_biz_id}/template_topo/"
    method = "GET"
    url_keys = ["bk_biz_id"]
    RequestSerializer = GetTemplateTopoRequestSerializer
    serializer_class = GetTemplateTopoResponseSerializer


class GetNodesByTemplate(BizBaseResource):
    name = gettext_lazy("节点列表(Template)")
    action = "/bizs/{bk_biz_id}/get_nodes_by_template/"
    method = "GET"
    url_keys = ["bk_biz_id"]
    RequestSerializer = GetNodesByTemplateRequestSerializer
    serializer_class = AgentStatusSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        if not validated_request_data["bk_inst_ids"]:
            return list()
        return super().perform_request(validated_request_data)


class CollectorsBaseResource(BKLogBaseResource, abc.ABC):
    tags = ["Collector"]


class CreateCollector(CollectorsBaseResource):
    name = gettext_lazy("创建采集项")
    action = "/databus_collector_plugins/{collector_plugin_id}/instances/"
    method = "POST"
    url_keys = ["collector_plugin_id"]


class UpdateCollector(CollectorsBaseResource):
    name = gettext_lazy("更新采集")
    action = "/databus_collector_plugins/update_instance/"
    method = "PUT"


class ListBcsClusters(BizBaseResource):
    name = gettext_lazy("获取集群列表")
    action = "/databus_collectors/list_bcs_clusters/?bk_biz_id={bk_biz_id}"
    method = "GET"
    url_keys = ["bk_biz_id"]
    RequestSerializer = ListBcsClustersRequestSerializer
    serializer_class = ListBcsClustersResponseSerializer
    many_response_data = True


class ValidateContainerConfigYaml(CollectorsBaseResource):
    name = gettext_lazy("校验Yaml合法")
    action = "/databus_collectors/validate_container_config_yaml/"
    method = "POST"
    RequestSerializer = ValidateContainerConfigYamlRequestSerializer
    serializer_class = ValidateContainerConfigYamlResponseSerializer


class CreateCollectorNormal(CollectorsBaseResource):
    name = gettext_lazy("创建采集")
    action = "/databus_collectors/"
    method = "POST"


class UpdateCollectorNormal(CollectorsBaseResource):
    name = gettext_lazy("更新采集")
    action = "/databus_collectors/{collector_config_id}/"
    method = "PUT"
    url_keys = ["collector_config_id"]


class GetCollector(CollectorsBaseResource):
    name = gettext_lazy("获取采集项")
    action = "/databus_collectors/{collector_config_id}/"
    method = "GET"
    url_keys = ["collector_config_id"]


class CreateCollectorEtl(CollectorsBaseResource):
    name = gettext_lazy("创建采集项清洗规则")
    action = "/databus_collector_plugins/instance_etl/"
    method = "POST"


class GetSubscriptTaskStatus(CollectorsBaseResource):
    name = gettext_lazy("获取任务下发状态(Task)")
    action = "/databus_collectors/{collector_config_id}/task_status/?task_id_list={task_id_list}"
    method = "GET"
    url_keys = ["task_id_list", "collector_config_id"]
    RequestSerializer = GetSubscriptTaskStatusRequestSerializer
    serializer_class = GetSubscriptTaskStatusResponseSerializer


class GetSubscriptTaskDetail(CollectorsBaseResource):
    name = gettext_lazy("获取任务下发详情")
    action = "/databus_collectors/{collector_config_id}/task_detail/?instance_id={instance_id}"
    method = "GET"
    url_keys = ["collector_config_id", "instance_id"]
    RequestSerializer = GetSubscriptTaskDetailRequestSerializer
    serializer_class = serializers.CharField

    def perform_request(self, validated_request_data):
        data = super().perform_request(validated_request_data)
        return data.get("log_detail", "")


class RetrySubscriptTask(CollectorsBaseResource):
    name = gettext_lazy("重试订阅任务")
    action = "/databus_collectors/{collector_config_id}/retry/"
    method = "POST"
    url_keys = ["collector_config_id"]
    RequestSerializer = RetrySubscriptTaskRequestSerializer
    serializer_class = serializers.ListField


class GetSubscriptionStatus(CollectorsBaseResource):
    name = gettext_lazy("获取任务下发状态(Collector)")
    action = "/databus_collectors/{collector_config_id}/subscription_status/"
    method = "GET"
    url_keys = ["collector_config_id"]
    RequestSerializer = GetSubscriptionStatusRequestSerializer
    ResponseSerializer = GetSubscriptionStatusResponseSerializer


class BatchSubscriptionStatus(CollectorsBaseResource):
    name = gettext_lazy("批量获取任务下发状态(Collector)")
    action = "/databus_collectors/batch_subscription_status/"
    method = "GET"
    RequestSerializer = BatchSubscriptionStatusRequestSerializer
    serializer_class = BatchSubscriptionStatusResponseSerializer
    many_response_data = True


class GetCollectorTailLog(CollectorsBaseResource):
    name = gettext_lazy("获取最新上报的数据")
    action = "/databus_collectors/{collector_config_id}/tail/"
    method = "GET"
    url_keys = ["collector_config_id"]
    RequestSerializer = CollectorRequestSerializer
    ResponseSerializer = GetCollectorTailLogResponseSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        try:
            return super().perform_request(validated_request_data)
        except APIRequestError as err:
            code = getattr(err, "data", {}).get("code")
            if str(code) == PARTITION_ERROR_CODE:
                return []
            raise err


class GetEtlPreview(CollectorsBaseResource):
    name = gettext_lazy("获取清洗预览")
    action = "/databus_collectors/{collector_config_id}/etl_preview/"
    method = "POST"
    url_keys = ["collector_config_id"]
    RequestSerializer = GetEtlPreviewRequestSerializer
    serializer_class = GetEtlPreviewResponseSerializer


class StopSubscription(CollectorsBaseResource):
    name = gettext_lazy("停止采集")
    action = "/databus_collectors/{collector_config_id}/stop/"
    method = "POST"
    url_keys = ["collector_config_id"]


class GetGlobals(BKLogBaseResource):
    name = gettext_lazy("全局配置")
    tags = ["Meta"]
    action = "/meta/globals/"
    method = "GET"


class CreateCollectorPlugin(BKLogBaseResource):
    name = gettext_lazy("创建采集插件")
    action = "/databus_collector_plugins/"
    method = "POST"
    platform_authorization = True


class UpdateCollectorPlugin(BKLogBaseResource):
    name = gettext_lazy("更新采集插件")
    action = "/databus_collector_plugins/{collector_plugin_id}/"
    method = "PUT"
    url_keys = ["collector_plugin_id"]
    platform_authorization = True


class PreCheckCollectorEnName(CollectorsBaseResource):
    name = gettext_lazy("预检查采集英文名")
    action = "/databus_collectors/pre_check/"
    method = "GET"
    RequestSerializer = PreCheckCollectorEnNameRequestSerialzier
    ResponseSerializer = PreCheckCollectorEnNameResponseSerialzier
    platform_authorization = True


class EsQuerySearchResource(BKLogBaseResource):
    name = gettext_lazy("搜索日志")
    tags = ["EsQuery"]
    action = "/esquery_search/"
    method = "POST"
    platform_authorization = True


class EsQueryScroll(BKLogBaseResource):
    name = gettext_lazy("滚动查询日志")
    tags = ["EsQuery"]
    action = "/esquery_scroll/"
    method = "POST"
    platform_authorization = True


class IndexSetReplace(BKLogBaseResource):
    name = gettext_lazy("重建索引集")
    tags = ["EsQuery"]
    action = "/index_set/replace/"
    method = "POST"
    platform_authorization = True


class IndexSetOperators(BKLogBaseResource):
    name = gettext_lazy("获取操作符")
    tags = ["EsQuery"]
    action = "/search_index_set/operators/"
    method = "GET"


class CheckAllowed(BKLogBaseResource):
    name = gettext_lazy("权限检测")
    tags = ["IAM"]
    action = "/iam/meta/check_allowed/"
    method = "POST"

    def perform_request(self, validated_request_data):
        resources = super(CheckAllowed, self).perform_request(validated_request_data)
        result = {}
        for action_allowed in resources:
            action_id = "{}_bk_log".format(action_allowed["action_id"])
            result[action_id] = action_allowed["is_allowed"]
        return result


class GetApplyData(BKLogBaseResource):
    name = gettext_lazy("获取鉴权信息")
    tags = ["IAM"]
    action = "/iam/meta/get_apply_data/"
    method = "POST"

    ResponseSerializer = GetApplyDataResponseSerializer


class GetSpacesMine(BKLogBaseResource):
    name = gettext_lazy("获取空间列表")
    method = "GET"
    action = "/meta/spaces/mine/"


class CreateCustomCollector(CollectorsBaseResource):
    name = gettext_lazy("创建自定义采集")
    action = "/databus_custom_create/"
    method = "POST"


class CreateApiPush(CreateCustomCollector):
    name = gettext_lazy("创建自定义日志上报")
    platform_authorization = True


class GetApiPushTailLog(GetCollectorTailLog):
    name = gettext_lazy("获取自定义日志上报最近日志")
    platform_authorization = True


class GetReportToken(CollectorsBaseResource):
    name = gettext_lazy("获取上报Token")
    action = "/databus_collectors/{collector_config_id}/report_token/"
    url_keys = ["collector_config_id"]
    method = "GET"
    platform_authorization = True


class GetReportHost(CollectorsBaseResource):
    name = gettext_lazy("获取上报Host")
    action = "/databus_collectors/report_host/"
    method = "GET"
    platform_authorization = True
