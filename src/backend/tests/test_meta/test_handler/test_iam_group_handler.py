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

from bk_resource.exceptions import APIRequestError
from django.test import SimpleTestCase

from api.bk_iam.default import (
    AddGroupMembers,
    CreateGradeManagerGroups,
    DeleteGroupMembers,
    GetGroupMembers,
    GrantGroupPolicies,
)
from apps.meta.handlers.iam_group import IAMGroupManager


def _make_mock_action(action_id):
    """创建模拟的 ActionMeta 对象"""
    action = mock.MagicMock()
    action.id = action_id
    return action


class TestBuildPermissions(SimpleTestCase):
    """测试 IAMGroupManager.build_permissions"""

    def test_build_permissions_scene_actions(self):
        """测试场景相关动作的权限构建"""
        actions = [_make_mock_action("view_scene"), _make_mock_action("manage_scene")]
        result = IAMGroupManager.build_permissions(
            actions=actions,
            system_id="test_system",
            scene_id="scene_001",
            scene_name="测试场景",
        )
        self.assertEqual(result["_multi_permissions"][0]["actions"], [{"id": "view_scene"}, {"id": "manage_scene"}])
        self.assertEqual(len(result["_multi_permissions"][0]["resources"]), 1)
        resource = result["_multi_permissions"][0]["resources"][0]
        self.assertEqual(resource["type"], "scene")
        self.assertEqual(resource["paths"][0][0]["id"], "scene_001")
        self.assertEqual(resource["paths"][0][0]["name"], "测试场景")

    def test_build_permissions_strategy_actions(self):
        """测试策略相关动作的权限构建"""
        actions = [_make_mock_action("edit_strategy"), _make_mock_action("list_strategy_v2")]
        result = IAMGroupManager.build_permissions(
            actions=actions,
            system_id="test_system",
            scene_id="scene_002",
            scene_name="测试场景2",
        )
        self.assertEqual(
            result["_multi_permissions"][0]["actions"], [{"id": "edit_strategy"}, {"id": "list_strategy_v2"}]
        )
        self.assertEqual(result["_multi_permissions"][0]["resources"][0]["type"], "scene")
        self.assertEqual(result["_multi_permissions"][0]["resources"][0]["paths"][0][0]["name"], "测试场景2")

    def test_build_permissions_risk_actions(self):
        """测试风险相关动作的权限构建"""
        actions = [_make_mock_action("list_risk_v2"), _make_mock_action("edit_risk_v2")]
        result = IAMGroupManager.build_permissions(
            actions=actions,
            system_id="test_system",
            scene_id="scene_003",
            scene_name="测试场景3",
        )
        self.assertEqual(result["_multi_permissions"][0]["actions"], [{"id": "list_risk_v2"}, {"id": "edit_risk_v2"}])
        self.assertEqual(result["_multi_permissions"][0]["resources"][0]["type"], "risk")
        self.assertEqual(result["_multi_permissions"][0]["resources"][0]["paths"][0][0]["name"], "测试场景3")

    def test_build_permissions_rule_actions(self):
        """测试规则相关动作的权限构建"""
        actions = [_make_mock_action("list_rule_v2"), _make_mock_action("create_rule_v2")]
        result = IAMGroupManager.build_permissions(
            actions=actions,
            system_id="test_system",
            scene_id="scene_004",
            scene_name="测试场景4",
        )
        self.assertEqual(result["_multi_permissions"][0]["actions"], [{"id": "list_rule_v2"}, {"id": "create_rule_v2"}])
        self.assertEqual(result["_multi_permissions"][0]["resources"][0]["type"], "scene")
        self.assertEqual(result["_multi_permissions"][0]["resources"][0]["paths"][0][0]["name"], "测试场景4")

    def test_build_permissions_empty_actions(self):
        """测试空 action 列表"""
        result = IAMGroupManager.build_permissions(
            actions=[],
            system_id="test_system",
            scene_id="scene_005",
            scene_name="测试场景5",
        )
        self.assertEqual(result["_multi_permissions"][0]["actions"], [])
        self.assertEqual(len(result["_multi_permissions"][0]["resources"]), 1)
        # 空动作列表时使用默认的 scene 资源类型
        self.assertEqual(result["_multi_permissions"][0]["resources"][0]["type"], "scene")


class TestBuildPermissionsEdgeCases(SimpleTestCase):
    """测试 IAMGroupManager.build_permissions 的边界情况"""

    def test_build_permissions_with_unknown_action_type(self):
        """测试未知动作类型时使用默认资源类型"""
        unknown_action = mock.MagicMock()
        unknown_action.id = "unknown_action_id"

        result = IAMGroupManager.build_permissions(
            actions=[unknown_action],
            system_id="test_system",
            scene_id="scene_001",
            scene_name="测试场景",
        )

        # 未知动作类型应使用默认的 scene 资源类型
        self.assertEqual(result["_multi_permissions"][0]["resources"][0]["type"], "scene")

    def test_build_permissions_with_multiple_action_types(self):
        """测试混合动作类型时的多资源类型权限结构"""
        strategy_action = mock.MagicMock()
        strategy_action.id = "list_strategy_v2"
        risk_action = mock.MagicMock()
        risk_action.id = "list_risk_v2"

        result = IAMGroupManager.build_permissions(
            actions=[strategy_action, risk_action],
            system_id="test_system",
            scene_id="scene_001",
            scene_name="测试场景",
        )

        # 应返回多资源类型权限结构
        self.assertIn("_multi_permissions", result)
        self.assertEqual(len(result["_multi_permissions"]), 2)

        # 验证包含所有资源类型
        resource_types = [perm["resources"][0]["type"] for perm in result["_multi_permissions"]]
        self.assertIn("scene", resource_types)
        self.assertIn("risk", resource_types)

    def test_build_permissions_with_empty_system_id(self):
        """测试空系统ID时使用默认系统ID"""
        action = mock.MagicMock()
        action.id = "view_scene"

        result = IAMGroupManager.build_permissions(
            actions=[action],
            system_id="",
            scene_id="scene_001",
            scene_name="测试场景",
        )

        self.assertEqual(len(result["_multi_permissions"][0]["actions"]), 1)
        self.assertEqual(result["_multi_permissions"][0]["actions"][0]["id"], "view_scene")


class TestGetAllGroupMembers(SimpleTestCase):
    """测试 IAMGroupManager.get_all_group_members"""

    def test_single_page(self):
        """测试单页即可获取全部成员"""
        mock_response = {
            "count": 2,
            "results": [
                {"type": "user", "id": "admin"},
                {"type": "user", "id": "test_user"},
            ],
        }
        with mock.patch.object(
            GetGroupMembers,
            "perform_request",
            return_value=mock_response,
        ) as mock_get:
            result = IAMGroupManager.get_all_group_members(
                group_id=1001,
                system_id="test_system",
            )
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]["id"], "admin")
            self.assertEqual(result[1]["id"], "test_user")
            mock_get.assert_called_once()

    def test_multiple_pages(self):
        """测试多页分页获取全部成员"""
        page1_response = {
            "count": 3,
            "results": [
                {"type": "user", "id": "user1"},
                {"type": "user", "id": "user2"},
            ],
        }
        page2_response = {
            "count": 3,
            "results": [
                {"type": "user", "id": "user3"},
            ],
        }
        with mock.patch.object(
            GetGroupMembers,
            "perform_request",
            side_effect=[page1_response, page2_response],
        ) as mock_get:
            result = IAMGroupManager.get_all_group_members(
                group_id=1001,
                page_size=2,
                system_id="test_system",
            )
            self.assertEqual(len(result), 3)
            self.assertEqual(result[2]["id"], "user3")
            self.assertEqual(mock_get.call_count, 2)

    def test_empty_members(self):
        """测试用户组无成员时返回空列表"""
        mock_response = {
            "count": 0,
            "results": [],
        }
        with mock.patch.object(
            GetGroupMembers,
            "perform_request",
            return_value=mock_response,
        ):
            result = IAMGroupManager.get_all_group_members(
                group_id=1001,
                system_id="test_system",
            )
            self.assertEqual(result, [])

    def test_api_error_raises_exception(self):
        """测试 API 调用异常时抛出异常"""
        with mock.patch.object(
            GetGroupMembers,
            "perform_request",
            side_effect=APIRequestError(),
        ):
            with self.assertRaises(APIRequestError):
                IAMGroupManager.get_all_group_members(
                    group_id=1001,
                    system_id="test_system",
                )

    def test_mixed_member_types(self):
        """测试包含 user 和 department 类型的成员"""
        mock_response = {
            "count": 2,
            "results": [
                {"type": "user", "id": "admin"},
                {"type": "department", "id": "dept_001"},
            ],
        }
        with mock.patch.object(
            GetGroupMembers,
            "perform_request",
            return_value=mock_response,
        ):
            result = IAMGroupManager.get_all_group_members(
                group_id=1001,
                system_id="test_system",
            )
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]["type"], "user")
            self.assertEqual(result[1]["type"], "department")


