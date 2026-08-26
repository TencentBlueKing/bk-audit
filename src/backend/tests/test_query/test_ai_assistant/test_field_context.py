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

F1 字段上下文服务测试
"""

from unittest import mock

from django.test import override_settings

from apps.meta.models import Field
from core.sql.constants import Operator
from services.web.query.ai_assistant.exceptions import AIPermissionDeniedError
from services.web.query.ai_assistant.services.field_context import FieldContextService
from services.web.query.constants import COLLECT_SEARCH_CONFIG
from services.web.query.utils.field_map import FieldMapHandler
from services.web.query.utils.search_config import (
    CollectorSearchConfig,
    FieldSearchConfig,
)
from tests.test_query.test_ai_assistant.base import AIAssistantTestCase

FIELD_CONTEXT_MODULE = "services.web.query.ai_assistant.services.field_context"


@override_settings(AI_ASSISTANT_FIELD_SAMPLE_ENABLED=False)
@mock.patch(f"{FIELD_CONTEXT_MODULE}.api.bk_base.query_sync")
@mock.patch(f"{FIELD_CONTEXT_MODULE}.resource.meta.system_list")
@mock.patch(f"{FIELD_CONTEXT_MODULE}.GlobalMetaConfig.get")
@mock.patch(f"{FIELD_CONTEXT_MODULE}.SearchLogPermission.has_system_search_permission")
class TestFieldContextService(AIAssistantTestCase):
    """F1 字段上下文服务（L0+L1 行为；L2 关闭路径，开启路径见 TestFieldContextL2Sampling）

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
        # 字段类型透出（前端渲染值控件依据；与 ConditionField.field_type 同源 FieldType.value）
        self.assertEqual(system_id_field.field_type, "string")
        # 枚举 options 内嵌：与日志检索页 field_map 同构；非枚举字段为 None
        self.assertIsNone(system_id_field.options)
        result_code_field = next(field for field in system.standard_fields if field.raw_name == "result_code")
        self.assertEqual(result_code_field.field_type, "int")
        self.assertEqual(
            [item.model_dump() for item in result_code_field.options],
            [{"id": "0", "name": "成功"}, {"id": "-1", "name": "其他"}],
        )
        # 常见/历史操作由平台层组装，query 层输出不含操作榜单字段
        self.assertFalse(hasattr(output, "common_operations"))

    def test_enum_options_same_source_as_field_map(self, mock_perm, mock_meta_get, mock_system_list, mock_query_sync):
        """枚举 options 与 FieldMapHandler（es_query/field_map 接口）同源同构"""
        mock_perm.return_value = True
        mock_meta_get.return_value = {}
        mock_system_list.return_value = []

        output = self._build()
        by_name = {field.raw_name: field for field in output.systems[0].standard_fields}

        # 有且仅有 3 个枚举字段带 options（与 db_field_func_map 对齐）
        with_options = {name for name, field in by_name.items() if field.options}
        self.assertEqual(with_options, {"access_type", "user_identify_type", "result_code"})
        for name in with_options:
            handler = FieldMapHandler(fields=[name], timedelta=1, namespace=self.namespace)
            self.assertEqual(
                [item.model_dump() for item in by_name[name].options],
                handler.field_map[name],
            )

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
                    "fields": {"username": {"nl_name": "操作人NL", "description": "自定义描述", "sample_value": "admin"}}
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
                    "extension_fields": [{"raw_name": "extend_data", "keys": ["ticket_id"], "display_name": "工单内容"}]
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
        # 一期拓展字段恒 string（协议待冻结 #6）
        self.assertEqual(ext.field_type, "string")

    def test_l2_disabled_via_settings(self, mock_perm, mock_meta_get, mock_system_list, mock_query_sync):
        """L2 可经配置关闭（BKAPP_AI_ASSISTANT_FIELD_SAMPLE_ENABLED=false）：sample_value 为 None，不发起 bk_base 采样"""
        mock_perm.return_value = True
        mock_meta_get.return_value = {}
        mock_system_list.return_value = []

        output = self._build()
        for field in output.systems[0].standard_fields:
            self.assertIsNone(field.sample_value)
        self.assertEqual(output.systems[0].extension_fields, [])
        mock_query_sync.assert_not_called()

    def test_l1_extension_nl_name_override_taken_as_is(
        self, mock_perm, mock_meta_get, mock_system_list, mock_query_sync
    ):
        """拓展字段 L1 显式配置 nl_name 原样采用（配置方负责携带 extend. 前缀）"""
        mock_perm.return_value = True
        mock_meta_get.return_value = {
            "systems": {
                self.target_system_id: {
                    "extension_fields": [
                        {"raw_name": "extend_data", "keys": ["ticket_id"], "display_name": "工单内容", "nl_name": "工单ID"}
                    ]
                }
            }
        }
        mock_system_list.return_value = []

        output = self._build()
        # L1 显式配置原样采用，不强制补 extend. 前缀（前缀责任在配置方）
        self.assertEqual(output.systems[0].extension_fields[0].nl_name, "工单ID")

        # 对照：未显式配置 nl_name 的拓展字段仍走缺省规则带前缀
        mock_meta_get.return_value = {
            "systems": {
                self.target_system_id: {
                    "extension_fields": [{"raw_name": "extend_data", "keys": ["custom_key"], "display_name": "自定义键"}]
                }
            }
        }
        output2 = self._build()
        self.assertEqual(output2.systems[0].extension_fields[0].nl_name, "extend.自定义键")

    def test_display_name_fallback_priority(self, mock_perm, mock_meta_get, mock_system_list, mock_query_sync):
        """通用字段 display_name 三级兜底：description → alias_name → field_name"""
        mock_perm.return_value = True
        mock_meta_get.return_value = {}
        mock_system_list.return_value = []

        def _field(field_name, description=None, alias_name=""):
            return Field(field_name=field_name, field_type="string", description=description, alias_name=alias_name)

        patched_config = CollectorSearchConfig(
            field_configs=[
                FieldSearchConfig(field=_field("f_with_desc", description="描述字段"), allow_operators=[Operator.EQ]),
                FieldSearchConfig(field=_field("f_with_alias", alias_name="别名字段"), allow_operators=[Operator.EQ]),
                FieldSearchConfig(field=_field("f_raw_only"), allow_operators=[Operator.EQ]),
            ]
        )
        with mock.patch(f"{FIELD_CONTEXT_MODULE}.COLLECT_SEARCH_CONFIG", patched_config):
            output = self._build()

        by_name = {field.raw_name: field for field in output.systems[0].standard_fields}
        self.assertEqual(by_name["f_with_desc"].display_name, "描述字段")
        self.assertEqual(by_name["f_with_alias"].display_name, "别名字段")
        self.assertEqual(by_name["f_raw_only"].display_name, "f_raw_only")
        # 缺省 nl_name 与 display_name 保持一致（沿用既有规则）
        for field in by_name.values():
            self.assertEqual(field.nl_name, field.display_name)


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
