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

    def test_build_permissions_structure(self):
        """测试构建权限数据结构正确"""
        actions = [_make_mock_action("view_scene"), _make_mock_action("manage_scene")]
        result = IAMGroupManager.build_permissions(
            actions=actions,
            system_id="test_system",
            scene_id="scene_001",
            scene_name="测试场景",
        )

        self.assertEqual(result["actions"], [{"id": "view_scene"}, {"id": "manage_scene"}])
        self.assertEqual(len(result["resources"]), 1)
        resource = result["resources"][0]
        self.assertEqual(resource["system"], "test_system")
        self.assertEqual(resource["type"], "scene")
        self.assertEqual(resource["paths"][0][0]["id"], "scene_001")
        self.assertEqual(resource["paths"][0][0]["name"], "测试场景")

    def test_build_permissions_single_action(self):
        """测试单个 action 的权限构建"""
        actions = [_make_mock_action("view_scene")]
        result = IAMGroupManager.build_permissions(
            actions=actions,
            system_id="test_system",
            scene_id="scene_002",
            scene_name="测试场景2",
        )
        self.assertEqual(result["actions"], [{"id": "view_scene"}])
        self.assertEqual(result["resources"][0]["paths"][0][0]["name"], "测试场景2")

    def test_build_permissions_empty_actions(self):
        """测试空 action 列表"""
        result = IAMGroupManager.build_permissions(
            actions=[],
            system_id="test_system",
            scene_id="scene_003",
            scene_name="测试场景3",
        )
        self.assertEqual(result["actions"], [])
        self.assertEqual(len(result["resources"]), 1)


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
            self.assertEqual(mock_grant.call_count, 2)

    def test_group_names_format(self):
        """测试创建的用户组名称格式正确"""
        with mock.patch.object(
            CreateGradeManagerGroups,
            "perform_request",
            return_value=[1001, 1002],
        ) as mock_create, mock.patch.object(
            GrantGroupPolicies,
            "perform_request",
            return_value={},
        ):
            IAMGroupManager.create_scene_groups_with_members(
                scene_id=self.scene_id,
                scene_name=self.scene_name,
            )
            # perform_request 接收的是 validated_request_data 字典（位置参数）
            call_args = mock_create.call_args[0][0]
            groups = call_args["groups"]
            self.assertEqual(len(groups), 2)
            self.assertEqual(groups[0]["name"], f"{self.scene_name}-管理用户组")
            self.assertEqual(groups[1]["name"], f"{self.scene_name}-使用用户组")

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
