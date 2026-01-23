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
from unittest.mock import PropertyMock, patch

from bk_resource import Resource
from django.db.models import Q
from django.test import TestCase
from django.utils import timezone
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from api.bk_base.default import UserAuthBatchCheck
from apps.meta.models import Tag
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
from services.web.tool.permissions import ToolPermission
from services.web.tool.resources import (
    DeleteTool,
    FavoriteTool,
    GetToolDetail,
    ListTool,
    ListToolAll,
    ListToolTags,
)
from tests.test_tool.constants import MOCK_FETCH_TOOL_PERMISSION_TAGS_EMPTY


class ToolFavoriteTestCase(TestCase):
    """工具收藏功能测试"""

    def setUp(self):
        self.uid = str(uuid.uuid4())
        self.uid_2 = str(uuid.uuid4())
        self.namespace = "default_ns"
        self.test_user = "test_user"
        self.other_user = "other_user"

        # 创建测试工具 1
        self.tool_1 = Tool.objects.create(
            uid=self.uid,
            version=1,
            name="Tool Alpha",
            namespace=self.namespace,
            tool_type=ToolTypeEnum.DATA_SEARCH.value,
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

    def _call_resource_with_request(self, resource_cls: Type[Resource], data):
        factory = APIRequestFactory()
        django_request = factory.post('/fake-url/', data, format='json')
        drf_request = Request(django_request)

        resource = resource_cls()
        response = resource.request(data, _request=drf_request)
        return response.data.get("results", response.data)

    # ==================== 收藏/取消收藏测试 ====================

    def test_favorite_tool_add(self):
        """测试收藏工具"""
        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            result = FavoriteTool()({"uid": self.tool_1.uid, "favorite": True})

        self.assertEqual(result["favorite"], True)
        self.assertTrue(ToolFavorite.objects.filter(tool=self.tool_1, username=self.test_user).exists())

    def test_favorite_tool_remove(self):
        """测试取消收藏工具"""
        # 先创建收藏记录
        ToolFavorite.objects.create(tool=self.tool_1, username=self.test_user)

        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            result = FavoriteTool()({"uid": self.tool_1.uid, "favorite": False})

        self.assertEqual(result["favorite"], False)
        self.assertFalse(ToolFavorite.objects.filter(tool=self.tool_1, username=self.test_user).exists())

    def test_favorite_tool_idempotent_add(self):
        """测试重复收藏工具（幂等性）"""
        # 先创建收藏记录
        ToolFavorite.objects.create(tool=self.tool_1, username=self.test_user)

        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            result = FavoriteTool()({"uid": self.tool_1.uid, "favorite": True})

        self.assertEqual(result["favorite"], True)
        # 确保只有一条记录
        self.assertEqual(ToolFavorite.objects.filter(tool=self.tool_1, username=self.test_user).count(), 1)

    def test_favorite_tool_idempotent_remove(self):
        """测试重复取消收藏工具（幂等性）"""
        # 不创建收藏记录，直接取消收藏
        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            result = FavoriteTool()({"uid": self.tool_1.uid, "favorite": False})

        self.assertEqual(result["favorite"], False)
        self.assertFalse(ToolFavorite.objects.filter(tool=self.tool_1, username=self.test_user).exists())

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
        self.assertTrue(ToolFavorite.objects.filter(tool=self.tool_1, username=self.test_user).exists())
        self.assertTrue(ToolFavorite.objects.filter(tool=self.tool_1, username=self.other_user).exists())

        # 用户1取消收藏
        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            FavoriteTool()({"uid": self.tool_1.uid, "favorite": False})

        # 验证用户1的收藏被删除，用户2的收藏仍在
        self.assertFalse(ToolFavorite.objects.filter(tool=self.tool_1, username=self.test_user).exists())
        self.assertTrue(ToolFavorite.objects.filter(tool=self.tool_1, username=self.other_user).exists())

    # ==================== 收藏状态在列表中的返回测试 ====================

    @patch.object(ToolPermission, 'fetch_tool_permission_tags', return_value=MOCK_FETCH_TOOL_PERMISSION_TAGS_EMPTY)
    @patch.object(ToolPermission, 'authed_tool_filter', new_callable=PropertyMock)
    def test_list_tool_with_favorite_status(self, mock_authed_tool_filter, mock_fetch_tool_permission_tags):
        """测试工具列表返回收藏状态"""
        mock_authed_tool_filter.return_value = Q()

        # 收藏 tool_1
        ToolFavorite.objects.create(tool=self.tool_1, username=self.test_user)

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

    @patch.object(ToolPermission, 'fetch_tool_permission_tags', return_value=MOCK_FETCH_TOOL_PERMISSION_TAGS_EMPTY)
    @patch.object(ToolPermission, 'authed_tool_filter', new_callable=PropertyMock)
    def test_list_tool_favorite_first_ordering(self, mock_authed_tool_filter, mock_fetch_tool_permission_tags):
        """测试工具列表收藏优先排序"""
        mock_authed_tool_filter.return_value = Q()

        # 收藏 tool_2（名称为 Beta，按名称排序应该在后面）
        ToolFavorite.objects.create(tool=self.tool_2, username=self.test_user)

        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            data = {"keyword": "", "page": 1, "page_size": 10}
            result = self._call_resource_with_request(ListTool, data)

        # 验证收藏的工具排在前面
        self.assertEqual(result[0]["uid"], self.tool_2.uid)
        self.assertTrue(result[0]["favorite"])

    # ==================== 收藏筛选测试 ====================

    @patch.object(ToolPermission, 'fetch_tool_permission_tags', return_value=MOCK_FETCH_TOOL_PERMISSION_TAGS_EMPTY)
    @patch.object(ToolPermission, 'authed_tool_filter', new_callable=PropertyMock)
    def test_list_tool_filter_by_favorite_tag(self, mock_authed_tool_filter, mock_fetch_tool_permission_tags):
        """测试通过收藏虚拟标签筛选工具"""
        mock_authed_tool_filter.return_value = Q()

        # 收藏 tool_1
        ToolFavorite.objects.create(tool=self.tool_1, username=self.test_user)

        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            data = {"keyword": "", "tags": [int(ToolTagsEnum.FAVORITE_TOOLS.value)], "page": 1, "page_size": 10}
            result = self._call_resource_with_request(ListTool, data)

        # 验证只返回收藏的工具
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["uid"], self.tool_1.uid)

    @patch.object(ToolPermission, 'fetch_tool_permission_tags', return_value=MOCK_FETCH_TOOL_PERMISSION_TAGS_EMPTY)
    @patch.object(ToolPermission, 'authed_tool_filter', new_callable=PropertyMock)
    def test_list_tool_filter_by_favorite_tag_empty(self, mock_authed_tool_filter, mock_fetch_tool_permission_tags):
        """测试没有收藏时通过收藏虚拟标签筛选返回空"""
        mock_authed_tool_filter.return_value = Q()

        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            data = {"keyword": "", "tags": [int(ToolTagsEnum.FAVORITE_TOOLS.value)], "page": 1, "page_size": 10}
            result = self._call_resource_with_request(ListTool, data)

        # 验证返回空列表
        self.assertEqual(len(result), 0)

    # ==================== 收藏状态在详情中的返回测试 ====================

    @patch.object(ToolPermission, 'fetch_tool_permission_tags', return_value=MOCK_FETCH_TOOL_PERMISSION_TAGS_EMPTY)
    @patch.object(ToolPermission, 'authed_tool_filter', new_callable=PropertyMock)
    def test_get_tool_detail_with_favorite_status(self, mock_authed_tool_filter, mock_fetch_tool_permission_tags):
        """测试工具详情返回收藏状态"""
        mock_authed_tool_filter.return_value = Q()

        # 收藏 tool_1
        ToolFavorite.objects.create(tool=self.tool_1, username=self.test_user)

        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            result = GetToolDetail()({"uid": self.tool_1.uid})

        self.assertTrue(result["favorite"])

    @patch.object(ToolPermission, 'fetch_tool_permission_tags', return_value=MOCK_FETCH_TOOL_PERMISSION_TAGS_EMPTY)
    @patch.object(ToolPermission, 'authed_tool_filter', new_callable=PropertyMock)
    def test_get_tool_detail_without_favorite(self, mock_authed_tool_filter, mock_fetch_tool_permission_tags):
        """测试工具详情未收藏状态"""
        mock_authed_tool_filter.return_value = Q()

        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            result = GetToolDetail()({"uid": self.tool_1.uid})

        self.assertFalse(result["favorite"])

    # ==================== 收藏标签统计测试 ====================

    @patch.object(ToolPermission, 'authed_tool_filter', new_callable=PropertyMock)
    def test_list_tool_tags_favorite_count(self, mock_authed_tool_filter):
        """测试标签列表中收藏工具数量统计"""
        mock_authed_tool_filter.return_value = Q()

        # 收藏 tool_1
        ToolFavorite.objects.create(tool=self.tool_1, username=self.test_user)

        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            result = ListToolTags()({})

        # 查找收藏标签
        favorite_tag = next((t for t in result if t["tag_id"] == ToolTagsEnum.FAVORITE_TOOLS.value), None)
        self.assertIsNotNone(favorite_tag)
        self.assertEqual(favorite_tag["tool_count"], 1)

    @patch.object(ToolPermission, 'authed_tool_filter', new_callable=PropertyMock)
    def test_list_tool_tags_favorite_count_zero(self, mock_authed_tool_filter):
        """测试标签列表中没有收藏时数量为0"""
        mock_authed_tool_filter.return_value = Q()

        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            result = ListToolTags()({})

        # 查找收藏标签
        favorite_tag = next((t for t in result if t["tag_id"] == ToolTagsEnum.FAVORITE_TOOLS.value), None)
        self.assertIsNotNone(favorite_tag)
        self.assertEqual(favorite_tag["tool_count"], 0)

    # ==================== 删除工具时收藏级联清理测试 ====================

    def test_delete_tool_cascade_favorite(self):
        """测试删除工具时级联删除收藏记录"""
        # 创建收藏记录
        ToolFavorite.objects.create(tool=self.tool_1, username=self.test_user)
        ToolFavorite.objects.create(tool=self.tool_1, username=self.other_user)

        # 验证收藏记录存在
        self.assertEqual(ToolFavorite.objects.filter(tool__uid=self.tool_1.uid).count(), 2)

        # 删除工具
        DeleteTool()({"uid": self.tool_1.uid})

        # 验证收藏记录被删除
        self.assertEqual(ToolFavorite.objects.filter(tool__uid=self.tool_1.uid).count(), 0)

    # ==================== ListToolAll 收藏状态测试 ====================

    @patch.object(ToolPermission, 'fetch_tool_permission_tags', return_value=MOCK_FETCH_TOOL_PERMISSION_TAGS_EMPTY)
    @patch.object(ToolPermission, 'authed_tool_filter', new_callable=PropertyMock)
    def test_list_tool_all_with_favorite_status(self, mock_authed_tool_filter, mock_fetch_tool_permission_tags):
        """测试全量工具列表返回收藏状态"""
        mock_authed_tool_filter.return_value = Q()

        # 收藏 tool_1
        ToolFavorite.objects.create(tool=self.tool_1, username=self.test_user)

        with patch("services.web.tool.resources.get_request_username", return_value=self.test_user):
            result = ListToolAll()({})

        # 验证收藏状态
        tool_1_data = next((t for t in result if t["uid"] == self.tool_1.uid), None)
        tool_2_data = next((t for t in result if t["uid"] == self.tool_2.uid), None)

        self.assertIsNotNone(tool_1_data)
        self.assertIsNotNone(tool_2_data)
        self.assertTrue(tool_1_data["favorite"])
        self.assertFalse(tool_2_data["favorite"])