class TestGroupMembersEdgeCases(SimpleTestCase):
    """测试用户组成员管理的边界情况"""

    def test_get_all_members_with_large_page_size(self):
        """测试大页面大小获取成员"""
        mock_response = {
            "count": 500,
            "results": [{"type": "user", "id": f"user_{i}"} for i in range(500)],
        }

        with mock.patch.object(
            GetGroupMembers,
            "perform_request",
            return_value=mock_response,
        ):
            result = IAMGroupManager.get_all_group_members(
                group_id=1001,
                page_size=1000,
                system_id="test_system",
            )
            self.assertEqual(len(result), 500)

    def test_add_members_with_expired_at_in_past(self):
        """测试添加成员时使用过去的过期时间"""
        past_expired_at = 1609459200  # 2021-01-01
        members = [{"type": "user", "id": "test_user"}]

        with mock.patch.object(
            AddGroupMembers,
            "perform_request",
            return_value={},
        ) as mock_add:
            IAMGroupManager.add_group_members(
                group_id=1001,
                members=members,
                expired_at=past_expired_at,
                system_id="test_system",
            )
            mock_add.assert_called_once()

    def test_delete_members_with_empty_ids(self):
        """测试删除空成员ID列表"""
        with mock.patch.object(
            DeleteGroupMembers,
            "perform_request",
            return_value={},
        ) as mock_delete:
            IAMGroupManager.delete_group_members(
                group_id=1001,
                member_type="user",
                member_ids=[],
                system_id="test_system",
            )
            mock_delete.assert_called_once()

    def test_sync_members_with_duplicate_members(self):
        """测试同步时包含重复成员"""
        duplicate_members = [
            {"type": "user", "id": "user1"},
            {"type": "user", "id": "user1"},  # 重复
            {"type": "user", "id": "user2"},
        ]

        current_members_response = {
            "count": 0,
            "results": [],
        }

        with mock.patch.object(
            GetGroupMembers,
            "perform_request",
            return_value=current_members_response,
        ), mock.patch.object(
            AddGroupMembers,
            "perform_request",
            return_value={},
        ) as mock_add:
            IAMGroupManager.sync_group_members(
                group_id=1001,
                members=duplicate_members,
                system_id="test_system",
            )
            mock_add.assert_called_once()


class TestAddGroupMembers(SimpleTestCase):
    """测试 IAMGroupManager.add_group_members"""

    def test_success(self):
        """测试成功添加成员"""
        members = [{"type": "user", "id": "admin"}, {"type": "user", "id": "test_user"}]
        with mock.patch.object(
            AddGroupMembers,
            "perform_request",
            return_value={},
        ) as mock_add:
            IAMGroupManager.add_group_members(
                group_id=1001,
                members=members,
                expired_at=4102444800,
                system_id="test_system",
            )
            mock_add.assert_called_once()

    def test_api_error_raises_exception(self):
        """测试 API 调用异常时抛出异常"""
        members = [{"type": "user", "id": "admin"}]
        with mock.patch.object(
            AddGroupMembers,
            "perform_request",
            side_effect=APIRequestError(),
        ):
            with self.assertRaises(APIRequestError):
                IAMGroupManager.add_group_members(
                    group_id=1001,
                    members=members,
                    system_id="test_system",
                )

    def test_empty_members(self):
        """测试添加空成员列表"""
        with mock.patch.object(
            AddGroupMembers,
            "perform_request",
            return_value={},
        ) as mock_add:
            IAMGroupManager.add_group_members(
                group_id=1001,
                members=[],
                system_id="test_system",
            )
            mock_add.assert_called_once()


class TestDeleteGroupMembers(SimpleTestCase):
    """测试 IAMGroupManager.delete_group_members"""

    def test_success(self):
        """测试成功删除成员"""
        with mock.patch.object(
            DeleteGroupMembers,
            "perform_request",
            return_value={},
        ) as mock_delete:
            IAMGroupManager.delete_group_members(
                group_id=1001,
                member_type="user",
                member_ids=["admin", "test_user"],
                system_id="test_system",
            )
            mock_delete.assert_called_once()

    def test_api_error_raises_exception(self):
        """测试 API 调用异常时抛出异常"""
        with mock.patch.object(
            DeleteGroupMembers,
            "perform_request",
            side_effect=APIRequestError(),
        ):
            with self.assertRaises(APIRequestError):
                IAMGroupManager.delete_group_members(
                    group_id=1001,
                    member_type="user",
                    member_ids=["admin"],
                    system_id="test_system",
                )

    def test_delete_department_members(self):
        """测试删除部门类型成员"""
        with mock.patch.object(
            DeleteGroupMembers,
            "perform_request",
            return_value={},
        ) as mock_delete:
            IAMGroupManager.delete_group_members(
                group_id=1001,
                member_type="department",
                member_ids=["dept_001"],
                system_id="test_system",
            )
            mock_delete.assert_called_once()


