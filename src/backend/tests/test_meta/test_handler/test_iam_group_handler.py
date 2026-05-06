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
from apps.meta.handlers.iam_group import (
    SCENE_MANAGER_GROUP_ACTIONS,
    SCENE_VIEWER_GROUP_ACTIONS,
    IAMGroupManager,
)
from apps.permission.exceptions import ActionNotExistError


def _make_mock_action(action_id):
    """创建模拟的 ActionMeta 对象"""
    action = mock.MagicMock()
    action.id = action_id
    return action


class TestBuildPermissions(SimpleTestCase):
    """测试 IAMGroupManager.build_permissions"""

    def test_scene_actions(self):
        """测试场景相关动作使用 scene 资源类型，验证完整结构"""
        actions = [_make_mock_action("view_scene"), _make_mock_action("manage_scene")]
        result = IAMGroupManager.build_permissions(
            actions=actions,
            system_id="test_system",
            scene_id="scene_001",
            scene_name="测试场景",
        )
        perm = result["_multi_permissions"][0]
        self.assertEqual(perm["actions"], [{"id": "view_scene"}, {"id": "manage_scene"}])
        self.assertEqual(perm["resources"][0]["type"], "scene")
        self.assertEqual(perm["resources"][0]["paths"][0][0]["id"], "scene_001")
        self.assertEqual(perm["resources"][0]["paths"][0][0]["name"], "测试场景")

    def test_resource_type_mapping(self):
        """测试各动作到资源类型的映射关系"""
        # (action_id, expected_resource_type)
        cases = [
            ("view_scene", "scene"),
            ("edit_strategy", "strategy"),
            ("list_risk_v2", "risk"),
            ("list_rule_v2", "scene"),
            ("view_link_table", "link_table"),
            ("edit_notice_group_v2", "notice_group"),
            ("list_pa_v2", "scene"),
        ]
        for action_id, expected_type in cases:
            with self.subTest(action_id=action_id):
                result = IAMGroupManager.build_permissions(
                    actions=[_make_mock_action(action_id)],
                    system_id="test_system",
                    scene_id="s",
                    scene_name="n",
                )
                self.assertEqual(result["_multi_permissions"][0]["resources"][0]["type"], expected_type)

    def test_unknown_action_raises_error(self):
        """测试未知动作抛出 ActionNotExistError"""
        with self.assertRaises(ActionNotExistError):
            IAMGroupManager.build_permissions(
                actions=[_make_mock_action("unknown_action")],
                system_id="test_system",
                scene_id="s",
                scene_name="n",
            )

    def test_mixed_actions_produce_multi_permissions(self):
        """测试混合动作类型产生多资源类型权限结构"""
        actions = [
            _make_mock_action("view_scene"),
            _make_mock_action("list_risk_v2"),
            _make_mock_action("edit_strategy"),
        ]
        result = IAMGroupManager.build_permissions(
            actions=actions,
            system_id="test_system",
            scene_id="s",
            scene_name="n",
        )
        types = {p["resources"][0]["type"] for p in result["_multi_permissions"]}
        self.assertEqual(types, {"scene", "risk", "strategy"})


class TestGroupMembersCRUD(SimpleTestCase):
    """测试 get_all_group_members / add_group_members / delete_group_members"""

    def test_get_all_members_pagination(self):
        """测试分页获取全部成员"""
        page1 = {"count": 3, "results": [{"type": "user", "id": "u1"}, {"type": "user", "id": "u2"}]}
        page2 = {"count": 3, "results": [{"type": "user", "id": "u3"}]}
        with mock.patch.object(GetGroupMembers, "perform_request", side_effect=[page1, page2]) as mock_get:
            result = IAMGroupManager.get_all_group_members(group_id=1001, page_size=2, system_id="test_system")
            self.assertEqual(len(result), 3)
            self.assertEqual(mock_get.call_count, 2)

    def test_get_all_members_empty(self):
        """测试无成员时返回空列表"""
        with mock.patch.object(GetGroupMembers, "perform_request", return_value={"count": 0, "results": []}):
            result = IAMGroupManager.get_all_group_members(group_id=1001, system_id="test_system")
            self.assertEqual(result, [])

    def test_add_members_success(self):
        """测试成功添加成员"""
        with mock.patch.object(AddGroupMembers, "perform_request", return_value={}) as mock_add:
            IAMGroupManager.add_group_members(
                group_id=1001,
                members=[{"type": "user", "id": "admin"}],
                expired_at=4102444800,
                system_id="test_system",
            )
            mock_add.assert_called_once()

    def test_delete_members_success(self):
        """测试成功删除成员"""
        with mock.patch.object(DeleteGroupMembers, "perform_request", return_value={}) as mock_delete:
            IAMGroupManager.delete_group_members(
                group_id=1001,
                member_type="user",
                member_ids=["admin"],
                system_id="test_system",
            )
            mock_delete.assert_called_once()


