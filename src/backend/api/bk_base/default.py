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
import traceback

from bk_resource.settings import bk_resource_settings
from bk_resource.utils.cache import CacheTypeItem
from blueapps.utils.logger import logger
from django.conf import settings
from django.utils.translation import gettext_lazy

from api.base import CommonBkApiResource
from api.bk_base.constants import UNSUPPORTED_CODE
from api.bk_base.serializers import (
    DataflowBatchStatusListReqSerializer,
    QuerySyncRequestSerializer,
    UserAuthBatchCheckReqSerializer,
    UserAuthCheckReqSerializer,
    UserAuthCheckRespSerializer,
)
from api.domains import BK_BASE_API_URL


class BkBaseResource(CommonBkApiResource, abc.ABC):
    base_url = BK_BASE_API_URL
    module_name = "bkbase"
    platform_authorization = True

    def build_request_data(self, validated_request_data: dict) -> dict:
        data = super().build_request_data(validated_request_data)
        data["bk_username"] = bk_resource_settings.PLATFORM_AUTH_ACCESS_USERNAME
        data["bk_app_code"] = settings.APP_CODE
        return data


class DatabusStoragesPost(BkBaseResource):
    name = gettext_lazy("创建入库")
    action = "/v3/databus/data_storages/"
    method = "POST"


class DatabusStoragesPut(BkBaseResource):
    name = gettext_lazy("更新入库")
    action = "/v3/databus/data_storages/{result_table_id}/"
    method = "PUT"
    url_keys = ["result_table_id"]


class DatabusStoragesDelete(BkBaseResource):
    name = gettext_lazy("删除入库")
    action = "/v3/databus/data_storages/{result_table_id}/"
    method = "DELETE"
    url_keys = ["result_table_id"]


class DatabusCleansPost(BkBaseResource):
    name = gettext_lazy("创建清洗")
    action = "/v3/databus/cleans/"
    method = "POST"


class DatabusCleansPut(BkBaseResource):
    name = gettext_lazy("更新清洗")
    action = "/v3/databus/cleans/{processing_id}/"
    method = "PUT"
    url_keys = ["processing_id"]


class DatabusCleansDelete(BkBaseResource):
    name = gettext_lazy("删除清洗")
    action = "/v3/databus/cleans/{processing_id}/"
    method = "DELETE"
    url_keys = ["processing_id"]


class DatabusTasksPost(BkBaseResource):
    name = gettext_lazy("启动清洗任务")
    action = "/v3/databus/tasks/"
    method = "POST"


class DatabusTasksDelete(BkBaseResource):
    name = gettext_lazy("停止清洗任务")
    action = "/v3/databus/tasks/{processing_id}/"
    method = "DELETE"
    url_keys = ["processing_id"]


class CreateResourceSet(BkBaseResource):
    name = gettext_lazy("创建资源")
    action = "/v3/resourcecenter/resource_sets/"
    method = "POST"


class UpdateResourceSet(BkBaseResource):
    name = gettext_lazy("更新资源")
    action = "/v3/resourcecenter/resource_sets/{resource_set_id}/"
    method = "PATCH"
    url_keys = ["resource_set_id"]


class CleanPreview(BkBaseResource):
    name = gettext_lazy("清洗预览")
    action = "/v3/databus/cleans/verify/"
    method = "POST"


class GetDeployPlan(BkBaseResource):
    name = gettext_lazy("查询数据源")
    action = "/v3/access/deploy_plan/{bkbase_data_id}/"
    method = "GET"
    url_keys = ["bkbase_data_id"]


class CreateDeployPlan(BkBaseResource):
    name = gettext_lazy("创建数据源")
    action = "/v3/access/deploy_plan/"
    method = "POST"


class UpdateDeployPlan(BkBaseResource):
    name = gettext_lazy("更新数据源")
    action = "/v3/access/deploy_plan/{bkbase_data_id}/"
    method = "PUT"
    url_keys = ["bkbase_data_id"]