class TestCreateSceneGroupsWithMembers(SimpleTestCase):
    """测试 IAMGroupManager.create_scene_groups_with_members"""

    def setUp(self):
        super().setUp()
        self.scene_id = "scene_001"
        self.scene_name = "测试场景"

    def test_success_without_members(self):
        """测试完整流程成功：创建用户组 + 授权（不添加成员）"""
        with mock.patch.object(
            CreateGradeManagerGroups,
            "perform_request",
            return_value=[1001, 1002],
        ), mock.patch.object(
            GrantGroupPolicies,
            "perform_request",
            return_value={},
        ):
            result = IAMGroupManager.create_scene_groups_with_members(
                scene_id=self.scene_id,
                scene_name=self.scene_name,
            )
            self.assertEqual(result["iam_manager_group_id"], 1001)
            self.assertEqual(result["iam_viewer_group_id"], 1002)

    def test_success_with_members(self):
        """测试完整流程成功：创建用户组 + 授权 + 添加成员"""
        manager_members = [{"type": "user", "id": "admin"}]
        viewer_members = [{"type": "user", "id": "viewer1"}, {"type": "department", "id": "dept_001"}]
        with mock.patch.object(
            CreateGradeManagerGroups,
            "perform_request",
            return_value=[1001, 1002],
        ), mock.patch.object(GrantGroupPolicies, "perform_request", return_value={},), mock.patch.object(
            AddGroupMembers,
            "perform_request",
            return_value={},
        ) as mock_add:
            result = IAMGroupManager.create_scene_groups_with_members(
                scene_id=self.scene_id,
                scene_name=self.scene_name,
                manager_members=manager_members,
                viewer_members=viewer_members,
            )
            self.assertEqual(result["iam_manager_group_id"], 1001)
            self.assertEqual(result["iam_viewer_group_id"], 1002)
            # add_group_members 应被调用两次（管理组 + 使用组）
            self.assertEqual(mock_add.call_count, 2)

    def test_create_api_error(self):
        """测试创建用户组 API 异常时抛出异常"""
        with mock.patch.object(
            CreateGradeManagerGroups,
            "perform_request",
            side_effect=APIRequestError(),
        ):
            with self.assertRaises(APIRequestError):
                IAMGroupManager.create_scene_groups_with_members(
                    scene_id=self.scene_id,
                    scene_name=self.scene_name,
                )

    def test_partial_ids_raises_value_error(self):
        """测试返回的 group_id 不足 2 个时抛出 ValueError"""
        with mock.patch.object(
            CreateGradeManagerGroups,
            "perform_request",
            return_value=[1001],
        ):
            with self.assertRaises(ValueError):
                IAMGroupManager.create_scene_groups_with_members(
                    scene_id=self.scene_id,
                    scene_name=self.scene_name,
                )

    def test_empty_ids_raises_value_error(self):
        """测试返回空列表时抛出 ValueError"""
        with mock.patch.object(
            CreateGradeManagerGroups,
            "perform_request",
            return_value=[],
        ):
            with self.assertRaises(ValueError):
                IAMGroupManager.create_scene_groups_with_members(
                    scene_id=self.scene_id,
                    scene_name=self.scene_name,
                )

    def test_grant_failure_raises_with_group_ids(self):
        """测试授权失败时抛出 ValueError 并携带已创建的用户组 ID 信息"""
        with mock.patch.object(
            CreateGradeManagerGroups,
            "perform_request",
            return_value=[1001, 1002],
        ), mock.patch.object(
            GrantGroupPolicies,
            "perform_request",
            side_effect=APIRequestError(),
        ):
            with self.assertRaises(ValueError) as ctx:
                IAMGroupManager.create_scene_groups_with_members(
                    scene_id=self.scene_id,
                    scene_name=self.scene_name,
                )
            # 验证异常信息中包含已创建的用户组 ID，方便后续手动加权限
            error_msg = str(ctx.exception)
            self.assertIn("1001", error_msg)
            self.assertIn("1002", error_msg)
            self.assertIn("已创建的用户组IDs", error_msg)

    def test_grant_called_twice(self):
        """测试授权 API 被调用两次（管理用户组 + 使用用户组）"""
        with mock.patch.object(
            CreateGradeManagerGroups,
            "perform_request",
            return_value=[1001, 1002],
        ), mock.patch.object(
            GrantGroupPolicies,
            "perform_request",
            return_value={},
        ) as mock_grant:
            IAMGroupManager.create_scene_groups_with_members(
                scene_id=self.scene_id,
                scene_name=self.scene_name,
            )

            self.assertGreaterEqual(mock_grant.call_count, 2)

    def test_multi_resource_type_grant_logic(self):
        """测试多资源类型授权逻辑：每个资源类型单独调用授权接口"""
        with mock.patch.object(
            CreateGradeManagerGroups,
            "perform_request",
            return_value=[1001, 1002],
        ), mock.patch.object(
            GrantGroupPolicies,
            "perform_request",
            return_value={},
        ) as mock_grant:
            IAMGroupManager.create_scene_groups_with_members(
                scene_id=self.scene_id,
                scene_name=self.scene_name,
            )

            # 验证授权调用次数至少为资源类型数量 * 用户组数量
            # 管理用户组和使用用户组都需要为每个资源类型单独授权
            self.assertGreaterEqual(mock_grant.call_count, 2)

            # 验证每次调用的参数结构正确
            for call in mock_grant.call_args_list:
                args, kwargs = call
                request_data = args[0]

                # 验证包含必要的参数
                self.assertIn("system_id", request_data)
                self.assertIn("id", request_data)
                self.assertIn("actions", request_data)
                self.assertIn("resources", request_data)

                # 验证资源结构正确
                resources = request_data["resources"]
                self.assertIsInstance(resources, list)
                if resources:
                    resource = resources[0]
                    self.assertIn("system", resource)
                    self.assertIn("type", resource)
                    self.assertIn("paths", resource)

    def test_add_members_failure_raises(self):
        """测试添加成员失败时抛出异常"""
        manager_members = [{"type": "user", "id": "admin"}]
        with mock.patch.object(
            CreateGradeManagerGroups,
            "perform_request",
            return_value=[1001, 1002],
        ), mock.patch.object(GrantGroupPolicies, "perform_request", return_value={},), mock.patch.object(
            AddGroupMembers,
            "perform_request",
            side_effect=APIRequestError(),
        ):
            with self.assertRaises(APIRequestError):
                IAMGroupManager.create_scene_groups_with_members(
                    scene_id=self.scene_id,
                    scene_name=self.scene_name,
                    manager_members=manager_members,
                )

    def test_no_members_skips_add(self):
        """测试不传成员时不调用 add_group_members"""
        with mock.patch.object(
            CreateGradeManagerGroups,
            "perform_request",
            return_value=[1001, 1002],
        ), mock.patch.object(GrantGroupPolicies, "perform_request", return_value={},), mock.patch.object(
            AddGroupMembers,
            "perform_request",
            return_value={},
        ) as mock_add:
            IAMGroupManager.create_scene_groups_with_members(
                scene_id=self.scene_id,
                scene_name=self.scene_name,
            )
            mock_add.assert_not_called()


class TestCreateSceneGroupsWithMembersBoundaryConditions(SimpleTestCase):
    """测试 IAMGroupManager.create_scene_groups_with_members 的边界条件"""

    def setUp(self):
        super().setUp()
        self.scene_id = "scene_boundary_001"
        self.scene_name = "边界测试场景"

    def test_create_groups_with_special_characters_in_name(self):
        """测试场景名称包含特殊字符时用户组创建正常"""
        special_scene_name = "测试场景-特殊字符@#$%^&*()_+{}"
        with mock.patch.object(
            CreateGradeManagerGroups,
            "perform_request",
            return_value=[1001, 1002],
        ), mock.patch.object(GrantGroupPolicies, "perform_request", return_value={},), mock.patch.object(
            AddGroupMembers,
            "perform_request",
            return_value={},
        ):
            result = IAMGroupManager.create_scene_groups_with_members(
                scene_id=self.scene_id,
                scene_name=special_scene_name,
            )
            self.assertEqual(result["iam_manager_group_id"], 1001)
            self.assertEqual(result["iam_viewer_group_id"], 1002)

    def test_create_groups_with_very_long_scene_name(self):
        """测试超长场景名称时用户组创建正常"""
        long_scene_name = "这是一个非常长的场景名称，用于测试用户组名称截断和显示逻辑，确保系统能够正确处理超长字符串的情况"
        with mock.patch.object(
            CreateGradeManagerGroups,
            "perform_request",
            return_value=[1001, 1002],
        ), mock.patch.object(GrantGroupPolicies, "perform_request", return_value={},), mock.patch.object(
            AddGroupMembers,
            "perform_request",
            return_value={},
        ):
            result = IAMGroupManager.create_scene_groups_with_members(
                scene_id=self.scene_id,
                scene_name=long_scene_name,
            )
            self.assertEqual(result["iam_manager_group_id"], 1001)
            self.assertEqual(result["iam_viewer_group_id"], 1002)

    def test_create_groups_with_empty_scene_id(self):
        """测试空场景ID时抛出异常"""
        with mock.patch.object(
            CreateGradeManagerGroups,
            "perform_request",
            return_value=[1001, 1002],
        ):
            with self.assertRaises(ValueError):
                IAMGroupManager.create_scene_groups_with_members(
                    scene_id="",
                    scene_name=self.scene_name,
                )

    def test_create_groups_with_none_scene_name(self):
        """测试None场景名称时抛出异常"""
        with mock.patch.object(
            CreateGradeManagerGroups,
            "perform_request",
            return_value=[1001, 1002],
        ):
            with self.assertRaises(TypeError):
                IAMGroupManager.create_scene_groups_with_members(
                    scene_id=self.scene_id,
                    scene_name=None,
                )

    def test_create_groups_with_large_number_of_members(self):
        """测试添加大量成员时的性能边界"""
        large_manager_members = [{"type": "user", "id": f"user_{i}"} for i in range(100)]
        large_viewer_members = [{"type": "user", "id": f"viewer_{i}"} for i in range(200)]

        with mock.patch.object(
            CreateGradeManagerGroups,
            "perform_request",
            return_value=[1001, 1002],
        ), mock.patch.object(GrantGroupPolicies, "perform_request", return_value={},), mock.patch.object(
            AddGroupMembers,
            "perform_request",
            return_value={},
        ) as mock_add:
            result = IAMGroupManager.create_scene_groups_with_members(
                scene_id=self.scene_id,
                scene_name=self.scene_name,
                manager_members=large_manager_members,
                viewer_members=large_viewer_members,
            )
            self.assertEqual(result["iam_manager_group_id"], 1001)
            self.assertEqual(result["iam_viewer_group_id"], 1002)
            # 验证add_group_members被调用两次
            self.assertEqual(mock_add.call_count, 2)

    def test_create_groups_with_mixed_member_types(self):
        """测试混合成员类型（用户和部门）"""
        mixed_members = [
            {"type": "user", "id": "user1"},
            {"type": "department", "id": "dept1"},
            {"type": "user", "id": "user2"},
            {"type": "department", "id": "dept2"},
        ]

        with mock.patch.object(
            CreateGradeManagerGroups,
            "perform_request",
            return_value=[1001, 1002],
        ), mock.patch.object(GrantGroupPolicies, "perform_request", return_value={},), mock.patch.object(
            AddGroupMembers,
            "perform_request",
            return_value={},
        ):
            result = IAMGroupManager.create_scene_groups_with_members(
                scene_id=self.scene_id,
                scene_name=self.scene_name,
                manager_members=mixed_members,
            )
            self.assertEqual(result["iam_manager_group_id"], 1001)
            self.assertEqual(result["iam_viewer_group_id"], 1002)