class TestCreateSingleGroupWithMembers(SimpleTestCase):
    """测试 IAMGroupManager.create_single_group_with_members"""

    def test_success_with_members(self):
        """测试完整流程：创建用户组 + 授权 + 添加成员"""
        with mock.patch.object(CreateGradeManagerGroups, "perform_request", return_value=[1001],), mock.patch.object(
            GrantGroupPolicies,
            "perform_request",
            return_value={},
        ), mock.patch.object(
            AddGroupMembers,
            "perform_request",
            return_value={},
        ) as mock_add:
            result = IAMGroupManager.create_single_group_with_members(
                group_name="测试场景-管理用户组",
                group_description="测试场景 场景管理用户组",
                group_actions=SCENE_MANAGER_GROUP_ACTIONS,
                members=["admin"],
                scene_id="s1",
                scene_name="测试场景",
            )
            self.assertEqual(result, 1001)
            mock_add.assert_called_once()

    def test_no_members_skips_add(self):
        """测试不传成员时不调用 add_group_members"""
        with mock.patch.object(CreateGradeManagerGroups, "perform_request", return_value=[1001],), mock.patch.object(
            GrantGroupPolicies,
            "perform_request",
            return_value={},
        ), mock.patch.object(
            AddGroupMembers,
            "perform_request",
            return_value={},
        ) as mock_add:
            IAMGroupManager.create_single_group_with_members(
                group_name="测试场景-管理用户组",
                group_description="测试场景 场景管理用户组",
                group_actions=SCENE_MANAGER_GROUP_ACTIONS,
                scene_id="s1",
                scene_name="测试场景",
            )
            mock_add.assert_not_called()

    def test_insufficient_group_ids_raises(self):
        """测试返回的 group_id 不足 1 个时抛出 ValueError"""
        with mock.patch.object(CreateGradeManagerGroups, "perform_request", return_value=[]):
            with self.assertRaises(ValueError):
                IAMGroupManager.create_single_group_with_members(
                    group_name="测试场景-管理用户组",
                    group_description="测试场景 场景管理用户组",
                    group_actions=SCENE_MANAGER_GROUP_ACTIONS,
                    scene_id="s1",
                    scene_name="测试场景",
                )

    def test_grant_failure_raises_with_group_ids(self):
        """测试授权失败时抛出 ValueError 并携带已创建的用户组 ID"""
        with mock.patch.object(
            CreateGradeManagerGroups,
            "perform_request",
            return_value=[1001],
        ), mock.patch.object(GrantGroupPolicies, "perform_request", side_effect=APIRequestError()):
            with self.assertRaises(ValueError) as ctx:
                IAMGroupManager.create_single_group_with_members(
                    group_name="测试场景-管理用户组",
                    group_description="测试场景 场景管理用户组",
                    group_actions=SCENE_MANAGER_GROUP_ACTIONS,
                    scene_id="s1",
                    scene_name="测试场景",
                )
            self.assertIn("1001", str(ctx.exception))