class StartCollector(BkBaseResource):
    name = gettext_lazy("启动数据接入")
    action = "/v3/access/collectorhub/{bkbase_data_id}/start/"
    method = "POST"
    url_keys = ["bkbase_data_id"]


class StopCollector(BkBaseResource):
    name = gettext_lazy("停止数据接入")
    action = "/v3/access/collectorhub/{bkbase_data_id}/stop/"
    method = "POST"
    url_keys = ["bkbase_data_id"]


class AiopsBaseResource(BkBaseResource, abc.ABC):
    def build_request_data(self, validated_request_data):
        data = super().build_request_data(validated_request_data)
        data["bkdata_authentication_method"] = "user"
        return data


class GetScenePlans(AiopsBaseResource):
    name = gettext_lazy("获取方案列表")
    action = "/v3/aiops/scene_service/plans/"
    method = "GET"


class GetPlanDetail(AiopsBaseResource):
    name = gettext_lazy("获取方案详情")
    action = "/v3/aiops/scene_service/plans/{plan_id}/"
    method = "GET"
    url_keys = ["plan_id"]


class CheckAiops(GetScenePlans):
    name = gettext_lazy("检测是否部署AIOPS")
    cache_type = CacheTypeItem("CheckAiopsAPI", 60 * 60, False)

    def parse_response(self, response):
        try:
            result = response.json()
            return UNSUPPORTED_CODE != str(result.get("code"))
        except Exception as err:
            logger.exception("[CheckAiopsFailed] Err => %s; Detail => %s", err, traceback.format_exc())
            return False


class AuthTickets(AiopsBaseResource):
    name = gettext_lazy("RT授权")
    action = "/v3/auth/tickets/"
    method = "POST"


class CreateFlow(AiopsBaseResource):
    name = gettext_lazy("创建Flow")
    action = "/v3/dataflow/flow/flows/"
    method = "POST"


class StartFlow(AiopsBaseResource):
    name = gettext_lazy("启动Flow")
    action = "/v3/dataflow/flow/flows/{flow_id}/start/"
    url_keys = ["flow_id"]
    method = "POST"


class RestartFlow(AiopsBaseResource):
    name = gettext_lazy("重启Flow")
    action = "/v3/dataflow/flow/flows/{flow_id}/restart/"
    url_keys = ["flow_id"]
    method = "POST"


class StopFlow(AiopsBaseResource):
    name = gettext_lazy("停止Flow")
    action = "/v3/dataflow/flow/flows/{flow_id}/stop/"
    url_keys = ["flow_id"]
    method = "POST"


class GetFlow(AiopsBaseResource):
    name = gettext_lazy("获取Flow")
    action = "/v3/dataflow/flow/flows/{flow_id}/"
    url_keys = ["flow_id"]
    method = "GET"


class GetFlowGraph(AiopsBaseResource):
    name = gettext_lazy("获取Flow图")
    action = "/v3/dataflow/flow/flows/{flow_id}/graph/"
    url_keys = ["flow_id"]
    method = "GET"


class CreateFlowNode(AiopsBaseResource):
    name = gettext_lazy("创建Flow节点")
    action = "/v3/dataflow/flow/flows/{flow_id}/nodes/"
    url_keys = ["flow_id"]
    method = "POST"


class UpdateFlowNode(AiopsBaseResource):
    name = gettext_lazy("更新Flow节点")
    action = "/v3/dataflow/flow/flows/{flow_id}/nodes/{node_id}/"
    url_keys = ["flow_id", "node_id"]
    method = "PUT"


class DeleteFlowNode(AiopsBaseResource):
    name = gettext_lazy("删除Flow节点")
    action = "/v3/dataflow/flow/flows/{flow_id}/nodes/{node_id}/"
    url_keys = ["flow_id", "node_id"]
    method = "DELETE"


class GetRtFields(AiopsBaseResource):
    name = gettext_lazy("获取结果表字段")
    action = "/v3/meta/result_tables/{result_table_id}/fields/"
    url_keys = ["result_table_id"]
    method = "GET"


