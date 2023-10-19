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

from django.conf import settings

from apps.permission.handlers.resource_types import ResourceEnum


class BkLogPermissionVersion:
    """
    日志平台权限版本管理
    """

    # 版本信息
    VERSION = settings.BKLOG_PERMISSION_VERSION

    # 关联的资源类型
    BUSINESS_VERSION = {"1": [ResourceEnum.BUSINESS_BK_LOG], "2": [ResourceEnum.SPACE_BK_LOG]}
    RELATED_RESOURCE_TYPES = {"create_collection": BUSINESS_VERSION, "view_business": BUSINESS_VERSION}

    def __init__(self, action_id: str):
        self._action_id = action_id

    @property
    def action_id(self) -> str:
        """
        操作ID
        """

        # 版本1
        if self.VERSION == "1":
            return f"{self._action_id}_bk_log"
        # 版本2
        if self.VERSION == "2":
            return f"{self._action_id}_v2_bk_log"
        # 默认返回原始
        return self._action_id

    @property
    def related_resource_types(self):
        """
        关联的资源类型
        """

        # 获取版本映射 Map
        version_map = self.RELATED_RESOURCE_TYPES.get(self._action_id, {})
        if not version_map:
            return []
        # 获取当前版本关联的资源类型
        return version_map.get(self.VERSION, [])
