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
import copy
from unittest import mock

from apps.permission.handlers.actions import ActionEnum


class PermissionMock(mock.MagicMock):
    @classmethod
    def batch_make_resource(cls, resources):
        return []

    @staticmethod
    def is_allowed(self, action):
        return False


# Check Permission
CHECK_PERMISSION_PARAMS = {
    "action_ids": ActionEnum.SEARCH_REGULAR_EVENT.id,
    "resources": ActionEnum.SEARCH_REGULAR_EVENT.related_resource_types[0].id,
}
CHECK_ALLOWED_API_RESP = {CHECK_PERMISSION_PARAMS["action_ids"]: False}
CHECK_PERMISSION_DATA = copy.deepcopy(CHECK_ALLOWED_API_RESP)
CHECK_PERMISSION_OF_BK_LOG_DATA = copy.deepcopy(CHECK_ALLOWED_API_RESP)
