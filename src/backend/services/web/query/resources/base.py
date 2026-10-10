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

from apps.audit.resources import AuditMixinResource
from apps.meta.utils.tools import is_system_admin
from apps.permission.handlers.service import PermissionService
from core.models import get_request_username
from services.web.query.exceptions import LogExportTaskNoPermission
from services.web.query.models import LogExportTask
from services.web.query.search_data import SearchDataParser as BaseSearchDataParser


class QueryBaseResource(AuditMixinResource, abc.ABC):
    tags = ["Query"]

    def get_request_username(self) -> str:
        return get_request_username()


class SearchDataParser(BaseSearchDataParser):
    """兼容旧 Resource 导入和 mock 路径的脱敏解析器。"""

    @staticmethod
    def _permission_service(username: str) -> PermissionService:
        return PermissionService(username=username)

    @staticmethod
    def _request_username() -> str:
        return get_request_username()


class SearchExportTaskBaseResource(QueryBaseResource, abc.ABC):
    def validate_task_permission(self, task: LogExportTask) -> None:
        username = self.get_request_username()
        if not (is_system_admin(username) or username == task.created_by):
            raise LogExportTaskNoPermission()