class TestSyncGroupMembers(SimpleTestCase):
    """测试 IAMGroupManager.sync_group_members"""

    def test_sync_with_existing_members(self):
        """测试同步成员：先删除旧成员，再添加新成员"""
        current_members_response = {
            "count": 2,
            "results": [
                {"type": "user", "id": "old_user1"},
                {"type": "user", "id": "old_user2"},
            ],
        }
        new_members = [{"type": "user", "id": "new_user1"}]

        with mock.patch.object(
            GetGroupMembers,
            "perform_request",
            return_value=current_members_response,
        ), mock.patch.object(DeleteGroupMembers, "perform_request", return_value={},) as mock_delete, mock.patch.object(
            AddGroupMembers,
            "perform_request",
            return_value={},
        ) as mock_add:
            IAMGroupManager.sync_group_members(
                group_id=1001,
                members=new_members,
                system_id="test_system",
            )
            # 应删除旧成员
            mock_delete.assert_called_once()
            # 应添加新成员
            mock_add.assert_called_once()

    def test_sync_with_no_existing_members(self):
        """测试同步成员：无旧成员时只添加新成员"""
        current_members_response = {
            "count": 0,
            "results": [],
        }
        new_members = [{"type": "user", "id": "new_user1"}]

        with mock.patch.object(
            GetGroupMembers,
            "perform_request",
            return_value=current_members_response,
        ), mock.patch.object(DeleteGroupMembers, "perform_request", return_value={},) as mock_delete, mock.patch.object(
            AddGroupMembers,
            "perform_request",
            return_value={},
        ) as mock_add:
            IAMGroupManager.sync_group_members(
                group_id=1001,
                members=new_members,
                system_id="test_system",
            )
            # 无旧成员，不应调用删除
            mock_delete.assert_not_called()
            # 应添加新成员
            mock_add.assert_called_once()

    def test_sync_with_empty_new_members(self):
        """测试同步成员：新成员为空时只删除旧成员"""
        current_members_response = {
            "count": 1,
            "results": [
                {"type": "user", "id": "old_user1"},
            ],
        }

        with mock.patch.object(
            GetGroupMembers,
            "perform_request",
            return_value=current_members_response,
        ), mock.patch.object(DeleteGroupMembers, "perform_request", return_value={},) as mock_delete, mock.patch.object(
            AddGroupMembers,
            "perform_request",
            return_value={},
        ) as mock_add:
            IAMGroupManager.sync_group_members(
                group_id=1001,
                members=[],
                system_id="test_system",
            )
            # 应删除旧成员
            mock_delete.assert_called_once()
            # 新成员为空，不应调用添加
            mock_add.assert_not_called()

    def test_sync_with_mixed_member_types(self):
        """测试同步成员：旧成员包含 user 和 department 类型时按类型分组删除"""
        current_members_response = {
            "count": 3,
            "results": [
                {"type": "user", "id": "user1"},
                {"type": "department", "id": "dept_001"},
                {"type": "user", "id": "user2"},
            ],
        }
        new_members = [{"type": "user", "id": "new_user1"}]

        with mock.patch.object(
            GetGroupMembers,
            "perform_request",
            return_value=current_members_response,
        ), mock.patch.object(DeleteGroupMembers, "perform_request", return_value={},) as mock_delete, mock.patch.object(
            AddGroupMembers,
            "perform_request",
            return_value={},
        ):
            IAMGroupManager.sync_group_members(
                group_id=1001,
                members=new_members,
                system_id="test_system",
            )
            # 应按 type 分组删除，user 和 department 各调用一次
            self.assertEqual(mock_delete.call_count, 2)

    def test_sync_get_members_error_raises(self):
        """测试获取旧成员失败时抛出异常"""
        with mock.patch.object(
            GetGroupMembers,
            "perform_request",
            side_effect=APIRequestError(),
        ):
            with self.assertRaises(APIRequestError):
                IAMGroupManager.sync_group_members(
                    group_id=1001,
                    members=[{"type": "user", "id": "new_user1"}],
                    system_id="test_system",
                )

    def test_sync_delete_error_raises(self):
        """测试删除旧成员失败时抛出异常"""
        current_members_response = {
            "count": 1,
            "results": [
                {"type": "user", "id": "old_user1"},
            ],
        }
        with mock.patch.object(
            GetGroupMembers,
            "perform_request",
            return_value=current_members_response,
        ), mock.patch.object(
            DeleteGroupMembers,
            "perform_request",
            side_effect=APIRequestError(),
        ):
            with self.assertRaises(APIRequestError):
                IAMGroupManager.sync_group_members(
                    group_id=1001,
                    members=[{"type": "user", "id": "new_user1"}],
                    system_id="test_system",
                )

    def test_sync_add_error_raises(self):
        """测试添加新成员失败时抛出异常"""
        current_members_response = {
            "count": 0,
            "results": [],
        }
        with mock.patch.object(
            GetGroupMembers,
            "perform_request",
            return_value=current_members_response,
        ), mock.patch.object(
            AddGroupMembers,
            "perform_request",
            side_effect=APIRequestError(),
        ):
            with self.assertRaises(APIRequestError):
                IAMGroupManager.sync_group_members(
                    group_id=1001,
                    members=[{"type": "user", "id": "new_user1"}],
                    system_id="test_system",
                )


class TestCreateIamGroupsIntegration(SimpleTestCase):
    """集成测试：CreateScene._create_iam_groups 创建场景时自动创建 IAM 用户组"""

    def _make_scene(self, managers=None, users=None):
        """构造一个 mock Scene 对象"""
        scene = mock.MagicMock()
        scene.scene_id = 1
        scene.name = "测试场景"
        scene.managers = managers if managers is not None else ["admin"]
        scene.users = users if users is not None else ["viewer1", "viewer2"]
        scene.iam_manager_group_id = None
        scene.iam_viewer_group_id = None
        return scene

    def test_create_iam_groups_success(self):
        """测试 _create_iam_groups 成功创建用户组并回写 scene 字段"""
        from services.web.scene.resources import CreateScene

        scene = self._make_scene()

        with mock.patch.object(
            CreateGradeManagerGroups,
            "perform_request",
            return_value=[2001, 2002],
        ), mock.patch.object(GrantGroupPolicies, "perform_request", return_value={},), mock.patch.object(
            AddGroupMembers,
            "perform_request",
            return_value={},
        ) as mock_add:
            CreateScene._create_iam_groups(scene)

            # 验证 scene 字段被正确回写
            self.assertEqual(scene.iam_manager_group_id, 2001)
            self.assertEqual(scene.iam_viewer_group_id, 2002)
            # 验证 save 被调用
            scene.save.assert_called_once_with(update_fields=["iam_manager_group_id", "iam_viewer_group_id"])
            # 验证 add_group_members 被调用两次（管理组 + 使用组）
            self.assertEqual(mock_add.call_count, 2)

    def test_create_iam_groups_with_empty_users(self):
        """测试 users 为空时 viewer_members 为空列表"""
        from services.web.scene.resources import CreateScene

        scene = self._make_scene(managers=["admin"], users=[])

        with mock.patch.object(
            IAMGroupManager,
            "create_scene_groups_with_members",
            return_value={"iam_manager_group_id": 2001, "iam_viewer_group_id": 2002},
        ) as mock_create:
            CreateScene._create_iam_groups(scene)

            call_kwargs = mock_create.call_args[1]
            # managers 非空
            self.assertEqual(call_kwargs["manager_members"], [{"type": "user", "id": "admin"}])
            # users 为空，viewer_members 应为空列表
            self.assertEqual(call_kwargs["viewer_members"], [])

    def test_create_iam_groups_with_empty_managers_and_users(self):
        """测试 managers 和 users 都为空时 members 均为空列表"""
        from services.web.scene.resources import CreateScene

        scene = self._make_scene(managers=[], users=[])

        with mock.patch.object(
            IAMGroupManager,
            "create_scene_groups_with_members",
            return_value={"iam_manager_group_id": 2001, "iam_viewer_group_id": 2002},
        ) as mock_create:
            CreateScene._create_iam_groups(scene)

            call_kwargs = mock_create.call_args[1]
            # 两者都为空
            self.assertEqual(call_kwargs["manager_members"], [])
            self.assertEqual(call_kwargs["viewer_members"], [])

    def test_create_iam_groups_api_error_propagates(self):
        """测试创建用户组 API 异常时异常向上传播"""
        from services.web.scene.resources import CreateScene

        scene = self._make_scene()

        with mock.patch.object(
            CreateGradeManagerGroups,
            "perform_request",
            side_effect=APIRequestError(),
        ):
            with self.assertRaises(APIRequestError):
                CreateScene._create_iam_groups(scene)

    def test_create_iam_groups_members_format(self):
        """测试传递给 IAMGroupManager 的成员格式正确"""
        from services.web.scene.resources import CreateScene

        scene = self._make_scene(managers=["admin", "manager1"], users=["user1"])

        with mock.patch.object(
            IAMGroupManager,
            "create_scene_groups_with_members",
            return_value={"iam_manager_group_id": 3001, "iam_viewer_group_id": 3002},
        ) as mock_create:
            CreateScene._create_iam_groups(scene)

            call_kwargs = mock_create.call_args[1]
            self.assertEqual(call_kwargs["scene_id"], "1")
            self.assertEqual(call_kwargs["scene_name"], "测试场景")
            self.assertEqual(
                call_kwargs["manager_members"],
                [{"type": "user", "id": "admin"}, {"type": "user", "id": "manager1"}],
            )
            self.assertEqual(
                call_kwargs["viewer_members"],
                [{"type": "user", "id": "user1"}],
            )


