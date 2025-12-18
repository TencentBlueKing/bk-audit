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
from unittest import mock

from tests.base import TestCase
from tests.test_permission.constants import (
    CHECK_ALLOWED_API_RESP,
    CHECK_PERMISSION_DATA,
    CHECK_PERMISSION_OF_BK_LOG_DATA,
    CHECK_PERMISSION_PARAMS,
    PermissionMock,
)


class PermissionTest(TestCase):
    def setUp(self) -> None:
        pass

    @mock.patch("permission.resources.Permission", mock.Mock(return_value=PermissionMock()))
    def test_check_permission(self):
        """CheckPermissionResource"""
        result = self.resource.permission.check_permission(**CHECK_PERMISSION_PARAMS)
        self.assertEqual(result, CHECK_PERMISSION_DATA)

    @mock.patch("permission.resources.api.bk_log.check_allowed", mock.Mock(return_value=CHECK_ALLOWED_API_RESP))
    @mock.patch("permission.resources.settings.BK_IAM_SYSTEM_ID", mock.Mock(return_value=None))
    def test_check_permission_of_bk_log(self):
        """CheckPermissionResource"""
        result = self.resource.permission.check_permission(**CHECK_PERMISSION_PARAMS)
        self.assertEqual(result, CHECK_PERMISSION_OF_BK_LOG_DATA)
