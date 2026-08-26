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
either express or implied. See the License for the specific language governing
permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

"""F1 字段上下文服务测试"""

from unittest import mock

from django.test import override_settings

from services.web.query.ai_assistant.exceptions import AIPermissionDeniedError
from services.web.query.ai_assistant.services.field_context import FieldContextService
from services.web.query.constants import COLLECT_SEARCH_CONFIG
from tests.test_query.test_ai_assistant.base import AIAssistantTestCase

FIELD_CONTEXT_MODULE = "services.web.query.ai_assistant.services.field_context"


@mock.patch(f"{FIELD_CONTEXT_MODULE}.api.bk_base.query_sync")
@mock.patch(f"{FIELD_CONTEXT_MODULE}.resource.meta.system_list")
@mock.patch(f"{FIELD_CONTEXT_MODULE}.GlobalMetaConfig.get")
@mock.patch(f"{FIELD_CONTEXT_MODULE}.SearchLogPermission.has_system_search_permission")
class TestFieldContextService(AIAssistantTestCase):
    """F1 字段上下文服务（L0+L1+L2，L2 默认关闭）

    注意：mock.patch 装饰器参数从下到上注入（最下面的装饰器对应第一个参数）。
    """

    def _build(self):
        return FieldContextService.build_selection(
            namespace=self.namespace, system_ids=[self.target_system_id], username=self.username
        )

    def test_build_selection_success(self, mock_perm, mock_meta_get, mock_system_list, mock_query_sync):
        mock_perm.return_value = True
        mock_meta_get.return_value = {}
        mock_system_list.return_value = [{"system_id": self.target_system_id, "name": self.target_system_name}]

        output = self._build()

        self.assertEqual(len(output.systems), 1)
        system = output.systems[0]
        self.assertEqual(system.system_id, self.target_system_id)
        self.assertEqual(system.name, self.target_system_name)
        # 字段清单与检索白名单同源全量
        self.assertEqual(len(system.standard_fields), len(COLLECT_SEARCH_CONFIG.field_configs))
        raw_names = {field.raw_name for field in system.standard_fields}
        self.assertIn("system_id", raw_names)
        # allow_operators 与配置一致
        system_id_field = next(field for field in system.standard_fields if field.raw_name == "system_id")
        self.assertEqual(system_id_field.allow_operators, ["include", "eq"])
        # 常见/历史操作由平台层组装，query 层输出不含操作榜单字段
        self.assertFalse(hasattr(output, "common_operations"))

    def test_no_permission_raises(self, mock_perm, mock_meta_get, mock_system_list, mock_query_sync):
        mock_perm.return_value = False

        with self.assertRaises(AIPermissionDeniedError) as ctx:
            self._build()
        self.assertEqual(ctx.exception.error_code, "PERMISSION_DENIED")

    def test_permission_checked_with_explicit_username(
        self, mock_perm, mock_meta_get, mock_system_list, mock_query_sync
    ):
        mock_perm.return_value = True
        mock_meta_get.return_value = {}
        mock_system_list.return_value = []

        self._build()
        mock_perm.assert_called_once_with(self.target_system_id, self.username)

    def test_nl_name_defaults_to_display_name(self, mock_perm, mock_meta_get, mock_system_list, mock_query_sync):
        mock_perm.return_value = True
        mock_meta_get.return_value = {}
        mock_system_list.return_value = []

        output = self._build()
        for field in output.systems[0].standard_fields:
            self.assertEqual(field.nl_name, field.display_name)

    def test_l1_override_standard_field(self, mock_perm, mock_meta_get, mock_system_list, mock_query_sync):
        mock_perm.return_value = True
        mock_meta_get.return_value = {
            "systems": {
                self.target_system_id: {
                    "fields": {
                        "username": {"nl_name": "操作人NL", "description": "自定义描述", "sample_value": "admin"}
                    }
                }
            }
        }
        mock_system_list.return_value = []

        output = self._build()
        username_field = next(field for field in output.systems[0].standard_fields if field.raw_name == "username")
        self.assertEqual(username_field.nl_name, "操作人NL")
        self.assertEqual(username_field.description, "自定义描述")
        self.assertEqual(username_field.sample_value, "admin")

    def test_l1_extension_fields(self, mock_perm, mock_meta_get, mock_system_list, mock_query_sync):
        mock_perm.return_value = True
        mock_meta_get.return_value = {
            "systems": {
                self.target_system_id: {
                    "extension_fields": [
                        {"raw_name": "extend_data", "keys": ["ticket_id"], "display_name": "工单内容"}
                    ]
                }
            }
        }
        mock_system_list.return_value = []

        output = self._build()
        extension_fields = output.systems[0].extension_fields
        self.assertEqual(len(extension_fields), 1)
        ext = extension_fields[0]
        self.assertEqual(ext.raw_name, "extend_data")
        self.assertEqual(ext.keys, ["ticket_id"])
        # D-G：拓展字段 nl_name 带 extend. 前缀
        self.assertEqual(ext.nl_name, "extend.工单内容")
        self.assertEqual(ext.system_id, self.target_system_id)
        self.assertTrue(ext.allow_operators)

    def test_l2_disabled_by_default(self, mock_perm, mock_meta_get, mock_system_list, mock_query_sync):
        """L2 默认关闭：sample_value 为 None，不发起 bk_base 采样"""
        mock_perm.return_value = True
        mock_meta_get.return_value = {}
        mock_system_list.return_value = []

        output = self._build()
        for field in output.systems[0].standard_fields:
            self.assertIsNone(field.sample_value)
        self.assertEqual(output.systems[0].extension_fields, [])
        mock_query_sync.assert_not_called()