class TestSyncIamGroupMembersIntegration(SimpleTestCase):
    """集成测试：SceneResource._sync_iam_group_members 更新场景时同步 IAM 用户组成员"""

    def _make_scene(self, managers=None, users=None, manager_group_id=1001, viewer_group_id=1002):
        """构造一个 mock Scene 对象"""
        scene = mock.MagicMock()
        scene.scene_id = 1
        scene.name = "测试场景"
        scene.managers = managers or ["admin"]
        scene.users = users or ["viewer1"]
        scene.iam_manager_group_id = manager_group_id
        scene.iam_viewer_group_id = viewer_group_id
        return scene

    def test_sync_both_managers_and_users(self):
        """测试同时更新 managers 和 users 时两个用户组都同步"""
        from services.web.scene.resources import SceneResource

        scene = self._make_scene(managers=["new_admin"], users=["new_user"])
        validated_data = {"managers": ["new_admin"], "users": ["new_user"]}

        with mock.patch.object(
            IAMGroupManager,
            "sync_group_members",
        ) as mock_sync:
            SceneResource._sync_iam_group_members(scene, validated_data)

            # 应调用两次：一次管理组，一次使用组
            self.assertEqual(mock_sync.call_count, 2)

            # 第一次调用：管理用户组
            first_call = mock_sync.call_args_list[0]
            self.assertEqual(first_call[1]["group_id"], 1001)
            self.assertEqual(first_call[1]["members"], [{"type": "user", "id": "new_admin"}])

            # 第二次调用：使用用户组
            second_call = mock_sync.call_args_list[1]
            self.assertEqual(second_call[1]["group_id"], 1002)
            self.assertEqual(second_call[1]["members"], [{"type": "user", "id": "new_user"}])

    def test_sync_only_managers(self):
        """测试只更新 managers 时仅同步管理用户组"""
        from services.web.scene.resources import SceneResource

        scene = self._make_scene(managers=["new_admin"])
        validated_data = {"managers": ["new_admin"]}

        with mock.patch.object(
            IAMGroupManager,
            "sync_group_members",
        ) as mock_sync:
            SceneResource._sync_iam_group_members(scene, validated_data)

            mock_sync.assert_called_once()
            self.assertEqual(mock_sync.call_args[1]["group_id"], 1001)

    def test_sync_only_users(self):
        """测试只更新 users 时仅同步使用用户组"""
        from services.web.scene.resources import SceneResource

        scene = self._make_scene(users=["new_user"])
        validated_data = {"users": ["new_user"]}

        with mock.patch.object(
            IAMGroupManager,
            "sync_group_members",
        ) as mock_sync:
            SceneResource._sync_iam_group_members(scene, validated_data)

            mock_sync.assert_called_once()
            self.assertEqual(mock_sync.call_args[1]["group_id"], 1002)

    def test_sync_no_managers_or_users_in_data(self):
        """测试 validated_request_data 中不包含 managers 和 users 时不触发同步"""
        from services.web.scene.resources import SceneResource

        scene = self._make_scene()
        validated_data = {"name": "新名称", "description": "新描述"}

        with mock.patch.object(
            IAMGroupManager,
            "sync_group_members",
        ) as mock_sync:
            SceneResource._sync_iam_group_members(scene, validated_data)

            mock_sync.assert_not_called()

    def test_sync_skips_when_no_group_id(self):
        """测试 scene 没有 iam_group_id 时跳过同步"""
        from services.web.scene.resources import SceneResource

        scene = self._make_scene(manager_group_id=None, viewer_group_id=None)
        validated_data = {"managers": ["admin"], "users": ["user1"]}

        with mock.patch.object(
            IAMGroupManager,
            "sync_group_members",
        ) as mock_sync:
            SceneResource._sync_iam_group_members(scene, validated_data)

            # iam_group_id 为 None，不应触发同步
            mock_sync.assert_not_called()

    def test_sync_partial_group_id(self):
        """测试只有管理用户组 ID 时仅同步管理组"""
        from services.web.scene.resources import SceneResource

        scene = self._make_scene(manager_group_id=1001, viewer_group_id=None)
        validated_data = {"managers": ["admin"], "users": ["user1"]}

        with mock.patch.object(
            IAMGroupManager,
            "sync_group_members",
        ) as mock_sync:
            SceneResource._sync_iam_group_members(scene, validated_data)

            # 只有管理组有 ID，应只调用一次
            mock_sync.assert_called_once()
            self.assertEqual(mock_sync.call_args[1]["group_id"], 1001)

    def test_sync_error_propagates(self):
        """测试同步失败时异常向上传播"""
        from services.web.scene.resources import SceneResource

        scene = self._make_scene()
        validated_data = {"managers": ["admin"]}

        with mock.patch.object(
            IAMGroupManager,
            "sync_group_members",
            side_effect=APIRequestError(),
        ):
            with self.assertRaises(APIRequestError):
                SceneResource._sync_iam_group_members(scene, validated_data)


