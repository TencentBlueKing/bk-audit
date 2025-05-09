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

from bk_resource import api, resource
from bkstorages.backends.bkrepo import BKRepoFile, BKRepoStorage
from blueapps.utils.logger import logger
from django.conf import settings
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy

from api.bk_base.constants import StorageType
from apps.meta.constants import ConfigLevelChoices
from apps.meta.models import GlobalMetaConfig
from apps.meta.utils.tools import is_system_admin
from apps.permission.handlers.actions import ActionEnum
from services.web.databus.constants import COLLECTOR_PLUGIN_ID
from services.web.databus.models import CollectorPlugin
from services.web.query.constants import COLLECT_SEARCH_CONFIG, TaskEnum
from services.web.query.exceptions import (
    LogExportMaxCountError,
    LogExportTaskStatusError,
)
from services.web.query.export.data_fetcher import DataFetcher
from services.web.query.models import ExportFieldLog, LogExportTask
from services.web.query.serializers import (
    CollectorSearchAllReqSerializer,
    CollectorSearchConfigRespSerializer,
    CollectorSearchReqSerializer,
    CollectorSearchResponseSerializer,
    ListLogExportRespSerializer,
    LogExportReqSerializer,
    LogExportRespSerializer,
)
from services.web.query.tasks import process_log_export_task
from services.web.query.utils.doris import DorisSQLBuilder

from .base import QueryBaseResource, SearchDataParser, SearchExportTaskBaseResource


class CollectorSearchConfigResource(QueryBaseResource):
    name = gettext_lazy("日志查询配置")
    many_response_data = True
    ResponseSerializer = CollectorSearchConfigRespSerializer

    def perform_request(self, validated_request_data):
        return COLLECT_SEARCH_CONFIG.to_json()


class CollectorSearchAllResource(QueryBaseResource, SearchDataParser):
    name = gettext_lazy("日志搜索(All)")
    RequestSerializer = CollectorSearchAllReqSerializer
    serializer_class = CollectorSearchResponseSerializer

    def build_sql(self, validated_request_data):
        """
        构建日志查询SQL
        """

        page = validated_request_data["page"]
        page_size = validated_request_data["page_size"]
        namespace = validated_request_data["namespace"]
        filters = validated_request_data["filters"]
        # 获取默认日志 RT
        collector_plugin_id = GlobalMetaConfig.get(
            config_key=COLLECTOR_PLUGIN_ID,
            config_level=ConfigLevelChoices.NAMESPACE.value,
            instance_key=namespace,
        )
        plugin = CollectorPlugin.objects.get(collector_plugin_id=collector_plugin_id)
        collector_rt_id = plugin.build_result_table_id(settings.DEFAULT_BK_BIZ_ID, plugin.collector_plugin_name_en)
        sql_builder = DorisSQLBuilder(
            table=collector_rt_id,
            filters=filters,
            sort_list=validated_request_data["sort_list"],
            page=page,
            page_size=page_size,
        )
        data_sql = sql_builder.build_data_sql()
        count_sql = sql_builder.build_count_sql()
        logger.info(f"[{self.__class__.__name__}] search data_sql: {data_sql};count_sql:{count_sql}")
        return data_sql, count_sql

    def perform_request(self, validated_request_data):
        page = validated_request_data["page"]
        page_size = validated_request_data["page_size"]
        bind_system_info = validated_request_data["bind_system_info"]
        data_sql, count_sql = self.build_sql(validated_request_data)
        bulk_req_params = [
            {
                "sql": data_sql,
                "prefer_storage": StorageType.DORIS.value,
            },
            {
                "sql": count_sql,
                "prefer_storage": StorageType.DORIS.value,
            },
        ]
        # 请求BKBASE数据
        bulk_resp = api.bk_base.query_sync.bulk_request(bulk_req_params)
        data_resp, count_resp = bulk_resp
        data = self.parse_data(data_resp.get("list", []))
        # 补充系统信息
        if bind_system_info:
            systems = resource.meta.system_list(namespace=validated_request_data["namespace"])
            system_map = {system["system_id"]: system for system in systems}
            for value in data:
                value["system_info"] = system_map.get(value.get("system_id"), dict())
        # 请求总数
        total = count_resp.get("list", [{}])[0].get("count", 0)
        # 响应
        resp = {
            "page": page,
            "num_pages": page_size,
            "total": total,
            "results": data,
            "query_sql": data_sql,
            "count_sql": count_sql,
        }
        return resp


