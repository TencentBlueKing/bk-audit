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

import uuid
from typing import Type
from unittest import mock
from unittest.mock import patch

from bk_resource import Resource
from django.test import TestCase
from django.utils import timezone
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from api.bk_base.default import UserAuthBatchCheck
from apps.meta.models import Tag
from apps.permission.handlers.permission import Permission
from services.web.scene.constants import (
    BindingType,
    PanelStatus,
    ResourceVisibilityType,
    VisibilityScope,
)
from services.web.scene.models import (
    ResourceBinding,
    ResourceBindingScene,
    ResourceBindingSystem,
    Scene,
)
from services.web.tool.constants import (
    DataSearchConfigTypeEnum,
    FieldCategory,
    SQLDataSearchConfig,
    SQLDataSearchInputVariable,
    SQLDataSearchOutputField,
    Table,
    ToolTagsEnum,
    ToolTypeEnum,
)
from services.web.tool.exceptions import ToolDoesNotExist
from services.web.tool.models import DataSearchToolConfig, Tool, ToolFavorite, ToolTag
from services.web.tool.resources import (
    DeleteTool,
    FavoriteTool,
    GetToolDetail,
    ListTool,
    ListToolAll,
    ListToolTags,
)


class ToolFavoriteTestCase(TestCase):
    """工具收藏功能测试"""

    def setUp(self):
        self.uid = str(uuid.uuid4())
        self.uid_2 = str(uuid.uuid4())
        self.namespace = "default_ns"
        self.test_user = "test_user"
        self.other_user = "other_user"
        self.scene = Scene.objects.create(name="tool-favorite-scene")
        self.scene_id = self.scene.scene_id

        # 创建测试工具 1
        self.tool_1 = Tool.objects.create(
            uid=self.uid,
            version=1,
            name="Tool Alpha",
            namespace=self.namespace,
            tool_type=ToolTypeEnum.DATA_SEARCH.value,
            created_by=self.test_user,
            config=SQLDataSearchConfig(
                sql="select f1 from test_table",
                referenced_tables=[Table(table_name="test_table")],
                input_variable=[
                    SQLDataSearchInputVariable(
                        raw_name="date_range",
                        required=True,
                        display_name="日期范围",
                        field_category=FieldCategory.TIME_RANGE_SELECT,
                        default_value=None,
                    ),
                ],
                output_fields=[SQLDataSearchOutputField(raw_name="thedate", display_name="日期")],
            ).model_dump(),
            is_deleted=False,
            description="Tool 1 Desc",
            updated_at=timezone.now(),
        )
        DataSearchToolConfig.objects.create(
            tool=self.tool_1,
            data_search_config_type=DataSearchConfigTypeEnum.SQL,
            sql="select 1",
        )

        # 创建测试工具 2
        self.tool_2 = Tool.objects.create(
            uid=self.uid_2,
            version=1,
            name="Tool Beta",
            namespace=self.namespace,
            tool_type=ToolTypeEnum.DATA_SEARCH.value,
            created_by=self.test_user,
            config=SQLDataSearchConfig(
                sql="select f2 from test_table_2",
                referenced_tables=[Table(table_name="test_table_2")],
                input_variable=[],
                output_fields=[SQLDataSearchOutputField(raw_name="field2", display_name="字段2")],
            ).model_dump(),
            is_deleted=False,
            description="Tool 2 Desc",
            updated_at=timezone.now(),
        )
        DataSearchToolConfig.objects.create(
            tool=self.tool_2,
            data_search_config_type=DataSearchConfigTypeEnum.SQL,
            sql="select 2",
        )

        # 创建标签
        self.tag1 = Tag.objects.create(tag_name="tag1")
        ToolTag.objects.create(tool_uid=self.tool_1.uid, tag_id=self.tag1.tag_id)
        self._bind_tools()

        # Mock 权限校验
        self.patcher_auth = mock.patch.object(
            UserAuthBatchCheck,
            "perform_request",
            return_value=[
                {"object_id": "test_table", "result": True, "user_id": "test_user", "permission": {"read": True}},
                {"object_id": "test_table_2", "result": True, "user_id": "test_user", "permission": {"read": True}},
            ],
        )
        self.mock_auth_check = self.patcher_auth.start()

    def tearDown(self):
        mock.patch.stopall()

    def _bind_tools(self):
        ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.TOOL,
            resource_id=self.tool_1.uid,
            binding_type=BindingType.PLATFORM_BINDING,
            visibility_type=VisibilityScope.ALL_VISIBLE,
        )
        scene_binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.TOOL,
            resource_id=self.tool_2.uid,
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=scene_binding, scene_id=self.scene_id)

    def _call_resource_with_request(self, resource_cls: Type[Resource], data):
        factory = APIRequestFactory()
        django_request = factory.post('/fake-url/', data, format='json')
        drf_request = Request(django_request)

        resource = resource_cls()
        request_data = dict(data)
        if resource_cls in [ListTool, ListToolAll, ListToolTags]:
            request_data.setdefault("scope_type", "scene")
            request_data.setdefault("scope_id", str(self.scene_id))
            with (
                patch("services.web.tool.resources.ScopePermission.get_scene_ids", return_value=[self.scene_id]),
                patch("services.web.tool.resources.ScopePermission.get_system_ids", return_value=[]),
            ):
                response = resource.request(request_data, _request=drf_request)
        else:
            response = resource.request(request_data, _request=drf_request)
        # response 可能直接是 ReturnDict/list 或者是 Response 对象
        if hasattr(response, 'data'):
            return response.data.get("results", response.data)
        elif isinstance(response, dict):
            return response.get("results", response)
        elif isinstance(response, list):
            return response
        return response

    # ==================== 收藏/取消收藏测试 ====================

    def test_favorite_tool_add(self):
        """测试收藏工具"""
        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            result = FavoriteTool()({"uid": self.tool_1.uid, "favorite": True})

        self.assertEqual(result["favorite"], True)
        self.assertTrue(ToolFavorite.objects.filter(tool_uid=self.tool_1.uid, username=self.test_user).exists())

    def test_favorite_tool_remove(self):
        """测试取消收藏工具"""
        # 先创建收藏记录
        ToolFavorite.objects.create(tool_uid=self.tool_1.uid, username=self.test_user)

        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            result = FavoriteTool()({"uid": self.tool_1.uid, "favorite": False})

        self.assertEqual(result["favorite"], False)
        self.assertFalse(ToolFavorite.objects.filter(tool_uid=self.tool_1.uid, username=self.test_user).exists())

    def test_favorite_tool_idempotent_add(self):
        """测试重复收藏工具（幂等性）"""
        # 先创建收藏记录
        ToolFavorite.objects.create(tool_uid=self.tool_1.uid, username=self.test_user)

        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            result = FavoriteTool()({"uid": self.tool_1.uid, "favorite": True})

        self.assertEqual(result["favorite"], True)
        # 确保只有一条记录
        self.assertEqual(ToolFavorite.objects.filter(tool_uid=self.tool_1.uid, username=self.test_user).count(), 1)

    def test_favorite_tool_idempotent_remove(self):
        """测试重复取消收藏工具（幂等性）"""
        # 不创建收藏记录，直接取消收藏
        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            result = FavoriteTool()({"uid": self.tool_1.uid, "favorite": False})

        self.assertEqual(result["favorite"], False)
        self.assertFalse(ToolFavorite.objects.filter(tool_uid=self.tool_1.uid, username=self.test_user).exists())

    def test_favorite_tool_not_exist(self):
        """测试收藏不存在的工具"""
        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            with self.assertRaises(ToolDoesNotExist):
                FavoriteTool()({"uid": "non_existent_uid", "favorite": True})

    def test_favorite_tool_user_isolation(self):
        """测试不同用户的收藏隔离"""
        # 用户1收藏
        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            FavoriteTool()({"uid": self.tool_1.uid, "favorite": True})

        # 用户2收藏同一工具
        with patch("services.web.tool.resources.get_request_username", return_value=self.other_user):
            FavoriteTool()({"uid": self.tool_1.uid, "favorite": True})

        # 验证两个用户都有收藏记录
        self.assertTrue(ToolFavorite.objects.filter(tool_uid=self.tool_1.uid, username=self.test_user).exists())
        self.assertTrue(ToolFavorite.objects.filter(tool_uid=self.tool_1.uid, username=self.other_user).exists())

        # 用户1取消收藏
        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            FavoriteTool()({"uid": self.tool_1.uid, "favorite": False})

        # 验证用户1的收藏被删除，用户2的收藏仍在
        self.assertFalse(ToolFavorite.objects.filter(tool_uid=self.tool_1.uid, username=self.test_user).exists())
        self.assertTrue(ToolFavorite.objects.filter(tool_uid=self.tool_1.uid, username=self.other_user).exists())

    # ==================== 收藏状态在列表中的返回测试 ====================

    def test_list_tool_with_favorite_status(self):
        """测试工具列表返回收藏状态"""

        # 收藏 tool_1
        ToolFavorite.objects.create(tool_uid=self.tool_1.uid, username=self.test_user)

        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            data = {"keyword": "", "page": 1, "page_size": 10}
            result = self._call_resource_with_request(ListTool, data)

        # 验证收藏状态
        tool_1_data = next((t for t in result if t["uid"] == self.tool_1.uid), None)
        tool_2_data = next((t for t in result if t["uid"] == self.tool_2.uid), None)

        self.assertIsNotNone(tool_1_data)
        self.assertIsNotNone(tool_2_data)
        self.assertTrue(tool_1_data["favorite"])
        self.assertFalse(tool_2_data["favorite"])
        self.assertEqual(tool_1_data["binding_type"], BindingType.PLATFORM_BINDING)
        self.assertEqual(tool_2_data["binding_type"], BindingType.SCENE_BINDING)

    def test_list_tool_returns_visibility_snapshot(self):
        """测试工具列表返回绑定可见范围快照"""

        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            data = {"keyword": "", "page": 1, "page_size": 10}
            result = self._call_resource_with_request(ListTool, data)

        tool_1_data = next((t for t in result if t["uid"] == self.tool_1.uid), None)
        tool_2_data = next((t for t in result if t["uid"] == self.tool_2.uid), None)

        self.assertEqual(
            tool_1_data["visibility"],
            {
                "binding_type": BindingType.PLATFORM_BINDING,
                "visibility_type": VisibilityScope.ALL_VISIBLE,
                "scene_ids": [],
                "system_ids": [],
            },
        )
        self.assertEqual(
            tool_2_data["visibility"],
            {
                "binding_type": BindingType.SCENE_BINDING,
                "visibility_type": VisibilityScope.SPECIFIC_SCENES,
                "scene_ids": [self.scene_id],
                "system_ids": [],
            },
        )

    def test_list_tool_returns_visibility_system_ids(self):
        """测试工具列表返回系统可见范围"""

        ResourceBinding.objects.filter(resource_id=self.tool_1.uid).update(
            visibility_type=VisibilityScope.SPECIFIC_SYSTEMS
        )
        binding = ResourceBinding.objects.get(resource_id=self.tool_1.uid)
        ResourceBindingSystem.objects.create(binding=binding, system_id="bk_job")

        factory = APIRequestFactory()
        django_request = factory.post('/fake-url/', {"keyword": ""}, format='json')
        drf_request = Request(django_request)

        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            response = ListTool().request({"keyword": ""}, _request=drf_request)

        result = response.data if hasattr(response, "data") else response
        tool_1_data = next((t for t in result if t["uid"] == self.tool_1.uid), None)
        self.assertEqual(
            tool_1_data["visibility"],
            {
                "binding_type": BindingType.PLATFORM_BINDING,
                "visibility_type": VisibilityScope.SPECIFIC_SYSTEMS,
                "scene_ids": [],
                "system_ids": ["bk_job"],
            },
        )

    def test_attach_visibility_metadata_uses_batch_queries(self):
        """测试工具可见范围元数据批量查询，避免按工具 N+1 查询"""

        with self.assertNumQueries(3):
            ListTool.attach_visibility_metadata([self.tool_1, self.tool_2])

        self.assertEqual(self.tool_1.visibility["binding_type"], BindingType.PLATFORM_BINDING)
        self.assertEqual(self.tool_2.visibility["scene_ids"], [self.scene_id])

    def test_list_tool_favorite_first_ordering(self):
        """测试工具列表收藏优先排序"""

        # 收藏 tool_2（名称为 Beta，按名称排序应该在后面）
        ToolFavorite.objects.create(tool_uid=self.tool_2.uid, username=self.test_user)

        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            data = {"keyword": "", "page": 1, "page_size": 10}
            result = self._call_resource_with_request(ListTool, data)

        # 验证收藏的工具排在前面
        self.assertEqual(result[0]["uid"], self.tool_2.uid)
        self.assertTrue(result[0]["favorite"])

    # ==================== 收藏筛选测试 ====================

    def test_list_tool_filter_by_favorite_tag(self):
        """测试通过收藏虚拟标签筛选工具"""

        # 收藏 tool_1
        ToolFavorite.objects.create(tool_uid=self.tool_1.uid, username=self.test_user)

        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            data = {"keyword": "", "tags": [int(ToolTagsEnum.FAVORITE_TOOLS.value)], "page": 1, "page_size": 10}
            result = self._call_resource_with_request(ListTool, data)

        # 验证只返回收藏的工具
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["uid"], self.tool_1.uid)

    def test_list_tool_filter_by_favorite_tag_empty(self):
        """测试没有收藏时通过收藏虚拟标签筛选返回空"""

        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            data = {"keyword": "", "tags": [int(ToolTagsEnum.FAVORITE_TOOLS.value)], "page": 1, "page_size": 10}
            result = self._call_resource_with_request(ListTool, data)

        # 验证返回空列表
        self.assertEqual(len(result), 0)

    def test_list_tool_tags_include_favorite_tools(self):
        """测试工具标签列表返回我的收藏虚拟标签"""

        ToolFavorite.objects.create(tool_uid=self.tool_1.uid, username=self.test_user)
        ToolFavorite.objects.create(tool_uid=self.tool_2.uid, username=self.other_user)

        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            result = self._call_resource_with_request(ListToolTags, {"status": None})

        tag_counts = {item["tag_id"]: item["tool_count"] for item in result}
        self.assertEqual(tag_counts[ToolTagsEnum.FAVORITE_TOOLS.value], 1)

    def test_list_tool_tags_favorite_tools_filter_by_status_and_scope(self):
        """测试我的收藏标签数量按状态和 scope 过滤"""

        other_scene = Scene.objects.create(name="other-favorite-scene")
        other_uid = str(uuid.uuid4())
        other_tool = Tool.objects.create(
            uid=other_uid,
            version=1,
            name="Other Scene Tool",
            namespace=self.namespace,
            tool_type=ToolTypeEnum.DATA_SEARCH.value,
            created_by=self.test_user,
            config=self.tool_1.config,
            is_deleted=False,
            description="Other Scene Tool Desc",
            updated_at=timezone.now(),
        )
        other_binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.TOOL,
            resource_id=other_tool.uid,
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=other_binding, scene_id=other_scene.scene_id)

        self.tool_1.status = PanelStatus.PUBLISHED
        self.tool_1.save(update_fields=["status"])
        self.tool_2.status = PanelStatus.UNPUBLISHED
        self.tool_2.save(update_fields=["status"])
        other_tool.status = PanelStatus.PUBLISHED
        other_tool.save(update_fields=["status"])

        ToolFavorite.objects.create(tool_uid=self.tool_1.uid, username=self.test_user)
        ToolFavorite.objects.create(tool_uid=self.tool_2.uid, username=self.test_user)
        ToolFavorite.objects.create(tool_uid=other_tool.uid, username=self.test_user)

        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            scope_result = self._call_resource_with_request(ListToolTags, {"status": None})
            status_result = self._call_resource_with_request(ListToolTags, {"status": PanelStatus.PUBLISHED})

        scope_counts = {item["tag_id"]: item["tool_count"] for item in scope_result}
        status_counts = {item["tag_id"]: item["tool_count"] for item in status_result}
        self.assertEqual(scope_counts[ToolTagsEnum.FAVORITE_TOOLS.value], 2)
        self.assertEqual(status_counts[ToolTagsEnum.FAVORITE_TOOLS.value], 1)

    # ==================== 收藏状态在详情中的返回测试 ====================

    def test_get_tool_detail_with_favorite_status(self):
        """测试工具详情返回收藏状态"""

        # 收藏 tool_1
        ToolFavorite.objects.create(tool_uid=self.tool_1.uid, username=self.test_user)

        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            result = self._call_resource_with_request(GetToolDetail, {"uid": self.tool_1.uid})

        self.assertTrue(result["favorite"])

    @patch.object(Permission, "has_action_any_permission", return_value=True)
    def test_get_tool_detail_without_favorite(self, _mock_has_action_any_permission):
        """测试工具详情未收藏状态"""

        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            result = self._call_resource_with_request(GetToolDetail, {"uid": self.tool_1.uid})

        self.assertFalse(result["favorite"])

    # ==================== 删除工具时收藏级联清理测试 ====================

    def test_delete_tool_cascade_favorite(self):
        """测试删除工具时级联删除收藏记录"""
        # 创建收藏记录
        ToolFavorite.objects.create(tool_uid=self.tool_1.uid, username=self.test_user)
        ToolFavorite.objects.create(tool_uid=self.tool_1.uid, username=self.other_user)

        # 验证收藏记录存在
        self.assertEqual(ToolFavorite.objects.filter(tool_uid=self.tool_1.uid).count(), 2)

        # 删除工具
        DeleteTool()({"uid": self.tool_1.uid})

        # 验证收藏记录被删除
        self.assertEqual(ToolFavorite.objects.filter(tool_uid=self.tool_1.uid).count(), 0)

    # ==================== 工具版本更新后收藏状态测试 ====================

    def test_favorite_persists_after_tool_version_update(self):
        """测试工具版本更新后收藏状态仍然保留（核心场景：使用 tool_uid 而非 tool_id 关联）"""

        # 收藏 tool_1（版本1）
        ToolFavorite.objects.create(tool_uid=self.tool_1.uid, username=self.test_user)

        # 创建 tool_1 的新版本（版本2）
        tool_1_v2 = Tool.objects.create(
            uid=self.tool_1.uid,  # 相同的 uid
            version=2,  # 新版本
            name="Tool Alpha V2",
            namespace=self.namespace,
            tool_type=ToolTypeEnum.DATA_SEARCH.value,
            created_by=self.test_user,
            config=self.tool_1.config,
            is_deleted=False,
            description="Tool 1 Desc V2",
            updated_at=timezone.now(),
        )
        DataSearchToolConfig.objects.create(
            tool=tool_1_v2,
            data_search_config_type=DataSearchConfigTypeEnum.SQL,
            sql="select 1 v2",
        )

        # 验证新版本在列表中仍然显示为已收藏
        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            data = {"keyword": "", "page": 1, "page_size": 10}
            result = self._call_resource_with_request(ListTool, data)

        # 找到 tool_1（应该返回最新版本）
        tool_1_data = next((t for t in result if t["uid"] == self.tool_1.uid), None)
        self.assertIsNotNone(tool_1_data)
        self.assertEqual(tool_1_data["version"], 2)  # 确认是最新版本
        self.assertTrue(tool_1_data["favorite"])  # 收藏状态仍然保留

        # 验证详情也返回正确的收藏状态
        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            detail_result = self._call_resource_with_request(GetToolDetail, {"uid": self.tool_1.uid})

        self.assertEqual(detail_result["version"], 2)  # 确认是最新版本
        self.assertTrue(detail_result["favorite"])  # 收藏状态仍然保留

        # 验证通过收藏标签筛选也能找到新版本
        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            data = {"keyword": "", "tags": [int(ToolTagsEnum.FAVORITE_TOOLS.value)], "page": 1, "page_size": 10}
            favorite_result = self._call_resource_with_request(ListTool, data)

        self.assertEqual(len(favorite_result), 1)
        self.assertEqual(favorite_result[0]["uid"], self.tool_1.uid)
        self.assertEqual(favorite_result[0]["version"], 2)

    # ==================== ListToolAll 收藏状态测试 ====================

    def test_list_tool_all_with_favorite_status(self):
        """测试全量工具列表返回收藏状态"""

        # 收藏 tool_1
        ToolFavorite.objects.create(tool_uid=self.tool_1.uid, username=self.test_user)

        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            result = self._call_resource_with_request(ListToolAll, {})

        # 验证收藏状态
        tool_1_data = next((t for t in result if t["uid"] == self.tool_1.uid), None)
        tool_2_data = next((t for t in result if t["uid"] == self.tool_2.uid), None)

        self.assertIsNotNone(tool_1_data)
        self.assertIsNotNone(tool_2_data)
        self.assertTrue(tool_1_data["favorite"])
        self.assertFalse(tool_2_data["favorite"])
        self.assertEqual(tool_1_data["binding_type"], BindingType.PLATFORM_BINDING)
        self.assertEqual(tool_2_data["binding_type"], BindingType.SCENE_BINDING)

    def test_list_tool_all_filter_by_status(self):
        """测试全量工具列表支持按上架状态过滤"""

        self.tool_1.status = PanelStatus.PUBLISHED
        self.tool_1.save(update_fields=["status"])

        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            result = self._call_resource_with_request(ListToolAll, {"status": PanelStatus.PUBLISHED})

        self.assertEqual([tool["uid"] for tool in result], [self.tool_1.uid])
        self.assertEqual(result[0]["status"], PanelStatus.PUBLISHED)

    def test_list_tool_all_filters_by_scope_relation_without_permission(self):
        """全量工具列表按 scope 关联关系过滤，不依赖当前用户权限"""

        other_scene = Scene.objects.create(name="other-list-tool-all-scene")
        other_tool = Tool.objects.create(
            uid=str(uuid.uuid4()),
            version=1,
            name="Tool Gamma",
            namespace=self.namespace,
            tool_type=ToolTypeEnum.DATA_SEARCH.value,
            created_by=self.test_user,
            config=SQLDataSearchConfig(
                sql="select f3 from test_table_3",
                referenced_tables=[Table(table_name="test_table_3")],
                input_variable=[],
                output_fields=[SQLDataSearchOutputField(raw_name="field3", display_name="字段3")],
            ).model_dump(),
            is_deleted=False,
            description="Tool 3 Desc",
            updated_at=timezone.now(),
        )
        DataSearchToolConfig.objects.create(
            tool=other_tool,
            data_search_config_type=DataSearchConfigTypeEnum.SQL,
            sql="select 3",
        )
        other_scene_binding = ResourceBinding.objects.create(
            resource_type=ResourceVisibilityType.TOOL,
            resource_id=other_tool.uid,
            binding_type=BindingType.SCENE_BINDING,
        )
        ResourceBindingScene.objects.create(binding=other_scene_binding, scene_id=other_scene.scene_id)

        factory = APIRequestFactory()
        django_request = factory.post('/fake-url/', {}, format='json')
        drf_request = Request(django_request)

        with (
            patch("services.web.tool.resources.get_request_username", return_value=self.test_user),
            patch(
                "services.web.tool.resources.ScopePermission.get_scene_ids",
                side_effect=AssertionError("ListToolAll should not check scene permission"),
            ),
            patch(
                "services.web.tool.resources.ScopePermission.get_system_ids",
                side_effect=AssertionError("ListToolAll should not check system permission"),
            ),
        ):
            result = ListToolAll().request(
                {"scope_type": "scene", "scope_id": str(self.scene_id)},
                _request=drf_request,
            )

        tool_uids = {tool["uid"] for tool in result}
        self.assertIn(self.tool_1.uid, tool_uids)
        self.assertIn(self.tool_2.uid, tool_uids)
        self.assertNotIn(other_tool.uid, tool_uids)

    def test_list_tool_tags_filter_by_status(self):
        """测试工具标签统计支持按上架状态过滤"""

        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            result = self._call_resource_with_request(ListToolTags, {"status": PanelStatus.PUBLISHED})

        tag_counts = {item["tag_id"]: item["tool_count"] for item in result}
        self.assertEqual(tag_counts[ToolTagsEnum.ALL_TOOLS.value], 0)
        self.assertNotIn(str(self.tag1.tag_id), tag_counts)