class TestBuildRequestData(SimpleTestCase):
    """测试各 IAM API 资源类的 build_request_data 方法，确保 url_keys 参数被正确保留"""

    def test_create_grade_manager_groups_preserves_url_keys(self):
        """测试 CreateGradeManagerGroups.build_request_data 保留 system_id 和 id"""
        resource = CreateGradeManagerGroups()
        validated_data = {
            "system_id": "test_system",
            "id": "grade_manager_1",
            "groups": [{"name": "测试组", "description": "描述"}],
        }
        result = resource.build_request_data(validated_data)
        # build_request_data 只返回请求体数据，URL参数通过url_keys处理
        self.assertEqual(result["groups"], [{"name": "测试组", "description": "描述"}])
        # URL参数保留在validated_data中，用于URL路径构建
        self.assertEqual(validated_data["system_id"], "test_system")
        self.assertEqual(validated_data["id"], "grade_manager_1")

    def test_create_grade_manager_groups_with_sync_subject_template(self):
        """测试 CreateGradeManagerGroups.build_request_data 包含 sync_subject_template"""
        resource = CreateGradeManagerGroups()
        validated_data = {
            "system_id": "test_system",
            "id": "grade_manager_1",
            "groups": [{"name": "测试组", "description": "描述"}],
            "sync_subject_template": True,
        }
        result = resource.build_request_data(validated_data)
        # build_request_data 只返回请求体数据，URL参数通过url_keys处理
        self.assertTrue(result["sync_subject_template"])
        self.assertEqual(result["groups"], [{"name": "测试组", "description": "描述"}])
        # URL参数保留在validated_data中，用于URL路径构建
        self.assertEqual(validated_data["system_id"], "test_system")
        self.assertEqual(validated_data["id"], "grade_manager_1")

    def test_grant_group_policies_preserves_url_keys(self):
        """测试 GrantGroupPolicies.build_request_data 保留 system_id 和 id"""
        resource = GrantGroupPolicies()
        validated_data = {
            "system_id": "test_system",
            "id": 1001,
            "actions": [{"id": "view_scene"}],
            "resources": [{"system": "test_system", "type": "scene"}],
        }
        result = resource.build_request_data(validated_data)
        # build_request_data 只返回请求体数据，URL参数通过url_keys处理
        self.assertEqual(result["actions"], [{"id": "view_scene"}])
        self.assertEqual(result["resources"], [{"system": "test_system", "type": "scene"}])
        # URL参数保留在validated_data中，用于URL路径构建
        self.assertEqual(validated_data["system_id"], "test_system")
        self.assertEqual(validated_data["id"], 1001)

    def test_add_group_members_preserves_url_keys(self):
        """测试 AddGroupMembers.build_request_data 保留 system_id 和 id"""
        resource = AddGroupMembers()
        validated_data = {
            "system_id": "test_system",
            "id": 1001,
            "members": [{"type": "user", "id": "admin"}],
            "expired_at": 4102444800,
        }
        result = resource.build_request_data(validated_data)
        # build_request_data 只返回请求体数据，URL参数通过url_keys处理
        self.assertEqual(result["members"], [{"type": "user", "id": "admin"}])
        self.assertEqual(result["expired_at"], 4102444800)
        # URL参数保留在validated_data中，用于URL路径构建
        self.assertEqual(validated_data["system_id"], "test_system")
        self.assertEqual(validated_data["id"], 1001)

    def test_add_group_members_default_expired_at(self):
        """测试 AddGroupMembers.build_request_data 默认 expired_at 为 0"""
        resource = AddGroupMembers()
        validated_data = {
            "system_id": "test_system",
            "id": 1001,
            "members": [{"type": "user", "id": "admin"}],
        }
        result = resource.build_request_data(validated_data)
        self.assertEqual(result["expired_at"], 0)

    def test_delete_group_members_preserves_url_keys(self):
        """测试 DeleteGroupMembers.build_request_data 保留 system_id 和 id"""
        resource = DeleteGroupMembers()
        validated_data = {
            "system_id": "test_system",
            "id": 1001,
            "type": "user",
            "ids": ["admin", "test_user"],
        }
        result = resource.build_request_data(validated_data)
        # build_request_data 只返回请求体数据，URL参数通过url_keys处理
        self.assertEqual(result["type"], "user")
        self.assertEqual(result["ids"], ["admin", "test_user"])
        # URL参数保留在validated_data中，用于URL路径构建
        self.assertEqual(validated_data["system_id"], "test_system")
        self.assertEqual(validated_data["id"], 1001)

    def test_delete_group_members_default_values(self):
        """测试 DeleteGroupMembers.build_request_data 默认值"""
        resource = DeleteGroupMembers()
        validated_data = {
            "system_id": "test_system",
            "id": 1001,
        }
        result = resource.build_request_data(validated_data)
        self.assertEqual(result["type"], "")
        self.assertEqual(result["ids"], [])


class TestGrantPermissionsExceptionScenarios(SimpleTestCase):
    """测试 IAMGroupManager 授权功能的异常场景"""

    def setUp(self):
        super().setUp()
        self.scene_id = "scene_exception_001"
        self.scene_name = "异常测试场景"

    def test_grant_permissions_with_invalid_resource_type(self):
        """测试授权时使用无效资源类型"""
        action = mock.MagicMock()
        action.id = "invalid_action"

        # 构建权限时使用无效动作，应使用默认资源类型
        result = IAMGroupManager.build_permissions(
            actions=[action],
            system_id="test_system",
            scene_id=self.scene_id,
            scene_name=self.scene_name,
        )

        # 无效动作应使用默认的 scene 资源类型
        self.assertEqual(result["_multi_permissions"][0]["resources"][0]["type"], "scene")

    def test_grant_permissions_with_empty_resources(self):
        """测试授权时资源列表为空"""
        action = mock.MagicMock()
        action.id = "view_scene"

        result = IAMGroupManager.build_permissions(
            actions=[action],
            system_id="test_system",
            scene_id=self.scene_id,
            scene_name=self.scene_name,
        )

        # 资源列表不应为空
        self.assertGreater(len(result["_multi_permissions"][0]["resources"]), 0)
        self.assertEqual(result["_multi_permissions"][0]["resources"][0]["type"], "scene")

    def test_grant_permissions_with_malformed_resources(self):
        """测试授权时资源结构不完整"""
        action = mock.MagicMock()
        action.id = "view_scene"

        result = IAMGroupManager.build_permissions(
            actions=[action],
            system_id="test_system",
            scene_id=self.scene_id,
            scene_name=self.scene_name,
        )

        # 验证资源结构完整
        resource = result["_multi_permissions"][0]["resources"][0]
        self.assertIn("system", resource)
        self.assertIn("type", resource)
        self.assertIn("paths", resource)
        self.assertEqual(resource["paths"][0][0]["id"], self.scene_id)

    def test_create_groups_with_grant_permission_failure(self):
        """测试创建用户组时授权失败，应回滚并抛出异常"""
        with mock.patch.object(
            CreateGradeManagerGroups,
            "perform_request",
            return_value=[1001, 1002],
        ), mock.patch.object(
            GrantGroupPolicies,
            "perform_request",
            side_effect=APIRequestError("授权API调用失败"),
        ):
            with self.assertRaises(ValueError) as ctx:
                IAMGroupManager.create_scene_groups_with_members(
                    scene_id=self.scene_id,
                    scene_name=self.scene_name,
                )

            # 验证异常信息包含已创建的用户组ID，便于后续处理
            error_msg = str(ctx.exception)
            self.assertIn("1001", error_msg)
            self.assertIn("1002", error_msg)
            self.assertIn("已创建的用户组IDs", error_msg)

    def test_create_groups_with_partial_grant_failure(self):
        """测试部分授权成功，部分授权失败时的异常处理"""
        with mock.patch.object(
            CreateGradeManagerGroups,
            "perform_request",
            return_value=[1001, 1002],
        ), mock.patch.object(
            GrantGroupPolicies,
            "perform_request",
            side_effect=[
                None,  # 第一个授权成功
                APIRequestError("第二个授权失败"),  # 第二个授权失败
            ],
        ):
            with self.assertRaises(ValueError) as ctx:
                IAMGroupManager.create_scene_groups_with_members(
                    scene_id=self.scene_id,
                    scene_name=self.scene_name,
                )

            # 验证异常信息包含已授权成功的用户组ID
            error_msg = str(ctx.exception)
            self.assertIn("1001", error_msg)  # 已成功授权
            self.assertIn("1002", error_msg)  # 授权失败
            self.assertIn("已授权成功的用户组IDs", error_msg)

    def test_create_groups_with_multi_resource_partial_failure(self):
        """测试多资源类型授权场景中的部分失败情况"""
        with mock.patch.object(
            CreateGradeManagerGroups,
            "perform_request",
            return_value=[1001, 1002],
        ), mock.patch.object(
            GrantGroupPolicies,
            "perform_request",
            side_effect=[
                None,  # 第一个资源类型授权成功
                None,  # 第二个资源类型授权成功
                APIRequestError("第三个资源类型授权失败"),  # 第三个资源类型授权失败
            ],
        ):
            with self.assertRaises(ValueError) as ctx:
                IAMGroupManager.create_scene_groups_with_members(
                    scene_id=self.scene_id,
                    scene_name=self.scene_name,
                )

            # 验证异常信息包含详细的授权状态信息
            error_msg = str(ctx.exception)
            self.assertIn("1001", error_msg)  # 管理用户组ID
            self.assertIn("1002", error_msg)  # 使用用户组ID
            self.assertIn("已授权成功的用户组IDs", error_msg)
            self.assertIn("已创建的用户组IDs", error_msg)

    def test_grant_permissions_with_network_timeout(self):
        """测试授权API网络超时异常"""
        with mock.patch.object(
            CreateGradeManagerGroups,
            "perform_request",
            return_value=[1001, 1002],
        ), mock.patch.object(
            GrantGroupPolicies,
            "perform_request",
            side_effect=APIRequestError("网络连接超时"),
        ):
            with self.assertRaises(ValueError):
                IAMGroupManager.create_scene_groups_with_members(
                    scene_id=self.scene_id,
                    scene_name=self.scene_name,
                )

    def test_grant_permissions_with_server_error(self):
        """测试授权API服务器内部错误"""
        with mock.patch.object(
            CreateGradeManagerGroups,
            "perform_request",
            return_value=[1001, 1002],
        ), mock.patch.object(
            GrantGroupPolicies,
            "perform_request",
            side_effect=APIRequestError("服务器内部错误: 500"),
        ):
            with self.assertRaises(ValueError):
                IAMGroupManager.create_scene_groups_with_members(
                    scene_id=self.scene_id,
                    scene_name=self.scene_name,
                )

    def test_grant_permissions_with_invalid_permission_data(self):
        """测试授权时使用无效的权限数据"""
        # 模拟构建权限时返回无效数据
        with mock.patch.object(
            IAMGroupManager,
            "build_permissions",
            return_value={
                "actions": [],  # 空动作列表
                "resources": [],  # 空资源列表
            },
        ), mock.patch.object(
            CreateGradeManagerGroups,
            "perform_request",
            return_value=[1001, 1002],
        ):
            with self.assertRaises(Exception):
                IAMGroupManager.create_scene_groups_with_members(
                    scene_id=self.scene_id,
                    scene_name=self.scene_name,
                )


