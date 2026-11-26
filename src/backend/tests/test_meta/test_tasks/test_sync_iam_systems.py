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
import json
from unittest import mock

import pytest
import requests
from blueapps.core.celery import celery_app
from django.test import override_settings

from api.bk_iam_v4.default import ListSystemResource, RetrieveSystemResource
from apps.meta.constants import SystemSourceTypeEnum
from apps.meta.models import Action, ResourceType, ResourceTypeActionRelation, System
from apps.meta.tasks import sync_iam_systems, sync_system_paas_info
from core.testing import assert_list_contains
from tests.base import TestCase
from tests.conftest import (
    mock_bk_paas_uni_apps_query,
    mock_iam_get_system_info,
    mock_iam_get_system_roles,
    mock_iam_get_systems,
    mock_iam_v4_list_system,
    mock_iam_v4_retrieve_system,
)
from tests.test_meta.constants import (
    ADD_CUSTOM_SYSTEMS,
    AUDIT_CUSTOM_SYSTEM,
    EXPECT_IAM_SYSTEMS,
)


@pytest.mark.django_db(transaction=True)
class TestSyncIamSystems(TestCase):
    """
    测试同步 IAM 系统
    1. 测试同步 IAM V3 和 V4 的系统数据正常
    2. 测试本地编辑系统，删除，新增系统后，同步后数据正常
    3. 测试并发同步
    """

    def mock_api(self):
        self.mock_iam_get_systems = mock_iam_get_systems().start()
        self.mock_iam_get_system_roles = mock_iam_get_system_roles().start()
        self.mock_iam_get_system_info = mock_iam_get_system_info().start()
        self.mock_iam_v4_list_system = mock_iam_v4_list_system().start()
        self.mock_iam_v4_retrieve_system = mock_iam_v4_retrieve_system().start()
        self.mock_bk_paas_uni_apps_query = mock_bk_paas_uni_apps_query().start()

    def setUp(self):
        super().setUp()
        # 初始创建测试系统
        self.mock_api()
        self.orig_eager = celery_app.conf.task_always_eager
        celery_app.conf.task_always_eager = True

    def tearDown(self):
        super().tearDown()
        mock.patch.stopall()
        celery_app.conf.task_always_eager = self.orig_eager

    def _get_system_data(self):
        """获取格式化后的系统数据"""
        return list(System.objects.all().values().order_by('-system_id'))

    def sync_system(self):
        """同步系统"""
        sync_iam_systems()
        sync_system_paas_info()

    def test_sync_systems(self):
        """测试同步IAM V3系统"""
        # 1. 测试同步正常
        self.sync_system()
        actual = self._get_system_data()
        assert_list_contains(actual, EXPECT_IAM_SYSTEMS)
        # 2. 修改本地系统后同步后正常
        system = System.objects.get(system_id="test_system")
        system.name = "Modified System"
        system.save(update_fields=['name'])
        self.sync_system()
        actual = self._get_system_data()
        assert_list_contains(actual, EXPECT_IAM_SYSTEMS)
        # 3. 删除系统后同步后正常
        system.delete()
        self.sync_system()
        actual = self._get_system_data()
        assert_list_contains(actual, EXPECT_IAM_SYSTEMS)
        # 4. 新增系统后同步后正常
        new_system: System = System.objects.create(
            instance_id="new_system", source_type=SystemSourceTypeEnum.IAM_V3.value, name="New System"
        )
        ResourceType.objects.create(
            system_id=new_system.system_id,
            resource_type_id="new_resource_type",
            name="New Resource Type",
            description="New Resource Type Description",
        )
        Action.objects.create(
            system_id=new_system.system_id,
            action_id="new_action",
            name="New Action",
            description="New Action Description",
        )
        self.sync_system()
        actual = self._get_system_data()
        assert_list_contains(actual, EXPECT_IAM_SYSTEMS)
        # 5. 新增自定义系统后同步后仍然保留
        System.objects.create(**AUDIT_CUSTOM_SYSTEM)
        self.sync_system()
        actual = self._get_system_data()
        assert_list_contains(actual, ADD_CUSTOM_SYSTEMS)
        # 6. 修改自定义字段后同步不会被覆盖
        system = System.objects.get(system_id="test_system")
        system.managers = ["modify_manager"]
        system.save(update_fields=['managers'])
        self.sync_system()
        system.refresh_from_db()
        self.assertEqual(system.managers, ["modify_manager"])

    def test_sync_systems_deletes_related_resources_and_actions(self):
        """同步删除下线系统时同步清理其资源、操作和关联关系"""
        stale_system = System.objects.create(
            namespace=self.namespace,
            source_type=SystemSourceTypeEnum.IAM_V4.value,
            instance_id="cmdb_inspection",
            name="CMDB 巡检",
        )
        ResourceType.objects.create(system_id=stale_system.system_id, resource_type_id="biz", name="业务")
        Action.objects.create(system_id=stale_system.system_id, action_id="view_biz", name="查看业务")
        ResourceTypeActionRelation.objects.create(
            system_id=stale_system.system_id,
            resource_type_id="biz",
            action_id="view_biz",
        )

        self.sync_system()

        self.assertFalse(System.objects.filter(system_id=stale_system.system_id).exists())
        self.assertFalse(ResourceType.objects.filter(system_id=stale_system.system_id).exists())
        self.assertFalse(Action.objects.filter(system_id=stale_system.system_id).exists())
        self.assertFalse(ResourceTypeActionRelation.objects.filter(system_id=stale_system.system_id).exists())