@mock.patch(f"{FIELD_CONTEXT_MODULE}.CollectorPlugin.build_collector_rt")
@mock.patch(f"{FIELD_CONTEXT_MODULE}.api.bk_base.query_sync")
@mock.patch(f"{FIELD_CONTEXT_MODULE}.resource.meta.system_list")
@mock.patch(f"{FIELD_CONTEXT_MODULE}.GlobalMetaConfig.get")
@mock.patch(f"{FIELD_CONTEXT_MODULE}.SearchLogPermission.has_system_search_permission")
class TestFieldContextL2Sampling(AIAssistantTestCase):
    """L2 采样开启路径：sample_value 回填（原始查询值）+ 拓展字段发现

    注意：mock.patch 装饰器参数从下到上注入（最下面的装饰器对应第一个参数）。
    """

    SAMPLE_ROW = {
        "username": "admin",
        "system_id": "bk_log",
        "result_code": 0,  # 原始查询值，非"成功(0)"
        "extend_data": {"ticket_id": "Story-3000", "custom_key": "v"},
    }

    @override_settings(AI_ASSISTANT_FIELD_SAMPLE_ENABLED=True)
    def test_l2_enabled_fills_sample_value_and_extensions(
        self, mock_perm, mock_meta_get, mock_system_list, mock_query_sync, mock_build_rt
    ):
        mock_build_rt.return_value = "test_rt.doris"
        mock_perm.return_value = True
        mock_meta_get.return_value = {}
        mock_system_list.return_value = []
        mock_query_sync.return_value = {"list": [self.SAMPLE_ROW]}

        output = FieldContextService.build_selection(
            namespace=self.namespace, system_ids=[self.target_system_id], username=self.username
        )

        system = output.systems[0]
        # sample_value 回填：原始查询值
        username_field = next(field for field in system.standard_fields if field.raw_name == "username")
        self.assertEqual(username_field.sample_value, "admin")
        result_code_field = next(field for field in system.standard_fields if field.raw_name == "result_code")
        self.assertEqual(result_code_field.sample_value, 0)
        # 拓展字段发现：extend_data 第一层子键（sub_keys=[] 全量发现）
        extension_fields = system.extension_fields
        self.assertTrue(extension_fields)
        for ext in extension_fields:
            self.assertEqual(ext.system_id, self.target_system_id)
            self.assertTrue(ext.nl_name.startswith("extend."))
        discovered = {(ext.raw_name, tuple(ext.keys)) for ext in extension_fields}
        self.assertIn(("extend_data", ("ticket_id",)), discovered)
        self.assertIn(("extend_data", ("custom_key",)), discovered)
        # 采样调用发生
        mock_query_sync.assert_called_once()

    @override_settings(AI_ASSISTANT_FIELD_SAMPLE_ENABLED=True)
    def test_l2_sampling_failure_degrades_gracefully(
        self, mock_perm, mock_meta_get, mock_system_list, mock_query_sync, mock_build_rt
    ):
        """采样失败不阻断主流程，退化为 sample_value=None"""
        mock_build_rt.return_value = "test_rt.doris"
        mock_perm.return_value = True
        mock_meta_get.return_value = {}
        mock_system_list.return_value = []
        mock_query_sync.side_effect = Exception("doris down")

        output = FieldContextService.build_selection(
            namespace=self.namespace, system_ids=[self.target_system_id], username=self.username
        )

        for field in output.systems[0].standard_fields:
            self.assertIsNone(field.sample_value)
        self.assertEqual(output.systems[0].extension_fields, [])