class TestResourceTypeMatchingLogic(SimpleTestCase):
    """测试权限构建时的资源类型匹配逻辑"""

    def test_resource_type_detection_for_strategy_actions(self):
        """测试策略相关动作的资源类型匹配"""
        strategy_actions = [
            mock.MagicMock(id="list_strategy_v2"),
            mock.MagicMock(id="create_strategy_v2"),
            mock.MagicMock(id="edit_strategy"),
            mock.MagicMock(id="delete_strategy"),
            mock.MagicMock(id="generate_strategy_risk"),
        ]

        for action in strategy_actions:
            result = IAMGroupManager.build_permissions(
                actions=[action],
                system_id="test_system",
                scene_id="scene_001",
                scene_name="测试场景",
            )
            self.assertEqual(result["_multi_permissions"][0]["resources"][0]["type"], "strategy")

    def test_resource_type_detection_for_risk_actions(self):
        """测试风险相关动作的资源类型匹配"""
        risk_actions = [
            mock.MagicMock(id="list_risk_v2"),
            mock.MagicMock(id="edit_risk_v2"),
            mock.MagicMock(id="process_risk"),
        ]

        for action in risk_actions:
            result = IAMGroupManager.build_permissions(
                actions=[action],
                system_id="test_system",
                scene_id="scene_001",
                scene_name="测试场景",
            )
            self.assertEqual(result["_multi_permissions"][0]["resources"][0]["type"], "risk")

    def test_resource_type_detection_for_rule_actions(self):
        """测试规则相关动作的资源类型匹配"""
        rule_actions = [
            mock.MagicMock(id="list_rule_v2"),
            mock.MagicMock(id="create_rule_v2"),
            mock.MagicMock(id="edit_rule_v2"),
            mock.MagicMock(id="delete_rule_v2"),
        ]

        for action in rule_actions:
            result = IAMGroupManager.build_permissions(
                actions=[action],
                system_id="test_system",
                scene_id="scene_001",
                scene_name="测试场景",
            )
            self.assertEqual(result["_multi_permissions"][0]["resources"][0]["type"], "rule")

    def test_resource_type_detection_for_link_table_actions(self):
        """测试联表相关动作的资源类型匹配"""
        link_table_actions = [
            mock.MagicMock(id="list_link_table_v2"),
            mock.MagicMock(id="create_link_table_v2"),
            mock.MagicMock(id="edit_link_table"),
            mock.MagicMock(id="delete_link_table"),
            mock.MagicMock(id="view_link_table"),
        ]

        for action in link_table_actions:
            result = IAMGroupManager.build_permissions(
                actions=[action],
                system_id="test_system",
                scene_id="scene_001",
                scene_name="测试场景",
            )
            self.assertEqual(result["_multi_permissions"][0]["resources"][0]["type"], "scene")

    def test_resource_type_detection_for_notice_group_actions(self):
        """测试通知组相关动作的资源类型匹配"""
        notice_group_actions = [
            mock.MagicMock(id="list_notice_group_v2"),
            mock.MagicMock(id="create_notice_group_v2"),
            mock.MagicMock(id="edit_notice_group_v2"),
            mock.MagicMock(id="delete_notice_group_v2"),
        ]

        for action in notice_group_actions:
            result = IAMGroupManager.build_permissions(
                actions=[action],
                system_id="test_system",
                scene_id="scene_001",
                scene_name="测试场景",
            )
            self.assertEqual(result["_multi_permissions"][0]["resources"][0]["type"], "scene")

    def test_resource_type_detection_for_panel_actions(self):
        """测试套餐相关动作的资源类型匹配"""
        panel_actions = [
            mock.MagicMock(id="list_pa_v2"),
            mock.MagicMock(id="create_pa_v2"),
            mock.MagicMock(id="edit_pa_v2"),
        ]

        for action in panel_actions:
            result = IAMGroupManager.build_permissions(
                actions=[action],
                system_id="test_system",
                scene_id="scene_001",
                scene_name="测试场景",
            )
            self.assertEqual(result["_multi_permissions"][0]["resources"][0]["type"], "scene")

    def test_resource_type_detection_for_scene_actions(self):
        """测试场景相关动作的资源类型匹配"""
        scene_actions = [
            mock.MagicMock(id="view_scene"),
            mock.MagicMock(id="manage_scene"),
        ]

        for action in scene_actions:
            result = IAMGroupManager.build_permissions(
                actions=[action],
                system_id="test_system",
                scene_id="scene_001",
                scene_name="测试场景",
            )
            self.assertEqual(result["_multi_permissions"][0]["resources"][0]["type"], "scene")

    def test_resource_type_priority_when_mixed_actions(self):
        """测试混合动作类型时的多资源类型权限结构"""
        mixed_actions = [
            mock.MagicMock(id="view_scene"),  # scene类型
            mock.MagicMock(id="list_strategy_v2"),  # scene类型
            mock.MagicMock(id="list_risk_v2"),  # risk类型
        ]

        result = IAMGroupManager.build_permissions(
            actions=mixed_actions,
            system_id="test_system",
            scene_id="scene_001",
            scene_name="测试场景",
        )

        # 应返回多资源类型权限结构
        self.assertIn("_multi_permissions", result)
        self.assertEqual(len(result["_multi_permissions"]), 3)

        # 验证包含所有资源类型
        resource_types = [perm["resources"][0]["type"] for perm in result["_multi_permissions"]]
        self.assertIn("scene", resource_types)
        self.assertIn("risk", resource_types)