MOCK_ADMIN_USERNAME = "mock_bk_admin"


@override_settings(
    BKPAAS_MULTI_TENANT_MODE=True,
    BK_TENANT_ID="tencent",
    BKIAM_APIGW_NAME="tenant-iam",
)
class TestSyncIamV4SystemsUsesAdminIdentityWithoutWebRequest(TestCase):
    """多租户下，后台系统同步（无登录用户）必须以租户管理员身份出站，不被用户态拦截。"""

    def _patch_transport(self, endpoint, payload):
        """只 mock 传输层，让鉴权分支（add_esb_info_before_request）真实执行。"""
        method = "get" if endpoint.method == "GET" else "request"

        def fake_send(*args, **kwargs):
            response = requests.Response()
            response.status_code = 200
            # SDK 标准响应格式，parse_response 会取其中 data
            response._content = json.dumps({"result": True, "code": 0, "data": payload}).encode()
            return response

        return mock.patch.object(endpoint.session, method, side_effect=fake_send)

    def _patch_admin_lookup(self):
        """固定管理员解析结果：不触虚拟用户网关，且断言使用独立期望值。"""
        return mock.patch("core.bk_api_base.get_admin_username", return_value=MOCK_ADMIN_USERNAME)

    def test_list_system_uses_admin_identity_without_web_request(self):
        endpoint = ListSystemResource()
        payload = [{"id": "test_system", "name": "IAM V4 测试系统"}]

        with self._patch_admin_lookup():
            with self._patch_transport(endpoint, payload) as transport:
                endpoint.request({"page": 1, "page_size": 1})

        headers = transport.call_args.kwargs["headers"]
        auth = json.loads(headers["x-bkapi-authorization"])
        self.assertEqual(headers["X-Bk-Tenant-Id"], "tencent")
        # 应用态：使用租户管理员身份，而非真实登录用户
        self.assertEqual(auth["bk_username"], MOCK_ADMIN_USERNAME)

    def test_retrieve_system_uses_admin_identity_without_web_request(self):
        endpoint = RetrieveSystemResource()
        payload = {"id": "test_system", "name": "IAM V4 测试系统", "system_info": {}}

        with self._patch_admin_lookup():
            with self._patch_transport(endpoint, payload) as transport:
                endpoint.request({"system_id": "test_system"})

        headers = transport.call_args.kwargs["headers"]
        auth = json.loads(headers["x-bkapi-authorization"])
        self.assertEqual(headers["X-Bk-Tenant-Id"], "tencent")
        self.assertEqual(auth["bk_username"], MOCK_ADMIN_USERNAME)