class GetFlowDeployData(AiopsBaseResource):
    name = gettext_lazy("获取Flow部署状态")
    action = "/v3/dataflow/flow/flows/{flow_id}/latest_deploy_data/"
    url_keys = ["flow_id"]
    method = "GET"


class GetRawdataList(BkBaseResource):
    name = gettext_lazy("获取源数据列表")
    action = "/v3/access/rawdata/"
    method = "GET"


class GetMyRawdataList(BkBaseResource):
    name = gettext_lazy("获取我有权限的源数据列表")
    action = "/v3/access/rawdata/mine/"
    method = "GET"
    platform_authorization = False


class GetRawdataDetail(BkBaseResource):
    name = gettext_lazy("获取源数据详情")
    action = "/v3/access/rawdata/{bk_data_id}/"
    url_keys = ["bk_data_id"]
    method = "GET"
    platform_authorization = False


class GetRawdataTail(BkBaseResource):
    name = gettext_lazy("获取源数据最近数据")
    action = "/v3/databus/rawdatas/{bk_data_id}/tail/"
    url_keys = ["bk_data_id"]
    method = "GET"


class GetResultTables(BkBaseResource):
    name = gettext_lazy("获取结果表列表")
    action = "/v3/meta/result_tables/"
    method = "GET"


class GetResultTable(BkBaseResource):
    name = gettext_lazy("获取结果表")
    method = "GET"
    action = "/v3/meta/result_tables/{result_table_id}/"
    url_keys = ["result_table_id"]


class GetRtStorages(BkBaseResource):
    name = gettext_lazy("获取结果表的存储信息")
    action = "/v3/meta/result_tables/{result_table_id}/storages/"
    url_keys = ["result_table_id"]
    method = "GET"


class GetProjectData(BkBaseResource):
    name = gettext_lazy("列举项目相关数据")
    action = "/v3/auth/projects/{project_id}/data/"
    method = "GET"
    url_keys = ["project_id"]


class GetAlertConfigs(BkBaseResource):
    name = gettext_lazy("获取告警策略配置详情")
    action = "/v3/datamanage/dmonitor/alert_configs/{object_type}/{object_id}/"
    method = "GET"
    url_keys = ["object_type", "object_id"]


class EditAlertConfigs(BkBaseResource):
    name = gettext_lazy("修改部分告警策略配置配置")
    action = "/v3/datamanage/dmonitor/alert_configs/{alert_config_id}/"
    method = "PATCH"
    url_keys = ["alert_config_id"]


class GetRoleUsersList(BkBaseResource):
    name = gettext_lazy("列举角色用户")
    action = "/v3/auth/roles/{role_id}/users/"
    method = "GET"
    url_keys = ["role_id"]


class GetSensitivityInfoViaDataset(BkBaseResource):
    name = gettext_lazy("获取敏感度信息")
    action = "/v3/auth/sensitivity/retrieve_dataset/"
    method = "GET"


class QuerySyncResource(BkBaseResource):
    """
    查询数据
    """

    action = "/v3/queryengine/query_sync/"
    method = "POST"
    TIMEOUT = 60 * 5
    RequestSerializer = QuerySyncRequestSerializer


class DataflowBatchStatusList(BkBaseResource):
    """
    查询离线任务状态列表
    """

    action = "/v3/dataflow/batch/data_makeup/status_list/"
    method = "GET"
    RequestSerializer = DataflowBatchStatusListReqSerializer


class UserAuthCheck(BkBaseResource):
    """
    校验用户与对象权限
    """

    action = "/v3/auth/users/{user_id}/check/"
    method = "POST"
    url_keys = ["user_id"]
    RequestSerializer = UserAuthCheckReqSerializer


class UserAuthBatchCheck(BkBaseResource):
    """
    批量校验用户与对象权限
    """

    action = "/v3/auth/users/batch_check/"
    method = "POST"
    many_response_data = True
    RequestSerializer = UserAuthBatchCheckReqSerializer
    ResponseSerializer = UserAuthCheckRespSerializer