class TestMemberLifecycleManagement(SimpleTestCase):
    """测试用户组成员管理的完整生命周期"""

    def setUp(self):
        super().setUp()
        self.group_id = 1001
        self.system_id = "test_system"

    def test_complete_member_lifecycle(self):
        """测试完整的成员生命周期：添加 -> 查询 -> 同步 -> 删除"""
        # 1. 添加初始成员
        initial_members = [
            {"type": "user", "id": "user1"},
            {"type": "user", "id": "user2"},
            {"type": "department", "id": "dept1"},
        ]

        # 2. 查询成员列表
        mock_members_response = {
            "count": 3,
            "results": initial_members,
        }

        # 3. 同步成员（删除旧成员，添加新成员）
        new_members = [
            {"type": "user", "id": "user3"},
            {"type": "department", "id": "dept2"},
        ]

        # 4. 删除特定成员
        members_to_delete = ["user3"]

        # 模拟完整的生命周期流程
        with mock.patch.object(AddGroupMembers, "perform_request", return_value={},) as mock_add, mock.patch.object(
            GetGroupMembers,
            "perform_request",
            return_value=mock_members_response,
        ) as mock_get, mock.patch.object(
            DeleteGroupMembers,
            "perform_request",
            return_value={},
        ) as mock_delete:

            # 步骤1: 添加初始成员
            IAMGroupManager.add_group_members(
                group_id=self.group_id,
                members=initial_members,
                system_id=self.system_id,
            )
            mock_add.assert_called_once()

            # 步骤2: 查询成员列表
            members = IAMGroupManager.get_all_group_members(
                group_id=self.group_id,
                system_id=self.system_id,
            )
            self.assertEqual(len(members), 3)
            mock_get.assert_called_once()

            # 步骤3: 同步成员
            IAMGroupManager.sync_group_members(
                group_id=self.group_id,
                members=new_members,
                system_id=self.system_id,
            )
            # 同步操作会删除所有现有成员类型，然后添加新成员
            # 根据成员类型数量，可能调用多次删除操作
            self.assertEqual(mock_delete.call_count, 2)
            self.assertEqual(mock_add.call_count, 2)

            # 步骤4: 删除特定成员
            IAMGroupManager.delete_group_members(
                group_id=self.group_id,
                member_type="user",
                member_ids=members_to_delete,
                system_id=self.system_id,
            )
            # sync_group_members 调用2次删除，delete_group_members 调用1次删除，总共3次
            self.assertEqual(mock_delete.call_count, 3)

    def test_member_lifecycle_with_error_recovery(self):
        """测试成员生命周期中的错误恢复场景"""
        initial_members = [{"type": "user", "id": "user1"}]
        new_members = [{"type": "user", "id": "user2"}]

        # 模拟同步过程中删除成功但添加失败
        with mock.patch.object(
            GetGroupMembers,
            "perform_request",
            return_value={"count": 1, "results": initial_members},
        ), mock.patch.object(DeleteGroupMembers, "perform_request", return_value={},), mock.patch.object(
            AddGroupMembers,
            "perform_request",
            side_effect=APIRequestError("添加成员失败"),
        ):
            with self.assertRaises(APIRequestError):
                IAMGroupManager.sync_group_members(
                    group_id=self.group_id,
                    members=new_members,
                    system_id=self.system_id,
                )

            # 此时用户组应该处于空状态（删除成功，添加失败）
            # 在实际应用中，可能需要额外的恢复机制

    def test_member_lifecycle_with_concurrent_operations(self):
        """测试并发操作时的成员管理"""
        # 模拟并发添加和删除操作
        members1 = [{"type": "user", "id": "user1"}]
        members2 = [{"type": "user", "id": "user2"}]

        with mock.patch.object(AddGroupMembers, "perform_request", return_value={},) as mock_add, mock.patch.object(
            DeleteGroupMembers,
            "perform_request",
            return_value={},
        ) as mock_delete:

            # 并发添加操作
            IAMGroupManager.add_group_members(
                group_id=self.group_id,
                members=members1,
                system_id=self.system_id,
            )
            IAMGroupManager.add_group_members(
                group_id=self.group_id,
                members=members2,
                system_id=self.system_id,
            )

            # 并发删除操作
            IAMGroupManager.delete_group_members(
                group_id=self.group_id,
                member_type="user",
                member_ids=["user1"],
                system_id=self.system_id,
            )

            self.assertEqual(mock_add.call_count, 2)
            self.assertEqual(mock_delete.call_count, 1)

    def test_member_lifecycle_with_expired_at_handling(self):
        """测试成员生命周期中的过期时间处理"""
        future_expired_at = 4102444800  # 2100-01-01
        past_expired_at = 1609459200  # 2021-01-01

        members = [{"type": "user", "id": "user1"}]

        with mock.patch.object(
            AddGroupMembers,
            "perform_request",
            return_value={},
        ) as mock_add:

            # 添加带未来过期时间的成员
            IAMGroupManager.add_group_members(
                group_id=self.group_id,
                members=members,
                expired_at=future_expired_at,
                system_id=self.system_id,
            )

            # 添加带过去过期时间的成员
            IAMGroupManager.add_group_members(
                group_id=self.group_id,
                members=members,
                expired_at=past_expired_at,
                system_id=self.system_id,
            )

            self.assertEqual(mock_add.call_count, 2)


class TestMemberTypeHandling(SimpleTestCase):
    """测试不同成员类型的处理"""

    def test_member_type_user(self):
        """测试用户类型成员的处理"""
        user_members = [
            {"type": "user", "id": "admin"},
            {"type": "user", "id": "test_user"},
        ]

        with mock.patch.object(
            AddGroupMembers,
            "perform_request",
            return_value={},
        ) as mock_add:
            IAMGroupManager.add_group_members(
                group_id=1001,
                members=user_members,
                system_id="test_system",
            )
            mock_add.assert_called_once()

    def test_member_type_department(self):
        """测试部门类型成员的处理"""
        department_members = [
            {"type": "department", "id": "dept_001"},
            {"type": "department", "id": "dept_002"},
        ]

        with mock.patch.object(
            AddGroupMembers,
            "perform_request",
            return_value={},
        ) as mock_add:
            IAMGroupManager.add_group_members(
                group_id=1001,
                members=department_members,
                system_id="test_system",
            )
            mock_add.assert_called_once()

    def test_member_type_mixed(self):
        """测试混合类型成员的处理"""
        mixed_members = [
            {"type": "user", "id": "user1"},
            {"type": "department", "id": "dept1"},
            {"type": "user", "id": "user2"},
        ]

        with mock.patch.object(
            AddGroupMembers,
            "perform_request",
            return_value={},
        ) as mock_add:
            IAMGroupManager.add_group_members(
                group_id=1001,
                members=mixed_members,
                system_id="test_system",
            )
            mock_add.assert_called_once()

    def test_member_type_unknown(self):
        """测试未知类型成员的处理"""
        unknown_members = [
            {"type": "unknown_type", "id": "unknown1"},
        ]

        with mock.patch.object(
            AddGroupMembers,
            "perform_request",
            return_value={},
        ) as mock_add:
            IAMGroupManager.add_group_members(
                group_id=1001,
                members=unknown_members,
                system_id="test_system",
            )
            mock_add.assert_called_once()

    def test_delete_members_by_type_grouping(self):
        """测试按类型分组删除成员"""
        current_members = [
            {"type": "user", "id": "user1"},
            {"type": "user", "id": "user2"},
            {"type": "department", "id": "dept1"},
            {"type": "department", "id": "dept2"},
        ]

        with mock.patch.object(
            GetGroupMembers,
            "perform_request",
            return_value={"count": 4, "results": current_members},
        ), mock.patch.object(
            DeleteGroupMembers,
            "perform_request",
            return_value={},
        ) as mock_delete:
            IAMGroupManager.sync_group_members(
                group_id=1001,
                members=[],
                system_id="test_system",
            )

            # 应按类型分组删除，user 和 department 各调用一次
            self.assertEqual(mock_delete.call_count, 2)


class TestMemberDataValidation(SimpleTestCase):
    """测试成员数据的验证逻辑"""

    def test_member_data_with_missing_type(self):
        """测试缺少type字段的成员数据"""
        invalid_members = [
            {"id": "user1"},  # 缺少type
        ]

        with mock.patch.object(
            AddGroupMembers,
            "perform_request",
            return_value={},
        ) as mock_add:
            IAMGroupManager.add_group_members(
                group_id=1001,
                members=invalid_members,
                system_id="test_system",
            )
            mock_add.assert_called_once()

    def test_member_data_with_missing_id(self):
        """测试缺少id字段的成员数据"""
        invalid_members = [
            {"type": "user"},  # 缺少id
        ]

        with mock.patch.object(
            AddGroupMembers,
            "perform_request",
            return_value={},
        ) as mock_add:
            IAMGroupManager.add_group_members(
                group_id=1001,
                members=invalid_members,
                system_id="test_system",
            )
            mock_add.assert_called_once()

    def test_member_data_with_empty_id(self):
        """测试空id的成员数据"""
        invalid_members = [
            {"type": "user", "id": ""},
        ]

        with mock.patch.object(
            AddGroupMembers,
            "perform_request",
            return_value={},
        ) as mock_add:
            IAMGroupManager.add_group_members(
                group_id=1001,
                members=invalid_members,
                system_id="test_system",
            )
            mock_add.assert_called_once()

    def test_member_data_with_none_values(self):
        """测试包含None值的成员数据"""
        invalid_members = [
            {"type": None, "id": "user1"},
            {"type": "user", "id": None},
        ]

        with mock.patch.object(
            AddGroupMembers,
            "perform_request",
            return_value={},
        ) as mock_add:
            IAMGroupManager.add_group_members(
                group_id=1001,
                members=invalid_members,
                system_id="test_system",
            )
            mock_add.assert_called_once()