class TestSyncGroupMembers(SimpleTestCase):
    """测试 IAMGroupManager.sync_group_members"""

    def test_sync_replaces_old_with_new(self):
        """测试同步成员：删除旧成员 + 添加新成员"""
        current = {"count": 2, "results": [{"type": "user", "id": "old1"}, {"type": "user", "id": "old2"}]}
        with mock.patch.object(GetGroupMembers, "perform_request", return_value=current), mock.patch.object(
            DeleteGroupMembers, "perform_request", return_value={}
        ) as mock_del, mock.patch.object(AddGroupMembers, "perform_request", return_value={}) as mock_add:
            IAMGroupManager.sync_group_members(
                group_id=1001,
                members=[{"type": "user", "id": "new1"}],
                system_id="test_system",
            )
            mock_del.assert_called_once()
            mock_add.assert_called_once()

    def test_sync_no_old_members_only_adds(self):
        """测试无旧成员时只添加"""
        with mock.patch.object(
            GetGroupMembers, "perform_request", return_value={"count": 0, "results": []}
        ), mock.patch.object(DeleteGroupMembers, "perform_request", return_value={}) as mock_del, mock.patch.object(
            AddGroupMembers, "perform_request", return_value={}
        ) as mock_add:
            IAMGroupManager.sync_group_members(
                group_id=1001,
                members=[{"type": "user", "id": "new1"}],
                system_id="test_system",
            )
            mock_del.assert_not_called()
            mock_add.assert_called_once()

    def test_sync_mixed_types_deletes_by_type(self):
        """测试旧成员含多种类型时按类型分组删除"""
        current = {
            "count": 3,
            "results": [
                {"type": "user", "id": "u1"},
                {"type": "department", "id": "d1"},
                {"type": "user", "id": "u2"},
            ],
        }
        with mock.patch.object(GetGroupMembers, "perform_request", return_value=current), mock.patch.object(
            DeleteGroupMembers, "perform_request", return_value={}
        ) as mock_del, mock.patch.object(AddGroupMembers, "perform_request", return_value={}):
            IAMGroupManager.sync_group_members(
                group_id=1001,
                members=[{"type": "user", "id": "new1"}],
                system_id="test_system",
            )
            self.assertEqual(mock_del.call_count, 2)


class TestCreateIamGroupsIntegration(SimpleTestCase):
    """集成测试：分别调用 create_single_group_with_members 创建管理组和使用组"""

    def test_create_iam_groups_success(self):
        """测试分别创建管理用户组和使用用户组并返回正确的 group id"""
        with mock.patch.object(
            CreateGradeManagerGroups, "perform_request", side_effect=[[2001], [2002]]
        ), mock.patch.object(GrantGroupPolicies, "perform_request", return_value={}), mock.patch.object(
            AddGroupMembers, "perform_request", return_value={}
        ) as mock_add:
            manager_group_id = IAMGroupManager.create_single_group_with_members(
                group_name="测试场景-管理用户组",
                group_description="测试场景 场景管理用户组",
                group_actions=SCENE_MANAGER_GROUP_ACTIONS,
                members=[{"type": "user", "id": "admin"}],
                scene_id="1",
                scene_name="测试场景",
            )
            viewer_group_id = IAMGroupManager.create_single_group_with_members(
                group_name="测试场景-使用用户组",
                group_description="测试场景 场景使用用户组",
                group_actions=SCENE_VIEWER_GROUP_ACTIONS,
                members=[{"type": "user", "id": "viewer1"}],
                scene_id="1",
                scene_name="测试场景",
            )
            self.assertEqual(manager_group_id, 2001)
            self.assertEqual(viewer_group_id, 2002)
            self.assertEqual(mock_add.call_count, 2)


class TestSyncIamGroupMembersIntegration(SimpleTestCase):
    """集成测试：SceneResource._sync_iam_group_members"""

    def _make_scene(self, manager_group_id=1001, viewer_group_id=1002):
        scene = mock.MagicMock()
        scene.scene_id = 1
        scene.name = "测试场景"
        scene.managers = ["admin"]
        scene.users = ["viewer1"]
        scene.iam_manager_group_id = manager_group_id
        scene.iam_viewer_group_id = viewer_group_id
        return scene

    def test_sync_both_groups(self):
        """测试同时更新 managers 和 users 时两个用户组都同步"""
        from services.web.scene.resources import SceneResource

        scene = self._make_scene()
        with mock.patch.object(IAMGroupManager, "sync_group_members") as mock_sync:
            SceneResource._sync_iam_group_members(scene, {"managers": ["new_admin"], "users": ["new_user"]})
            self.assertEqual(mock_sync.call_count, 2)

    def test_no_managers_or_users_skips(self):
        """测试不包含 managers/users 时不触发同步"""
        from services.web.scene.resources import SceneResource

        scene = self._make_scene()
        with mock.patch.object(IAMGroupManager, "sync_group_members") as mock_sync:
            SceneResource._sync_iam_group_members(scene, {"name": "新名称"})
            mock_sync.assert_not_called()