class CollectorSearchResource(CollectorSearchAllResource):
    name = gettext_lazy("日志查询")
    RequestSerializer = CollectorSearchReqSerializer
    serializer_class = CollectorSearchResponseSerializer
    audit_action = ActionEnum.SEARCH_REGULAR_EVENT


class CreateCollectorSearchExportTask(SearchExportTaskBaseResource):
    name = gettext_lazy("创建日志检索导出任务")
    audit_action = ActionEnum.SEARCH_REGULAR_EVENT
    RequestSerializer = LogExportReqSerializer
    ResponseSerializer = LogExportRespSerializer

    def record_export_fields(self, validated_request_data: dict):
        """
        记录导出字段信息
        """

        export_fields = validated_request_data["export_config"]["fields"]
        export_field_logs = [
            ExportFieldLog(raw_name=field["raw_name"], display_name=field["display_name"], keys=field["keys"])
            for field in export_fields
            if field["display_name"]
        ]
        ExportFieldLog.objects.bulk_create(export_field_logs)

    def perform_request(self, validated_request_data):
        # 获取总条数进行判断
        total = DataFetcher.get_total(validated_request_data["query_params"])
        if total > settings.LOG_EXPORT_MAX_COUNT:
            raise LogExportMaxCountError(current_count=total, max_count=settings.LOG_EXPORT_MAX_COUNT)
        try:
            self.record_export_fields(validated_request_data)
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] create export field logs failed: {e}")
        task: LogExportTask = LogExportTask.objects.create(
            namespace=validated_request_data["namespace"],
            name=validated_request_data["name"],
            query_params=validated_request_data["query_params"],
            export_config=validated_request_data["export_config"],
            status=TaskEnum.READY.value,
            search_params_url=validated_request_data["search_params_url"],
            total=total,
        )
        process_log_export_task.delay(task_id=task.id)
        return task


class ListCollectorSearchExportTask(SearchExportTaskBaseResource):
    name = gettext_lazy("获取日志检索导出任务列表")
    ResponseSerializer = ListLogExportRespSerializer
    many_response_data = True

    def perform_request(self, validated_request_data):
        namespace = validated_request_data["namespace"]
        tasks = LogExportTask.objects.filter(namespace=namespace)
        username = self.get_request_username()
        if not is_system_admin(username):
            tasks = tasks.filter(created_by=username)
        return tasks


class GetCollectorSearchExportTask(SearchExportTaskBaseResource):
    name = gettext_lazy("获取日志检索导出任务详情")
    ResponseSerializer = LogExportRespSerializer

    def perform_request(self, validated_request_data):
        task: LogExportTask = get_object_or_404(LogExportTask, id=validated_request_data["id"])
        # 检查用户是否有权限访问该任务
        self.validate_task_permission(task)
        return task


class DownloadCollectorSearchExportTask(SearchExportTaskBaseResource):
    name = gettext_lazy("下载日志检索导出任务")

    def perform_request(self, validated_request_data):
        task: LogExportTask = get_object_or_404(LogExportTask, id=validated_request_data["id"])
        # 检查用户是否有权限访问该任务
        self.validate_task_permission(task)
        # 检查任务状态
        if task.status != TaskEnum.SUCCESS.value:
            raise LogExportTaskStatusError(status=dict(TaskEnum.choices).get(task.status))
        # 下载文件
        origin_name = task.result["origin_name"]
        storage_name = task.result["storage_name"]
        # 创建流式响应对象
        stream_response = FileResponse(BKRepoFile(storage_name, storage=BKRepoStorage()), filename=origin_name)
        # 设置下载头信息
        stream_response['Content-Type'] = 'application/octet-stream'
        return stream_response
