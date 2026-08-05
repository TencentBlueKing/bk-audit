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
from typing import List

from apps.audit.resources import AuditMixinResource
from apps.meta.models import SensitiveObject
from apps.meta.utils.tools import is_system_admin
from apps.permission.handlers.service import PermissionService
from core.models import get_request_username
from services.web.query.exceptions import LogExportTaskNoPermission
from services.web.query.models import LogExportTask
from services.web.query.utils.formatter import HitsFormatter


class QueryBaseResource(AuditMixinResource, abc.ABC):
    tags = ["Query"]

    def get_request_username(self) -> str:
        return get_request_username()


class SearchDataParser:
    @staticmethod
    def mark_sensitive_permissions(sensitive_objs: List[SensitiveObject], username: str) -> None:
        """Mark sensitive objects; PermissionService hides V3 resource vs V4 no-resource details."""
        if not username:
            for sensitive_obj in sensitive_objs:
                setattr(sensitive_obj, "_has_permission", False)
            return

        permissions = PermissionService(username=username).get_sensitive_object_permissions(
            [sensitive_obj.id for sensitive_obj in sensitive_objs]
        )
        for sensitive_obj in sensitive_objs:
            setattr(sensitive_obj, "_has_permission", permissions.get(str(sensitive_obj.id), False))

    def parse_data(self, data: List[dict]) -> list:
        # 获取敏感字段列表
        private_sensitive_objs = list(SensitiveObject._objects.filter(is_private=True))
        sensitive_objs = list(SensitiveObject.objects.all())
        # 获取用户信息，用于判断敏感权限
        if sensitive_objs:
            self.mark_sensitive_permissions(sensitive_objs, get_request_username())
        # parse
        return [HitsFormatter(value, [*sensitive_objs, *private_sensitive_objs]).value for value in data]


class SearchExportTaskBaseResource(QueryBaseResource, abc.ABC):
    def validate_task_permission(self, task: LogExportTask) -> None:
        username = self.get_request_username()
        if not (is_system_admin(username) or username == task.created_by):
            raise LogExportTaskNoPermission()
